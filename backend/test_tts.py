"""TTS API contract, voice rollback and HTTP resource lifecycle regression tests."""
import json
import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
from fastapi.testclient import TestClient
from fastapi import UploadFile
from starlette.requests import Request

import main


def _install_transport(monkeypatch, handler):
    clients = []
    original_client = httpx.AsyncClient

    def create_client(**kwargs):
        client = original_client(transport=httpx.MockTransport(handler), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(main.httpx, "AsyncClient", create_client)
    monkeypatch.setattr(main, "GOOGLE_CLOUD_API_KEY", "test-key")
    return clients


def test_default_voice_reuses_connection_pool_and_closes_on_shutdown(monkeypatch):
    requests = []

    def synthesize(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"audioContent": "bXAz"})

    clients = _install_transport(monkeypatch, synthesize)
    monkeypatch.setattr(main, "DEFAULT_TTS_VOICE", "en-US-Chirp3-HD-Leda")
    with TestClient(main.app) as api:
        for _ in range(2):
            response = api.post("/api/tts", json={"text": "Hello!"})
            assert response.status_code == 200
            assert response.json() == {
                "audio_b64": "bXAz", "voice": "en-US-Chirp3-HD-Leda", "encoding": "MP3",
            }
        assert len(clients) == 1
        assert not clients[0].is_closed
        assert all(r["voice"]["name"] == "en-US-Chirp3-HD-Leda" for r in requests)
        assert all(r["audioConfig"]["audioEncoding"] == "MP3" for r in requests)
    assert clients[0].is_closed
    assert main.app.state.http_client is None


def test_journey_configuration_rollback_and_explicit_override(monkeypatch):
    voices = []

    def synthesize(request):
        voices.append(json.loads(request.content)["voice"]["name"])
        return httpx.Response(200, json={"audioContent": "bXAz"})

    _install_transport(monkeypatch, synthesize)
    monkeypatch.setattr(main, "DEFAULT_TTS_VOICE", "en-US-Journey-F")
    with TestClient(main.app) as api:
        default = api.post("/api/tts", json={"text": "Hello!", "voice": None})
        explicit = api.post("/api/tts", json={"text": "Hello!", "voice": "en-US-Chirp3-HD-Leda"})
    assert default.json()["voice"] == "en-US-Journey-F"
    assert explicit.json()["voice"] == "en-US-Chirp3-HD-Leda"
    assert voices == ["en-US-Journey-F", "en-US-Chirp3-HD-Leda"]


def test_provider_failure_does_not_break_next_synthesis(monkeypatch):
    calls = []

    def synthesize(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}})
        return httpx.Response(200, json={"audioContent": "bXAz"})

    clients = _install_transport(monkeypatch, synthesize)
    with TestClient(main.app) as api:
        assert api.post("/api/tts", json={"text": "Hello!"}).status_code == 502
        assert api.post("/api/tts", json={"text": "Hello!"}).status_code == 200
        assert len(clients) == 1


def test_turn_waits_for_feedback_and_saves_the_same_card_for_history(monkeypatch):
    """Faster TTS must not turn the response into delayed feedback delivery."""
    reply = "Oh, she wants cookies? What kind does she like?"
    card = {"id": "feedback-1", "original": "she want", "corrected": "she wants",
            "explanation_ko": "3인칭 단수 현재형에는 -s를 붙여요."}
    timestamp = "2026-09-15T00:00:00+00:00"
    sessions, messages = Mock(), Mock()
    for query in (sessions, messages):
        for method in ("select", "eq", "order", "insert"):
            getattr(query, method).return_value = query
    sessions.execute.return_value = SimpleNamespace(data=[{
        "id": "conversation-1", "user_id": "user-1", "ended_at": None,
        "character_name": "Pally", "level": "B1",
    }])
    messages.execute.side_effect = [
        SimpleNamespace(data=[]), SimpleNamespace(data=[]),
        SimpleNamespace(data=[{"id": "turn-1", "role": "user", "created_at": timestamp}]),
    ]
    sb = Mock()
    sb.table.side_effect = lambda name: {"sessions": sessions, "messages": messages}[name]
    monkeypatch.setattr(main, "get_supabase", lambda: sb)
    monkeypatch.setattr(main, "_reserve_turn", lambda *_: 1)
    monkeypatch.setattr(main, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(main, "DEFAULT_TTS_VOICE", "en-US-Chirp3-HD-Leda")
    monkeypatch.setattr(main, "_stt_from_bytes", AsyncMock(return_value=("she want cookies", 1.0)))
    monkeypatch.setattr(main, "_call_gemini_chat", AsyncMock(return_value=reply))

    async def scenario():
        audio_ready, feedback_started, release_feedback = asyncio.Event(), asyncio.Event(), asyncio.Event()

        def synthesize(request):
            payload = json.loads(request.content)
            assert payload["voice"]["name"] == "en-US-Chirp3-HD-Leda"
            assert payload["input"]["text"] == reply
            audio_ready.set()
            return httpx.Response(200, json={"audioContent": "bXAz"})

        async def feedback(utterance, spoken_reply, level):
            assert spoken_reply == reply
            feedback_started.set()
            await release_feedback.wait()
            return [card]

        _install_transport(monkeypatch, synthesize)
        monkeypatch.setattr(main, "_gen_feedback", feedback)
        async with main.app.router.lifespan_context(main.app):
            task = asyncio.create_task(main.create_turn(
                "conversation-1", Request({"type": "http"}),
                UploadFile(filename="test.wav", file=BytesIO(b"test-audio")),
                "user-1", "request-1",
            ))
            try:
                await asyncio.wait_for(asyncio.gather(audio_ready.wait(), feedback_started.wait()), 2)
                assert not task.done()
                messages.insert.assert_not_called()
            finally:
                release_feedback.set()
            result = await asyncio.wait_for(task, 2)
        assert result["pally"] == {"text": reply, "audio": "bXAz"}
        assert result["feedback"] == [card]
        assert result["feedback_pending"] is False
        saved_user, saved_pally = messages.insert.call_args.args[0]
        assert saved_user["feedback"] == [card]
        assert saved_pally["transcript"] == reply
        saved_user.update(id="turn-1", created_at=timestamp)
        saved_pally.update(id="reply-1", created_at=timestamp)
        assert main._turn_detail(saved_user, saved_pally, 1)["feedback"] == [card]

    asyncio.run(scenario())
