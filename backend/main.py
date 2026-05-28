# -*- coding: utf-8 -*-
import asyncio
import base64
import json
import logging
import os
import sys

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional

load_dotenv()

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ai.analyzer import analyze_utterance
from ai.matrix_engine import apply_ema, compute_character, describe_character

try:
    from lib.supabase import get_supabase
    _SUPABASE_ENABLED = True
except Exception:
    _SUPABASE_ENABLED = False
    get_supabase = None  # type: ignore

GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")    # Gemini (AI Studio)
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")  # STT / TTS (Cloud Console)

# 하나의 키만 있을 때 공용으로 사용
if not GOOGLE_AI_API_KEY:
    GOOGLE_AI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if not GOOGLE_CLOUD_API_KEY:
    GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_API_KEY", "")

app = FastAPI(title="Pally Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ────────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    utterance: str
    session_id: Optional[str] = None
    current_axes: Optional[Dict[str, int]] = None  # EMA용 이전 누적 축 점수


class FeedbackResponse(BaseModel):
    status: str
    axes: Dict[str, int]             # EMA 적용 후 누적 축 점수
    character: Dict[str, int]        # 캐릭터 파라미터
    character_labels: Dict[str, str]
    feedback: Dict[str, str]         # correction / tone_feedback / practice_prompt
    tts_audio: Optional[str] = None  # base64 MP3 (correction 문장 TTS)


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-Journey-F"
    speaking_rate: Optional[float] = 1.0


class ChatMessage(BaseModel):
    role: str   # "user" | "pally"
    content: str


class ChatRequest(BaseModel):
    utterance: str                              # STT 결과 텍스트 (FE에서 /api/stt 호출 후 전달)
    session_id: Optional[str] = None
    current_axes: Optional[Dict[str, int]] = None
    conversation_history: Optional[list[ChatMessage]] = None
    character_name: Optional[str] = "Pally"
    level: Optional[str] = "B1"                # A2 / B1 / B2 / C1


class InlineHintKo(BaseModel):
    hint: str        # 한국어 힌트 (교정 설명 또는 칭찬)
    expression: str  # 올바른 영어 표현


class ChatResponse(BaseModel):
    status: str
    transcript: str                            # 사용자 발화 텍스트 (echo)
    reply: str                                 # Pally 응답 텍스트
    tts_audio: Optional[str] = None           # base64 MP3 (Pally 응답 TTS)
    axes: Dict[str, int]
    character: Dict[str, int]
    character_labels: Dict[str, str]
    hint_ko: Optional[InlineHintKo] = None    # 인라인 한국어 힌트


# ── Health ───────────────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug-keys")
def debug_keys():
    """서버가 로드한 API 키 확인용 (끝 4자리만 표시)"""
    def mask(key: str) -> str:
        return f"...{key[-4:]}" if len(key) > 4 else "(비어있음)"
    return {
        "GOOGLE_AI_API_KEY": mask(GOOGLE_AI_API_KEY),
        "GOOGLE_CLOUD_API_KEY": mask(GOOGLE_CLOUD_API_KEY),
    }


# ── STT — Google Cloud Speech-to-Text ────────────────────────────────────────


def _detect_encoding(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "webm" in ct or "opus" in ct:
        return "WEBM_OPUS"
    if "mp3" in ct or "mpeg" in ct:
        return "MP3"
    if "wav" in ct:
        return "LINEAR16"
    if "flac" in ct:
        return "FLAC"
    return "WEBM_OPUS"  # browser MediaRecorder 기본값


@app.post("/api/stt")
async def stt(audio: UploadFile = File(...)):
    """
    오디오 파일 → 텍스트 변환 (Google Cloud Speech-to-Text v1)

    - FE: MediaRecorder로 녹음한 webm/opus 파일을 multipart/form-data로 전송
    - 응답: { transcript, confidence }
    - 제한: 동기 인식은 최대 60초. 그 이상은 longrunningrecognize 사용 필요.
    """
    if not GOOGLE_CLOUD_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_CLOUD_API_KEY not configured")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    payload = {
        "config": {
            "encoding": _detect_encoding(audio.content_type),
            "languageCode": "en-US",
            "model": "latest_long",
            "enableAutomaticPunctuation": True,
        },
        "audio": {"content": base64.b64encode(audio_bytes).decode()},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://speech.googleapis.com/v1/speech:recognize?key={GOOGLE_CLOUD_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Google STT error: {resp.text}")

    results = resp.json().get("results", [])
    if not results:
        return {"transcript": "", "confidence": 0.0}

    alt = results[0]["alternatives"][0]
    return {
        "transcript": alt["transcript"].strip(),
        "confidence": alt.get("confidence", 1.0),
    }


# ── TTS — Google Cloud Text-to-Speech ────────────────────────────────────────


async def _call_google_tts(
    text: str,
    voice: str = "en-US-Journey-F",
    speaking_rate: float = 1.0,
) -> str:
    """Google Cloud TTS 호출 → base64 MP3 반환"""
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": "en-US", "name": voice},
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": speaking_rate,
            "pitch": 0.0,
            "effectsProfileId": ["headphone-class-device"],
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_CLOUD_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=_format_google_tts_error(resp))

    return resp.json()["audioContent"]  # base64 MP3


def _format_google_tts_error(resp: httpx.Response) -> dict:
    try:
        error = resp.json().get("error", {})
    except Exception:
        return {
            "message": "Google TTS request failed.",
            "status_code": resp.status_code,
            "google_response": resp.text,
        }

    reason = None
    for detail in error.get("details", []):
        if detail.get("@type") == "type.googleapis.com/google.rpc.ErrorInfo":
            reason = detail.get("reason")
            break

    help_text = "Check the Google Cloud API key, billing, and Text-to-Speech API status."
    if reason == "API_KEY_SERVICE_BLOCKED":
        help_text = (
            "This API key is restricted from calling Cloud Text-to-Speech. "
            "In Google Cloud Console, open APIs & Services > Credentials > this API key > "
            "API restrictions, then allow Cloud Text-to-Speech API or remove API restrictions. "
            "Also confirm Cloud Text-to-Speech API is enabled for the same project."
        )
    elif error.get("status") == "PERMISSION_DENIED":
        help_text = (
            "Permission denied from Google Cloud. Confirm billing is enabled, "
            "Cloud Text-to-Speech API is enabled, and GOOGLE_CLOUD_API_KEY belongs to that project."
        )

    return {
        "message": error.get("message", "Google TTS request failed."),
        "status": error.get("status"),
        "reason": reason,
        "help": help_text,
    }


@app.post("/api/tts")
async def tts(req: TTSRequest):
    """
    텍스트 → MP3 오디오 (Google Cloud Text-to-Speech)

    - 응답: { audio_b64, voice, encoding }
    - FE: audio_b64를 Audio() 또는 <audio> 태그로 재생
    """
    if not GOOGLE_CLOUD_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_CLOUD_API_KEY not configured")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    audio_b64 = await _call_google_tts(
        req.text,
        req.voice or "en-US-Journey-F",
        req.speaking_rate or 1.0,
    )
    return {"audio_b64": audio_b64, "voice": req.voice, "encoding": "MP3"}


