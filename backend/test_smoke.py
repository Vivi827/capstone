# -*- coding: utf-8 -*-
"""
CI smoke test — 시크릿/실서비스 없이 도는 최소 검증.

목적:
- 앱이 import 되는지 (문법 에러, import 에러, 정의 안 된 참조 등)
- 핵심 라우트가 사라지지 않았는지 (PR #33 처럼 머지 사고로 엔드포인트가
  조용히 삭제되는 것을 CI 단계에서 차단)

실제 STT/Gemini/TTS/Supabase E2E 는 시크릿·비용 때문에 여기서 돌리지 않는다.
그건 로컬/별도 통합 테스트에서 실제 서비스로 검증한다.
"""
import main


def test_app_imports():
    assert main.app is not None


def test_core_routes_present():
    paths = {getattr(r, "path", None) for r in main.app.routes}
    # 절대 사라지면 안 되는 핵심 비즈니스 엔드포인트. 새 라우트 추가는 자유.
    required = {
        "/api/health",
        "/api/onboarding",
        "/api/profile",
        "/api/profile/avatar",
        "/api/conversations",
        "/api/conversations/{conversation_id}/turns",
    }
    missing = required - paths
    assert not missing, f"core routes missing (merge clobber?): {sorted(missing)}"


def test_extract_avatar_normalizes_oauth_metadata():
    class User:
        user_metadata = {"picture": "https://example.com/avatar.png"}

    assert main._extract_avatar(User()) == "https://example.com/avatar.png"


def test_extract_avatar_returns_none_without_profile_picture():
    class User:
        user_metadata = {"name": "Pally user"}

    assert main._extract_avatar(User()) is None


def test_extract_avatar_requests_high_resolution_google_photo():
    class User:
        user_metadata = {"picture": "https://lh3.googleusercontent.com/a/example=s96-c"}

    assert main._extract_avatar(User()) == "https://lh3.googleusercontent.com/a/example=s512-c"


def test_extract_avatar_prefers_kakao_profile_image_over_thumbnail():
    class User:
        user_metadata = {
            "avatar_url": "https://k.kakaocdn.net/thumbnail.jpg",
            "kakao_account": {
                "profile": {
                    "profile_image_url": "https://k.kakaocdn.net/profile.jpg",
                    "thumbnail_image_url": "https://k.kakaocdn.net/thumbnail.jpg",
                },
            },
        }

    assert main._extract_avatar(User()) == "https://k.kakaocdn.net/profile.jpg"


def test_retrying_query_replays_attribute_chaining():
    """postgrest 의 `q.not_.is_(...)` 처럼 호출 없는 속성 체이닝도 그대로 재현돼야 한다.

    재시도 래퍼가 이 패턴을 못 다뤄 GET /api/conversations?status=completed 가
    500 로 죽은 적이 있다. 같은 회귀를 CI 에서 차단한다.
    """
    trace = []

    class FakeBuilder:
        @property
        def not_(self):
            trace.append("not_")
            return self

        def select(self, *args):
            trace.append("select")
            return self

        def eq(self, *args):
            trace.append("eq")
            return self

        def is_(self, column, value):
            trace.append(f"is_({column},{value})")
            return self

        def execute(self):
            trace.append("execute")
            return "RESULT"

    query = main._RetryingQuery(lambda: FakeBuilder())
    result = query.select("*").eq("user_id", "u").not_.is_("ended_at", "null").execute()

    assert result == "RESULT"
    assert trace == ["select", "eq", "not_", "is_(ended_at,null)", "execute"]


def test_should_retry_is_conservative_for_writes():
    """읽기는 전송 오류 전부 재시도하되, 쓰기는 서버가 처리하지 않은 것이 확실한
    실패만 재시도한다 (중복 실행 방지)."""
    import httpx

    assert main._should_retry(httpx.ReadTimeout("x"), is_write=False) is True
    assert main._should_retry(httpx.ReadTimeout("x"), is_write=True) is False
    assert main._should_retry(httpx.ConnectError("x"), is_write=True) is True
    assert main._should_retry(ValueError("x"), is_write=False) is False


def test_should_retry_writes_on_http2_goaway():
    """Supabase 가 HTTP/2 GOAWAY 로 커넥션을 정리하면 httpx 가 RemoteProtocolError 를 낸다.
    GOAWAY 규약상 그 요청은 서버가 처리하지 않았으므로 쓰기도 재시도해야 한다.

    이 케이스를 쓰기에서 제외했다가 온보딩·대화 생성·업적 저장이 503 으로 실패한 적이 있다.
    """
    import httpx

    assert main._should_retry(httpx.RemoteProtocolError("goaway"), is_write=True) is True
    assert main._should_retry(httpx.RemoteProtocolError("goaway"), is_write=False) is True


def test_retrying_query_retries_write_after_goaway():
    """GOAWAY 로 첫 시도가 끊겨도 쓰기가 새 커넥션으로 재시도되어 성공해야 한다."""
    import httpx

    attempts = []

    class FlakyBuilder:
        def insert(self, *args, **kwargs):
            return self

        def execute(self):
            attempts.append(1)
            if len(attempts) == 1:
                raise httpx.RemoteProtocolError("<ConnectionTerminated error_code:0>")
            return "SAVED"

    query = main._RetryingQuery(lambda: FlakyBuilder())

    assert query.insert({"a": 1}).execute() == "SAVED"
    assert len(attempts) == 2


def test_conversation_turns_restore_user_before_pally_for_equal_timestamps():
    messages = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "role": "pally",
            "transcript": "That's great you're focused on your project!",
            "feedback": None,
            "created_at": "2026-09-06T10:00:00+00:00",
        },
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "role": "user",
            "transcript": "just working on my project",
            "feedback": [],
            "created_at": "2026-09-06T10:00:00+00:00",
        },
    ]

    assert main._conversation_turns(messages) == [
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "sequence": 1,
            "status": "completed",
            "user_transcript": "just working on my project",
            "pally_text": "That's great you're focused on your project!",
            "feedback": [],
            "feedback_pending": False,
            "created_at": "2026-09-06T10:00:00+00:00",
        }
    ]