# ── Feedback — 5축 분석 + Gemini 피드백 + TTS ────────────────────────────────

_FEEDBACK_SYSTEM_PROMPT = """\
You are Pally, a friendly English conversation tutor.
Analyze the user's utterance and provide structured feedback.

Return ONLY valid JSON with exactly these three fields:
{
  "correction": "A natural alternative phrasing or minor correction. If already natural, offer a slight variation.",
  "tone_feedback": "One encouraging sentence about their tone, energy, or humor style.",
  "practice_prompt": "One engaging follow-up question for them to practice responding to."
}

Rules:
- Each field: 1-2 sentences max.
- Be warm, encouraging, and specific.
- Do NOT mention the numeric scores directly.
"""


async def _call_gemini_feedback(utterance: str, axes: dict) -> dict:
    """Gemini 2.5 Flash REST API 호출 → 피드백 JSON 반환"""
    user_prompt = (
        f'User utterance: "{utterance}"\n'
        f"Style analysis — Formality: {axes['Formality']}/100, "
        f"Energy: {axes['Energy']}/100, Intimacy: {axes['Intimacy']}/100, "
        f"Humor: {axes['Humor']}/100, Curiosity: {axes['Curiosity']}/100\n\n"
        "Provide feedback JSON:"
    )

    payload = {
        "system_instruction": {"parts": [{"text": _FEEDBACK_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
            "maxOutputTokens": 512,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={GOOGLE_AI_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text}")

    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Gemini가 간혹 ```json ... ``` 마크다운으로 감싸서 반환하는 경우 처리
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


_FEEDBACK_FALLBACK = {
    "correction": "Great attempt! Try to vary your sentence structure for more natural flow.",
    "tone_feedback": "Your expression is coming through clearly — keep it up!",
    "practice_prompt": "Can you try expressing the same idea in a different way?",
}


@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest):
    """
    utterance → 5축 분석 → EMA → 캐릭터 파라미터 → Gemini 피드백 → TTS

    흐름:
      1. analyze_utterance()  → raw 5축 점수
      2. apply_ema()          → 이전 축 점수 반영 (current_axes 있을 때)
      3. compute_character()  → 캐릭터 파라미터
      4. Gemini 2.5 Flash     → correction / tone_feedback / practice_prompt
      5. Google TTS           → correction 문장을 MP3로 변환 (tts_audio)
    """
    if not GOOGLE_AI_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_AI_API_KEY not configured")
    if not req.utterance.strip():
        raise HTTPException(status_code=400, detail="utterance is required")

    # 1. 5축 분석
    raw_axes = analyze_utterance(req.utterance)

    # 2. EMA — 이전 누적 점수가 있을 때만 적용
    smoothed_axes = apply_ema(req.current_axes, raw_axes) if req.current_axes else raw_axes

    # 3. 캐릭터 파라미터
    character = compute_character(smoothed_axes)
    tone_label, energy_label, humor_label = describe_character(character)

    # 4. Gemini 피드백 (실패 시 fallback)
    try:
        feedback_data = await _call_gemini_feedback(req.utterance, smoothed_axes)
        for key in ("correction", "tone_feedback", "practice_prompt"):
            if key not in feedback_data:
                raise ValueError(f"Missing key: {key}")
    except Exception as e:
        logging.warning(f"Gemini fallback triggered: {e}")
        feedback_data = _FEEDBACK_FALLBACK

    # 5. TTS — correction 문장을 음성으로 (실패해도 피드백은 정상 반환)
    tts_audio: Optional[str] = None
    correction_text = feedback_data.get("correction", "")
    if correction_text:
        try:
            tts_audio = await _call_google_tts(correction_text)
        except Exception:
            tts_audio = None

    return {
        "status": "ok",
        "axes": smoothed_axes,
        "character": character,
        "character_labels": {
            "tone": tone_label,
            "energy": energy_label,
            "humor": humor_label,
        },
        "feedback": feedback_data,
        "tts_audio": tts_audio,
    }


# ── Chat — STT 결과 → Gemini 대화 응답 → TTS + 한국어 힌트 ────────────────────

_LEVEL_GUIDE = {
    "A2": "Use very simple words and short sentences (A2 beginner level).",
    "B1": "Use everyday vocabulary and mid-length sentences (B1 intermediate level).",
    "B2": "Use varied vocabulary and natural phrasing (B2 upper-intermediate level).",
    "C1": "Use rich vocabulary and complex sentences naturally (C1 advanced level).",
}


def _build_chat_system_prompt(character_name: str, level: str) -> str:
    level_guide = _LEVEL_GUIDE.get(level, _LEVEL_GUIDE["B1"])
    return f"""\
You are {character_name}, a warm and playful English conversation friend.
{level_guide}
Keep responses to 1-3 sentences — natural, friendly, and engaging.

When the user makes a grammar or vocabulary mistake:
- Do NOT explicitly point it out or say "you made a mistake".
- Instead, naturally use the correct expression in your own reply so the user can pick it up.
- Example: user says "I'm very boring today" → you reply "Oh, you're bored? What's going on?"

Stay in character as {character_name} at all times. Never break the fourth wall."""


async def _call_gemini_chat(
    utterance: str,
    history: list,
    character_name: str,
    level: str,
) -> str:
    """Gemini 2.5 Flash로 Pally 대화 응답 생성"""
    system_prompt = _build_chat_system_prompt(character_name, level)

    contents = []
    for msg in (history or []):
        role = "user" if msg.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": utterance}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 256,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={GOOGLE_AI_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini chat error {resp.status_code}: {resp.text}")

    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


_HINT_KO_SYSTEM_PROMPT = """\
You are a Korean-speaking English tutor assistant. Given the user's English utterance and Pally's reply,
identify whether Pally implicitly corrected a grammar or vocabulary mistake (by naturally using the correct form).
Explain briefly in Korean, or give praise if no correction was needed.

Return ONLY valid JSON:
{
  "hint": "한국어 설명 1-2문장. 교정이 있으면 무엇이 어떻게 교정됐는지 설명. 없으면 '자연스러운 표현이에요!'처럼 칭찬.",
  "expression": "올바른 영어 표현 (짧은 구나 문장. 교정 없으면 사용자 표현 그대로)"
}
"""

_HINT_KO_FALLBACK = InlineHintKo(
    hint="잘 표현했어요! 계속 연습하면 더 자연스러워질 거예요.",
    expression="Keep it up!",
)


async def _call_gemini_hint_ko(utterance: str, pally_reply: str) -> InlineHintKo:
    """사용자 발화 + Pally 응답 → 한국어 인라인 힌트 (Gemini 2.5 Flash)"""
    user_prompt = (
        f'User said: "{utterance}"\n'
        f'Pally replied: "{pally_reply}"\n\n'
        "Provide Korean hint JSON:"
    )
    payload = {
        "system_instruction": {"parts": [{"text": _HINT_KO_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
            "maxOutputTokens": 256,
        },
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={GOOGLE_AI_API_KEY}",
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini hint error {resp.status_code}: {resp.text}")
    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(raw)
    return InlineHintKo(hint=data.get("hint", ""), expression=data.get("expression", ""))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    utterance(텍스트) → 5축 분석 → EMA → 캐릭터 파라미터 → Gemini 대화 응답 → TTS + 한국어 힌트

    흐름:
      1. Supabase 세션 조회/생성 + 대화 이력 로드 (session_id 있을 때)
      2. analyze_utterance()  → raw 5축 점수
      3. apply_ema()          → EMA 평활화 (alpha=0.7)
      4. compute_character()  → 캐릭터 파라미터
      5. Gemini 2.5 Flash     → Pally 대화 응답 (자연스러운 교정 포함)
      6. TTS + 한국어 힌트    → asyncio.gather()로 병렬 실행
      7. Supabase 저장        → user + pally 메시지
    """
    if not GOOGLE_AI_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_AI_API_KEY not configured")
    if not req.utterance.strip():
        raise HTTPException(status_code=400, detail="utterance is required")

    # 1. Supabase 세션 & 대화 이력
    # Phase 1C에서는 frontend가 anonymous client UUID로 session_id를 보내면
    # 동일 세션의 이전 messages가 DB에서 로드되고 이후 요청에 conversation_history로 이어집니다.
    character_name = req.character_name or "Pally"
    level = req.level or "B1"
    history: list[ChatMessage] = req.conversation_history or []

    if req.session_id and _SUPABASE_ENABLED:
        try:
            sb = get_supabase()
            session_res = sb.table("sessions").select("id, character_name, level").eq("id", req.session_id).execute()
            if getattr(session_res, "error", None):
                raise RuntimeError(getattr(session_res.error, "message", repr(session_res.error)))
            if session_res.data:
                character_name = session_res.data[0]["character_name"]
                level = session_res.data[0]["level"]
            else:
                insert_session_res = sb.table("sessions").insert({
                    "id": req.session_id,
                    "character_name": character_name,
                    "level": level,
                }).execute()
                if getattr(insert_session_res, "error", None):
                    raise RuntimeError(getattr(insert_session_res.error, "message", repr(insert_session_res.error)))
            msg_res = sb.table("messages").select("role, transcript").eq("session_id", req.session_id).order("created_at").execute()
            if getattr(msg_res, "error", None):
                raise RuntimeError(getattr(msg_res.error, "message", repr(msg_res.error)))
            if msg_res.data:
                history = [ChatMessage(role=m["role"], content=m["transcript"]) for m in msg_res.data]
        except Exception as e:
            logging.warning(f"Supabase session load failed: {e}")

    # 2. 5축 분석
    raw_axes = analyze_utterance(req.utterance)

    # 3. EMA
    smoothed_axes = apply_ema(req.current_axes, raw_axes) if req.current_axes else raw_axes

    # 4. 캐릭터 파라미터
    character = compute_character(smoothed_axes)
    tone_label, energy_label, humor_label = describe_character(character)

    # 5. Gemini 대화 응답
    try:
        reply = await _call_gemini_chat(req.utterance, history, character_name, level)
    except Exception as e:
        logging.warning(f"Gemini chat fallback: {e}")
        reply = "I see! Tell me more."

    # 6. TTS + 한국어 힌트 (병렬)
    tts_result, hint_result = await asyncio.gather(
        _call_google_tts(reply),
        _call_gemini_hint_ko(req.utterance, reply),
        return_exceptions=True,
    )
    tts_audio = tts_result if not isinstance(tts_result, Exception) else None
    hint_ko: Optional[InlineHintKo] = (
        hint_result if not isinstance(hint_result, Exception) else _HINT_KO_FALLBACK
    )

    # 7. Supabase 저장
    if req.session_id and _SUPABASE_ENABLED:
        try:
            sb = get_supabase()
            save_res = sb.table("messages").insert([
                {
                    "session_id": req.session_id,
                    "role": "user",
                    "transcript": req.utterance,
                    "axes": smoothed_axes,
                    "character": character,
                },
                {
                    "session_id": req.session_id,
                    "role": "pally",
                    "transcript": reply,
                    "axes": None,
                    "character": character,
                },
            ]).execute()
            if getattr(save_res, "error", None):
                raise RuntimeError(getattr(save_res.error, "message", repr(save_res.error)))
        except Exception as e:
            logging.warning(f"Supabase save failed: {e}")

    return {
        "status": "ok",
        "transcript": req.utterance,
        "reply": reply,
        "tts_audio": tts_audio,
        "axes": smoothed_axes,
        "character": character,
        "character_labels": {
            "tone": tone_label,
            "energy": energy_label,
            "humor": humor_label,
        },
        "hint_ko": hint_ko,
    }
