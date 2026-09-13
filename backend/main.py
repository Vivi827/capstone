# -*- coding: utf-8 -*-
import asyncio
import base64
import json
import logging
import os
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import hashlib
import time
import uuid
from collections import deque
from datetime import datetime, time as dtime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, field_validator
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
from ai.reply_shaping import shape_reply

try:
    from lib.supabase import get_supabase as _get_supabase_raw
    _SUPABASE_ENABLED = True
except Exception:
    _SUPABASE_ENABLED = False
    _get_supabase_raw = None  # type: ignore

# AI 담당 제공: generate_feedback(utterance, pally_reply, level) -> (items, failed).
# 없으면 None → turn 의 feedback 은 [] (실패 아님, 미구현).
try:
    from ai.generate_feedback import generate_feedback
except Exception:
    generate_feedback = None  # type: ignore

# 5축 분석 어댑터 (rule|ml|hybrid, env PALLY_AXIS_ANALYZER, 기본 rule).
# 한 번만 생성해 재사용(ml/hybrid 모델 재로딩 방지). 실패하면 기존 rule 함수로 폴백.
try:
    from ai.analyzers import get_axis_analyzer
    _axis_analyzer = get_axis_analyzer()
except Exception as _axis_e:
    logging.warning(f"axis analyzer init failed → analyze_utterance(rule) fallback: {_axis_e}")
    _axis_analyzer = None


def _analyze_axes(text: str) -> Dict[str, int]:
    """5축 dict. 어댑터(rule/ml/hybrid) 사용, 실패 시 기존 rule 함수로 폴백."""
    if _axis_analyzer is not None:
        try:
            return _axis_analyzer.analyze(text).model_dump()
        except Exception as e:
            logging.warning(f"axis analyzer.analyze failed → rule fallback: {e}")
    return analyze_utterance(text)


GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")    # Gemini (AI Studio)
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")  # STT / TTS (Cloud Console)

app = FastAPI(title="Pally Backend API", version="1.0.0")

# CORS 허용 origin: 기본 "*"(개발). 프로덕션은 CORS_ALLOW_ORIGINS 에 프론트 도메인을
# 콤마로 넣어 제한한다. 예: CORS_ALLOW_ORIGINS=https://capstone-eight-virid.vercel.app
_cors_env = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
_allow_origins = ["*"] if _cors_env == "*" else [o.strip() for o in _cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# production에서만 debug route를 숨기려면 PALLY_DEBUG_ENDPOINTS=1 을 설정한 환경에서만 등록.
# Railway 운영 환경에는 이 변수를 두지 않아 /api/debug-keys 가 노출되지 않는다.
_DEBUG_ENDPOINTS_ENABLED = os.getenv("PALLY_DEBUG_ENDPOINTS") == "1"

# 무료 일일 turn 한도. 하드코딩하지 않고 config 로 빼서 정책 변경 시 재배포 없이 조정.
FREE_DAILY_TURNS = int(os.getenv("FREE_DAILY_TURNS", "20"))
_KST = timezone(timedelta(hours=9))  # 한국은 DST 없음 → 고정 UTC+9


# ── Errors — 계약 포맷 { "error": { code, message, request_id, details? } } ────


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Optional[dict] = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _request_id(request: Request) -> str:
    """미들웨어가 심어둔 request_id를 반환 (없으면 새로 생성)."""
    return getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex}"


# ── Observability — 구조화 로그 + turn 단계별 latency ────────────────────────
# 기존 STT/Gemini/TTS 함수는 안 건드리고, 호출부(미들웨어·create_turn)에서 시간만 잰다.

_TURN_METRICS: deque = deque(maxlen=200)  # 최근 turn latency (단일 프로세스 메모리)


def _log_event(event: str, **fields) -> None:
    """구조화 로그 한 줄(JSON). 기존 로그 포맷은 유지하고 새 이벤트만 JSON 문자열로 emit."""
    try:
        logging.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))
    except Exception:
        logging.info(f"event={event} {fields}")


def _pct(values: list, p: int):
    if not values:
        return None
    s = sorted(values)
    k = min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))
    return round(s[k])


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # 미들웨어에서 잡힌 예외도 access 로그로 남기고 다시 올린다.
        _log_event(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=500,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        raise
    response.headers["X-Request-ID"] = request_id
    _log_event(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
    return response


def _error_body(code: str, message: str, request_id: str, details: Optional[dict] = None) -> dict:
    error: dict = {"code": code, "message": message, "request_id": request_id}
    if details:
        error["details"] = details
    return {"error": error}


def _is_transport_error(exc: BaseException) -> bool:
    """Supabase 호출이 '연결' 때문에 실패했는지 판별 (죽은 keep-alive 커넥션·타임아웃 등).
    무효 토큰 같은 논리적 거절(AuthApiError)과 구분하기 위해 쓴다."""
    return isinstance(exc, httpx.TransportError)


def _reset_supabase_client() -> None:
    """죽은 커넥션을 물고 있는 Supabase 싱글톤을 폐기해, 다음 호출에서 새 커넥션으로
    재생성되게 한다. lib/supabase.py(다른 담당 영역)는 수정하지 않고 모듈 전역만 비운다.
    이게 없으면 Supabase 가 잠시 끊겼다 복구돼도 프로세스를 재배포할 때까지 계속 실패한다."""
    try:
        import lib.supabase as _sb_module
        _sb_module._client = None
    except Exception as e:
        logging.warning(f"supabase client reset failed (non-fatal): {e}")


# 쓰기 재시도는 "요청이 서버에서 처리되지 않은 것이 확실한" 실패에만 허용한다.
# ReadTimeout 등은 서버가 이미 처리했을 수 있어 재시도하면 중복 실행 위험이 있다.
_WRITE_OPS = {"insert", "update", "upsert", "delete"}

# Supabase 가 HTTP/2 GOAWAY(ConnectionTerminated)로 커넥션을 주기적으로 정리한다.
# httpx 는 이를 RemoteProtocolError 로 올리는데, GOAWAY 규약상 last_stream_id 이후의
# 요청은 서버가 처리하지 않았음이 보장되므로 쓰기라도 재시도해도 중복되지 않는다.
_WRITE_SAFE_RETRY = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError)


def _should_retry(exc: BaseException, is_write: bool) -> bool:
    if is_write:
        return isinstance(exc, _WRITE_SAFE_RETRY)
    return _is_transport_error(exc)


class _QueryStep:
    """빌더의 한 단계. 호출되면 메서드 호출로, 그대로 속성을 더 타고 가면 속성 접근으로
    기록한다. postgrest 의 `q.not_.is_(...)` 처럼 호출 없는 속성 체이닝을 지원하기 위함."""

    def __init__(self, query, name):
        self._query = query
        self._name = name

    def __call__(self, *args, **kwargs):
        self._query._ops.append(("call", self._name, args, kwargs))
        return self._query

    def __getattr__(self, name):
        self._query._ops.append(("attr", self._name, (), {}))
        return _QueryStep(self._query, name)


class _RetryingQuery:
    """PostgREST 쿼리 빌더 프록시. 체이닝을 기록해 두었다가 execute() 에서 실행하고,
    죽은 커넥션 때문에 실패하면 클라이언트를 폐기한 뒤 새 커넥션으로 1회 재시도한다."""

    def __init__(self, build):
        self._build = build   # () -> 새 클라이언트에서 시작하는 빌더
        self._ops = []        # ("call"|"attr", name, args, kwargs)

    def __getattr__(self, name):
        return _QueryStep(self, name)

    def _run(self):
        query = self._build()
        for kind, name, args, kwargs in self._ops:
            query = getattr(query, name) if kind == "attr" else getattr(query, name)(*args, **kwargs)
        return query.execute()

    def execute(self):
        try:
            return self._run()
        except Exception as e:
            is_write = any(name in _WRITE_OPS for _, name, _, _ in self._ops)
            if not _should_retry(e, is_write):
                raise
            logging.warning(f"DB transport error, retrying with fresh client: {e}")
            _reset_supabase_client()
            return self._run()


class _RetryingSupabase:
    """get_supabase() 가 돌려주는 클라이언트 래퍼. table()/rpc() 만 재시도로 감싸고
    auth 등 나머지는 원본 클라이언트에 그대로 위임한다. 호출부는 수정하지 않는다."""

    def table(self, name):
        return _RetryingQuery(lambda: _get_supabase_raw().table(name))

    def rpc(self, fn_name, params=None):
        if params is None:
            return _RetryingQuery(lambda: _get_supabase_raw().rpc(fn_name))
        return _RetryingQuery(lambda: _get_supabase_raw().rpc(fn_name, params))

    def __getattr__(self, name):
        return getattr(_get_supabase_raw(), name)


def get_supabase():
    """Supabase 클라이언트(재시도 래퍼). 죽은 커넥션으로 인한 일시적 실패가
    사용자에게 503 으로 보이지 않도록 호출부 수정 없이 한 곳에서 방어한다."""
    return _RetryingSupabase()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    # 503(연결·저장소 실패)은 커넥션이 죽었을 가능성이 있으므로 싱글톤을 폐기해
    # 다음 요청이 새 커넥션으로 자가 회복하게 한다 (수동 재배포 없이 복구).
    if exc.status_code == 503:
        _reset_supabase_client()
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, _request_id(request), exc.details),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # FastAPI 기본 {"detail": ...} 대신 계약 포맷으로 통일.
    return JSONResponse(
        status_code=422,
        content=_error_body(
            "validation_error",
            "Request validation failed.",
            _request_id(request),
            {"errors": exc.errors()},
        ),
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
    # 계약: liveness만, 환경변수/키 정보 노출 금지.
    return {"status": "ok", "version": app.version}


if _DEBUG_ENDPOINTS_ENABLED:
    # debug-keys 와 동일하게 조건부 등록 → 프로덕션에선 라우트 자체가 없어 openapi 에도 안 뜬다.
    @app.get("/api/metrics")
    def metrics():
        """
        최근 turn 파이프라인 latency 요약 (STT/Gemini/TTS/save/total 의 p50·p95·평균).
        운영 데이터라 debug 게이트(PALLY_DEBUG_ENDPOINTS=1) 뒤에 둔다.
        단일 프로세스 메모리 기준(최근 200 turn). 다중 인스턴스면 인스턴스별로만 집계됨.
        """
        turns = list(_TURN_METRICS)
        stages = ("stt_ms", "gemini_ms", "tts_ms", "feedback_ms", "save_ms", "total_ms")
        summary = {}
        for stage in stages:
            vals = [t[stage] for t in turns if t.get(stage) is not None]
            summary[stage] = {
                "p50": _pct(vals, 50),
                "p95": _pct(vals, 95),
                "avg": round(sum(vals) / len(vals)) if vals else None,
                "max": max(vals) if vals else None,
            }
        return {
            "count": len(turns),
            "stages": summary,
            "recent": turns[-20:],
        }


if _DEBUG_ENDPOINTS_ENABLED:
    # production(Railway)에는 PALLY_DEBUG_ENDPOINTS 미설정 → 이 route 자체가 등록되지 않음.
    @app.get("/api/debug-keys")
    def debug_keys():
        """서버가 로드한 API 키 확인용 (끝 4자리만 표시). 로컬 전용."""
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
    if "mp4" in ct or "m4a" in ct or "aac" in ct:
        return "MP3"  # iOS Safari MediaRecorder: audio/mp4 (AAC) → closest STT v1 encoding
    if "wav" in ct:
        return "LINEAR16"
    if "flac" in ct:
        return "FLAC"
    return "WEBM_OPUS"  # browser MediaRecorder 기본값 (Chrome/Firefox)


def _parse_wav(audio_bytes: bytes) -> tuple[bytes, int, int] | None:
    """
    WAV 파일 감지 및 파싱. RIFF 매직 바이트로 판별.
    반환: (raw_pcm_bytes, sample_rate, num_channels) 또는 None (WAV 아닌 경우)

    LINEAR16 인코딩은 raw PCM만 받음 — WAV 헤더를 포함해 보내면 헤더 바이트가
    오디오 데이터로 해석돼 빈 결과가 반환됨. 헤더를 파싱해 제거 후 전달해야 함.
    """
    if len(audio_bytes) < 44:
        return None
    if audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        return None
    num_channels = int.from_bytes(audio_bytes[22:24], "little")
    sample_rate = int.from_bytes(audio_bytes[24:28], "little")
    # Walk RIFF chunks to find 'data'
    offset = 12
    while offset + 8 <= len(audio_bytes):
        chunk_id = audio_bytes[offset : offset + 4]
        chunk_size = int.from_bytes(audio_bytes[offset + 4 : offset + 8], "little")
        if chunk_id == b"data":
            return audio_bytes[offset + 8 : offset + 8 + chunk_size], sample_rate, num_channels
        offset += 8 + chunk_size
    # Fallback: assume standard 44-byte header
    return audio_bytes[44:], sample_rate, num_channels


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

    # WAV 감지: RIFF 매직 바이트로 판별 (Content-Type보다 신뢰도 높음)
    wav_parsed = _parse_wav(audio_bytes)
    if wav_parsed:
        pcm_bytes, sample_rate, num_channels = wav_parsed
        encoding = "LINEAR16"
        audio_bytes = pcm_bytes  # WAV 헤더 제거 — raw PCM만 Google STT에 전달
        logging.info(
            f"STT WAV detected: sample_rate={sample_rate}, channels={num_channels}, "
            f"pcm_size={len(audio_bytes)} bytes"
        )
    else:
        encoding = _detect_encoding(audio.content_type or "")
        sample_rate = None
        num_channels = None
        logging.info(
            f"STT request: content_type={audio.content_type!r}, "
            f"size={len(audio_bytes)} bytes, encoding={encoding}"
        )

    # latest_short is optimized for <2s voice commands and returns empty for longer speech.
    # Use latest_long for WAV/LINEAR16 (browser recordings are typically 3-30s).
    model = "latest_long" if encoding == "LINEAR16" else "latest_short"
    config: dict = {
        "encoding": encoding,
        "languageCode": "en-US",
        "model": model,
        "enableAutomaticPunctuation": False,
    }
    if encoding == "LINEAR16" and sample_rate:
        config["sampleRateHertz"] = sample_rate
    if encoding == "WEBM_OPUS":
        config["sampleRateHertz"] = 48000
    if num_channels and num_channels > 1:
        config["audioChannelCount"] = num_channels

    payload = {
        "config": config,
        "audio": {"content": base64.b64encode(audio_bytes).decode()},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://speech.googleapis.com/v1/speech:recognize?key={GOOGLE_CLOUD_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        logging.error(
            f"Google STT failed: status={resp.status_code}, "
            f"content_type={audio.content_type!r}, size={len(audio_bytes)}, "
            f"encoding={encoding}, google_response={resp.text[:500]}"
        )
        raise HTTPException(status_code=502, detail=f"Google STT error: {resp.text}")

    results = resp.json().get("results", [])
    if not results:
        return {"transcript": "", "confidence": 0.0}

    alt = results[0].get("alternatives", [{}])[0]
    return {
        "transcript": alt.get("transcript", "").strip(),
        "confidence": alt.get("confidence", 1.0),
    }


# ── TTS — Google Cloud Text-to-Speech ────────────────────────────────────────


_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F"   # emoticons
    "\U0001F300-\U0001F5FF"   # symbols & pictographs
    "\U0001F680-\U0001F6FF"   # transport & map symbols
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


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
        _strip_emoji(req.text),
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
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash-lite:generateContent?key={GOOGLE_AI_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text}")

    parts = resp.json()["candidates"][0]["content"]["parts"]
    raw = " ".join(p["text"] for p in parts if not p.get("thought", False)).strip()
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
    raw_axes = _analyze_axes(req.utterance)

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
Keep your reply to ONE short sentence (about 10-15 words). Never write two sentences.

## Grammar correction rules
When the user makes grammar or vocabulary mistakes, do not list or explain the mistakes.
Instead, naturally recast the user's idea with the key corrected expression inside your reply.
If two errors are tightly connected in one phrase, you may fix both without explaining them.

Use this pattern:
1. React emotionally or empathetically first.
2. Rephrase the user's idea with the corrected expression.
3. Ask one short follow-up question.

Keep the spoken reply compact, usually 1-2 short sentences.
Keep the user's casual style when it is natural, such as "bestie", "hang out", "dying laughing", or "no way".
Do not over-correct slang or casual expressions unless they are actually wrong.

Example:
User: "My bestie and I watch it yesterday and we was dying laughing."
Pally: "Oh! You and your bestie watched it yesterday, and you were dying laughing? What was so funny?"

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
    for msg in (history or [])[-10:]:
        role = "user" if msg.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": utterance}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 512,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash-lite:generateContent?key={GOOGLE_AI_API_KEY}",
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini chat error {resp.status_code}: {resp.text}")

    candidate = resp.json()["candidates"][0]
    if candidate.get("finishReason") == "MAX_TOKENS":
        logging.warning("Gemini chat response cut off by MAX_TOKENS")

    # Skip thought parts (thinkingBudget=0이어도 방어적으로 필터)
    parts = candidate["content"]["parts"]
    reply = " ".join(p["text"] for p in parts if not p.get("thought", False)).strip()
    if not reply:
        raise RuntimeError("Gemini returned empty chat response")
    return shape_reply(reply)


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
            "maxOutputTokens": 512,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash-lite:generateContent?key={GOOGLE_AI_API_KEY}",
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini hint error {resp.status_code}: {resp.text}")
    parts = resp.json()["candidates"][0]["content"]["parts"]
    raw = " ".join(p["text"] for p in parts if not p.get("thought", False)).strip()
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
    raw_axes = _analyze_axes(req.utterance)

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
    # 답변 길이 정형화 (TTS·응답 모두 shaped 버전 사용)
    reply = shape_reply(reply)

    # 6. TTS — 이모지 제거 후 호출
    tts_result = await asyncio.gather(
        _call_google_tts(_strip_emoji(reply)),
        return_exceptions=True,
    )
    tts_audio = tts_result[0] if not isinstance(tts_result[0], Exception) else None

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
        "hint_ko": None,
    }


# ── Auth — Supabase JWT 검증 ──────────────────────────────────────────────────


def _verify_bearer_user(authorization: Optional[str]):
    """Authorization: Bearer <JWT> 를 Supabase Auth로 검증하고 user 객체 반환. 실패 시 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "unauthorized", "Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError(401, "unauthorized", "Missing or invalid Authorization header")

    if not _SUPABASE_ENABLED:
        raise AppError(503, "service_unavailable", "Supabase is not configured")

    try:
        user_res = get_supabase().auth.get_user(token)
    except Exception as e:
        # 연결 실패를 "토큰 만료"로 응답하면 클라이언트가 원인을 오판한다.
        # 전송 오류(죽은 커넥션 등)와 토큰 거절을 반드시 구분한다.
        if _is_transport_error(e):
            logging.warning(f"Auth transport error, retrying with fresh client: {e}")
            _reset_supabase_client()
            try:
                user_res = get_supabase().auth.get_user(token)
            except Exception as retry_e:
                logging.error(f"Auth service unreachable after retry: {retry_e}")
                raise AppError(503, "auth_unavailable",
                               "인증 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.")
        else:
            status = getattr(e, "status", None)
            if isinstance(status, int) and status >= 500:
                logging.error(f"Auth service error {status}: {e}")
                raise AppError(503, "auth_unavailable",
                               "인증 서버에 일시적인 문제가 있어요. 잠시 후 다시 시도해 주세요.")
            # 인증 서버가 토큰을 명시적으로 거절한 경우만 401.
            logging.warning(f"Token rejected by auth service: {e}")
            raise AppError(401, "unauthorized", "Invalid or expired token")

    user = getattr(user_res, "user", None)
    if user is None or not getattr(user, "id", None):
        raise AppError(401, "unauthorized", "Invalid or expired token")

    return user


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """user_id(uuid)만 반환. user_id는 토큰에서만 추출하고 body 값을 신뢰하지 않는다."""
    return _verify_bearer_user(authorization).id


def get_current_user(authorization: Optional[str] = Header(None)):
    """검증된 user 객체 반환 (id + user_metadata). 프로필 사진 등 메타데이터가 필요할 때."""
    return _verify_bearer_user(authorization)


# OAuth provider 별로 프사 URL 이 들어가는 메타데이터 키가 달라(구글=avatar_url/picture,
# 카카오=케이스별로 다름) 후보 키를 순서대로 확인해 하나로 정규화한다.
# 정확한 카카오 키는 실제 카카오 로그인 유저로 확인 필요(실측 전 후보만 나열).
_AVATAR_KEYS = ("profile_image_url", "avatar_url", "picture", "profile_image")
_GOOGLE_AVATAR_SIZE = 512


def _normalize_avatar_url(value: str) -> str:
    """Google OAuth 사진은 Retina UI에서도 선명하도록 512px 정사각형을 요청한다."""
    try:
        parts = urlsplit(value)
    except ValueError:
        return value

    hostname = (parts.hostname or "").lower()
    if hostname != "googleusercontent.com" and not hostname.endswith(".googleusercontent.com"):
        return value

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "sz" in query:
        query["sz"] = str(_GOOGLE_AVATAR_SIZE)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    sized_path = re.sub(r"=s\d+(?:-c)?$", "", parts.path)
    sized_path = f"{sized_path}=s{_GOOGLE_AVATAR_SIZE}-c"
    return urlunsplit((parts.scheme, parts.netloc, sized_path, parts.query, parts.fragment))


def _extract_avatar(user) -> Optional[str]:
    meta = getattr(user, "user_metadata", None) or {}
    if not isinstance(meta, dict):
        return None

    # Kakao profile_image_url 은 480~640px, thumbnail_image_url 은 100~110px다.
    # 중첩된 고해상도 원본을 일반 avatar_url 후보보다 먼저 사용한다.
    ka = meta.get("kakao_account")
    if isinstance(ka, dict):
        prof = ka.get("profile")
        if isinstance(prof, dict):
            v = prof.get("profile_image_url")
            if isinstance(v, str) and v.strip():
                return v

    for k in _AVATAR_KEYS:
        v = meta.get(k)
        if isinstance(v, str) and v.strip():
            return _normalize_avatar_url(v)

    # 고해상도 원본이 없을 때만 Kakao thumbnail 을 마지막 후보로 사용한다.
    if isinstance(ka, dict):
        prof = ka.get("profile")
        if isinstance(prof, dict):
            v = prof.get("thumbnail_image_url")
            if isinstance(v, str) and v.strip():
                return v
    return None


def require_idempotency_key(idempotency_key: str = Header(..., alias="Idempotency-Key")) -> str:
    """
    비용·데이터 생성 POST용 멱등 키. 계약상 필수 헤더.
    이번 slice에서는 헤더 존재만 강제하고(누락 시 422), 24h replay store는 미구현.
    실제 중복 방지는 각 엔드포인트의 상태 충돌(409)로 처리한다.
    """
    key = (idempotency_key or "").strip()
    if not key:
        raise AppError(422, "validation_error", "Idempotency-Key header is required")
    return key


# ── Onboarding & Profile — profiles 테이블 (service_role 쓰기 전용) ───────────

_VALID_ENGLISH_LEVELS = {"A2", "B1", "B2", "C1"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_display_name(value: str) -> str:
    name = (value or "").strip()
    if not (1 <= len(name) <= 30):
        raise AppError(422, "validation_error", "display_name must be 1-30 characters after trimming")
    return name


def _validate_english_level(value: str) -> str:
    if value not in _VALID_ENGLISH_LEVELS:
        raise AppError(422, "validation_error", f"english_level must be one of {sorted(_VALID_ENGLISH_LEVELS)}")
    return value


class OnboardingRequest(BaseModel):
    # extra=forbid → 알 수 없는 필드(traits 등)는 422 validation_error.
    model_config = ConfigDict(extra="forbid")
    display_name: str
    english_level: str


class ProfilePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Optional[str] = None
    english_level: Optional[str] = None


class ProfileAvatarResponse(BaseModel):
    avatar_url: Optional[str] = None


def _profile_to_response(row: dict, avatar_url: Optional[str] = None) -> dict:
    # 계약: snake_case UserProfile. traits는 DB seed 5개(생성 로직은 후속).
    # avatar_url 은 DB 가 아니라 OAuth 메타데이터(구글/카카오)에서 정규화해 넣는다.
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "english_level": row["english_level"],
        "onboarding_completed": row["onboarding_completed"],
        "traits": row.get("traits"),
        "avatar_url": avatar_url,
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


@app.post("/api/onboarding")
async def onboarding(
    req: OnboardingRequest,
    user=Depends(get_current_user),
    _idem: str = Depends(require_idempotency_key),
):
    """최초 프로필 생성. 이미 온보딩 완료한 사용자는 409 conflict (덮어쓰지 않음)."""
    user_id = user.id
    display_name = _validate_display_name(req.display_name)
    english_level = _validate_english_level(req.english_level)

    sb = get_supabase()

    # 이미 온보딩 완료 여부 확인 (덮어쓰기 방지).
    try:
        existing = sb.table("profiles").select("onboarding_completed").eq("id", user_id).execute()
    except Exception as e:
        logging.error(f"Onboarding existence check failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read profile")

    if existing.data and existing.data[0].get("onboarding_completed"):
        raise AppError(409, "conflict", "Onboarding already completed. Use PATCH /api/profile to edit.")

    try:
        res = sb.table("profiles").upsert({
            "id": user_id,
            "display_name": display_name,
            "english_level": english_level,
            "onboarding_completed": True,
            "updated_at": _now_iso(),
        }).execute()
    except Exception as e:
        logging.error(f"Onboarding upsert failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to save profile")

    if not res.data:
        raise AppError(503, "persistence_failed", "Failed to save profile")

    return {"profile": _profile_to_response(res.data[0], _extract_avatar(user))}


@app.get("/api/profile/avatar", response_model=ProfileAvatarResponse)
async def get_profile_avatar(user=Depends(get_current_user)):
    """OAuth 프로필 사진 조회. profiles 행이 없는 온보딩 전에도 사용할 수 있다."""
    return ProfileAvatarResponse(avatar_url=_extract_avatar(user))


@app.get("/api/profile")
async def get_profile(user=Depends(get_current_user)):
    """본인 profile 조회. 온보딩 전(row 없음)이면 404 profile_not_found. avatar_url 포함(OAuth)."""
    user_id = user.id
    sb = get_supabase()
    try:
        res = sb.table("profiles").select("*").eq("id", user_id).execute()
    except Exception as e:
        logging.error(f"Profile fetch failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to fetch profile")

    if not res.data:
        raise AppError(404, "profile_not_found", "Profile not found. Complete onboarding first.")

    return {"profile": _profile_to_response(res.data[0], _extract_avatar(user))}


@app.patch("/api/profile")
async def update_profile(
    req: ProfilePatchRequest,
    user=Depends(get_current_user),
):
    """본인 profile 부분 수정. traits 등 unknown 필드는 422 (extra=forbid)."""
    user_id = user.id
    update_fields: Dict[str, object] = {}

    if req.display_name is not None:
        update_fields["display_name"] = _validate_display_name(req.display_name)
    if req.english_level is not None:
        update_fields["english_level"] = _validate_english_level(req.english_level)

    if not update_fields:
        raise AppError(422, "validation_error", "At least one field (display_name or english_level) is required")

    update_fields["updated_at"] = _now_iso()

    sb = get_supabase()
    try:
        res = sb.table("profiles").update(update_fields).eq("id", user_id).execute()
    except Exception as e:
        logging.error(f"Profile update failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to update profile")

    if not res.data:
        raise AppError(404, "profile_not_found", "Profile not found. Complete onboarding first.")

    return {"profile": _profile_to_response(res.data[0], _extract_avatar(user))}


# ── Conversations & Turns — 3주차 음성 대화 (sessions/messages 재사용) ────────
#
# 경계: STT/Gemini/TTS 파이프라인 자체는 AI 영역. 여기서는 그 어댑터를 "호출"만 하고
# (기존 _call_gemini_chat / _call_google_tts, 신규 _stt_from_bytes),
# 백엔드는 conversation/turn 저장 + 소유권 + 실패/완료 구분 + 중복방지(dedup)만 담당한다.


async def _stt_from_bytes(audio_bytes: bytes, content_type: str) -> tuple[str, float]:
    """
    오디오 bytes → (transcript, confidence). turn 처리 전용 STT 어댑터 호출부.
    무음/인식실패 → ("", 0.0). Google API 비-200 → RuntimeError.
    (기존 /api/stt 는 건드리지 않고, turn 용으로 동일 파이프라인을 별도 호출한다.)
    """
    wav_parsed = _parse_wav(audio_bytes)
    if wav_parsed:
        pcm_bytes, sample_rate, num_channels = wav_parsed
        encoding = "LINEAR16"
        audio_bytes = pcm_bytes
    else:
        encoding = _detect_encoding(content_type or "")
        sample_rate = None
        num_channels = None

    model = "latest_long" if encoding == "LINEAR16" else "latest_short"
    config: dict = {
        "encoding": encoding,
        "languageCode": "en-US",
        "model": model,
        "enableAutomaticPunctuation": False,
    }
    if encoding == "LINEAR16" and sample_rate:
        config["sampleRateHertz"] = sample_rate
    if encoding == "WEBM_OPUS":
        config["sampleRateHertz"] = 48000
    if num_channels and num_channels > 1:
        config["audioChannelCount"] = num_channels

    payload = {"config": config, "audio": {"content": base64.b64encode(audio_bytes).decode()}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://speech.googleapis.com/v1/speech:recognize?key={GOOGLE_CLOUD_API_KEY}",
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Google STT error {resp.status_code}: {resp.text[:300]}")

    results = resp.json().get("results", [])
    if not results:
        return "", 0.0
    alt = results[0].get("alternatives", [{}])[0]
    return alt.get("transcript", "").strip(), alt.get("confidence", 1.0)


_INITIAL_AXES = {"Formality": 50, "Energy": 50, "Intimacy": 50, "Humor": 50, "Curiosity": 50}


def _conversation_to_response(row: dict) -> dict:
    # 계약 §4.5 Conversation 모양. 생성 시점 기준 기본값(turn 없음).
    return {
        "id": row["id"],
        "status": "completed" if row.get("ended_at") else "active",
        "title": None,
        "started_at": row["created_at"],
        "last_turn_at": None,
        "completed_at": row.get("ended_at"),
        "turn_count": 0,
        "current_axes": dict(_INITIAL_AXES),
    }


@app.post("/api/conversations", status_code=201)
async def create_conversation(
    user_id: str = Depends(get_current_user_id),
    _idem: str = Depends(require_idempotency_key),
):
    """새 대화 생성. 사용자 레벨은 profile 에서 읽는다 (없으면 기본 B1)."""
    sb = get_supabase()

    level = "B1"
    try:
        prof = sb.table("profiles").select("english_level").eq("id", user_id).execute()
    except Exception as e:
        logging.error(f"create_conversation profile read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read profile")
    if prof.data:
        level = prof.data[0]["english_level"]

    try:
        res = sb.table("sessions").insert({
            "character_name": "Pally",
            "level": level,
            "user_id": user_id,
        }).execute()
    except Exception as e:
        logging.error(f"create_conversation insert failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to create conversation")

    if not res.data:
        raise AppError(503, "persistence_failed", "Failed to create conversation")

    return {"conversation": _conversation_to_response(res.data[0])}


def _paired_reply(sb, session_id: str, user_created_at: str) -> str:
    """dedup 재반환용: 해당 user turn 뒤에 저장된 pally 응답 텍스트를 찾는다."""
    r = (
        sb.table("messages")
        .select("transcript")
        .eq("session_id", session_id)
        .eq("role", "pally")
        .gte("created_at", user_created_at)
        .order("created_at")
        .limit(1)
        .execute()
    )
    return r.data[0]["transcript"] if r.data else ""


async def _gen_feedback(utterance: str, reply: str, level: str) -> list:
    """
    AI feedback 생성 호출 래퍼 (경계: 생성 로직은 AI, 여기선 호출·형태만).
    - 미제공(generate_feedback is None) → [] 반환 (실패 아님, 미구현).
    - 동기 함수라 asyncio.to_thread 로 offload (이벤트 루프 안 막음) + 10s 타임아웃.
    - 예외/타임아웃은 그대로 raise → 호출부(gather)가 partial + feedback_failed 로 처리.
    - id 는 계약(§5)상 BE 가 부여. AI 는 {original, corrected, explanation_ko} 만 준다.
    """
    if generate_feedback is None:
        return []
    # 계약: (items, failed). failed=True 는 생성 실패/폴백 → 빈 items 를 "교정 없음"으로
    # 보지 말라는 뜻이므로 raise 해서 호출부(gather)가 partial + feedback_failed 로 처리.
    items, failed = await asyncio.wait_for(
        asyncio.to_thread(generate_feedback, utterance, reply, level),
        timeout=10,
    )
    if failed:
        raise RuntimeError("feedback generation degraded (failed flag)")
    out = []
    for it in (items or []):
        out.append({
            "id": str(uuid.uuid4()),
            "original": it.get("original", ""),
            "corrected": it.get("corrected", ""),
            "explanation_ko": it.get("explanation_ko", ""),
        })
    return out


# ── Quota — 무료 일일 사용량 (KST bucket + 원자적 차감) ───────────────────────


def _kst_date() -> str:
    """오늘의 KST 날짜 (YYYY-MM-DD). 사용량 bucket 키."""
    return datetime.now(_KST).date().isoformat()


def _kst_reset_at() -> str:
    """다음 KST 자정(=오늘 사용량 리셋 시각)을 UTC ISO 로."""
    tomorrow = datetime.now(_KST).date() + timedelta(days=1)
    midnight_kst = datetime.combine(tomorrow, dtime.min, tzinfo=_KST)
    return midnight_kst.astimezone(timezone.utc).isoformat()


def _reserve_turn(sb, user_id: str) -> int:
    """
    turn 1개를 원자적으로 예약(차감). 반환: 예약 후 used_turns(>=1), 소진이면 -1.
    DB 함수(reserve_turn)가 행 잠금으로 동시성 race 를 막는다.
    """
    try:
        res = sb.rpc("reserve_turn", {
            "p_user_id": user_id,
            "p_date": _kst_date(),
            "p_limit": FREE_DAILY_TURNS,
        }).execute()
    except Exception as e:
        logging.error(f"reserve_turn failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to reserve quota")
    used = res.data
    if isinstance(used, list):  # 방어적: 배열로 오면 첫 값
        used = used[0] if used else None
    if used is None:
        raise AppError(503, "persistence_failed", "Quota reservation returned no result")
    return int(used)


def _release_turn(sb, user_id: str) -> None:
    """예약한 turn 을 롤백(환불). turn 이 실패했을 때만 호출. 실패해도 turn 흐름은 안 막음."""
    try:
        sb.rpc("release_turn", {"p_user_id": user_id, "p_date": _kst_date()}).execute()
    except Exception as e:
        logging.warning(f"release_turn failed (non-fatal): {e}")


@app.get("/api/usage")
async def get_usage(user_id: str = Depends(get_current_user_id)):
    """당일 무료 사용량 조회 (§4.11). 현재는 전원 free plan."""
    sb = get_supabase()
    date_kst = _kst_date()
    try:
        res = sb.table("usage_daily").select("used_turns").eq("user_id", user_id).eq("date_kst", date_kst).execute()
    except Exception as e:
        logging.error(f"get_usage failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read usage")
    used = res.data[0]["used_turns"] if res.data else 0
    return {
        "plan": "free",
        "date": date_kst,
        "timezone": "Asia/Seoul",
        "used_turns": used,
        "remaining_turns": max(FREE_DAILY_TURNS - used, 0),
        "daily_limit": FREE_DAILY_TURNS,
        "reset_at": _kst_reset_at(),
    }


# ── Activity events — Achievements Daily Task 측정용 사실 이벤트 기록 ─────────

_ALLOWED_EVENT_TYPES = {
    "app_session_started",
    "conversation_detail_opened",
    "transcript_expanded",
    "feedback_item_opened",
    "achievements_opened",
    "profile_opened",
}


class ActivityEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    event_type: str
    occurred_at: Optional[str] = None
    conversation_id: Optional[str] = None
    feedback_item_id: Optional[str] = None


@app.post("/api/activity-events", status_code=202)
async def record_activity_event(
    req: ActivityEventRequest,
    user_id: str = Depends(get_current_user_id),
    _idem: str = Depends(require_idempotency_key),
):
    """
    화면 진입·열람형 이벤트 기록 (§4.20). 완료 평가는 하지 않고 "사실 이벤트"만 저장.
    - event_type 은 허용된 6종만 (422)
    - occurred_at 은 서버 시각 ±5분만 허용 (422). task 날짜는 서버 수신 시각 기준
    - resource(conversation_id) 있으면 소유권 검증 (타인 것 404)
    - (user_id, event_id) 유일 → 재전송은 중복 저장 없이 동일 응답 (멱등)
    """
    if req.event_type not in _ALLOWED_EVENT_TYPES:
        raise AppError(422, "validation_error", f"event_type must be one of {sorted(_ALLOWED_EVENT_TYPES)}")
    if not (req.event_id or "").strip():
        raise AppError(422, "validation_error", "event_id is required")

    if req.occurred_at:
        try:
            occ = datetime.fromisoformat(req.occurred_at.replace("Z", "+00:00"))
        except ValueError:
            raise AppError(422, "validation_error", "occurred_at must be ISO 8601")
        if occ.tzinfo is None:
            occ = occ.replace(tzinfo=timezone.utc)
        drift = abs((datetime.now(timezone.utc) - occ).total_seconds())
        if drift > 300:
            raise AppError(422, "validation_error", "occurred_at is too far from server time (>5min)")

    sb = get_supabase()

    # resource 소유권 (있을 때만) — 타인 conversation 은 404
    if req.conversation_id:
        _owned_session(sb, req.conversation_id, user_id)

    # insert-or-ignore: (user_id, event_id) 중복이면 조용히 무시 → 멱등
    try:
        sb.table("activity_events").upsert(
            {
                "user_id": user_id,
                "event_id": req.event_id,
                "event_type": req.event_type,
                "occurred_at": req.occurred_at,
                "conversation_id": req.conversation_id,
                "feedback_item_id": req.feedback_item_id,
            },
            on_conflict="user_id,event_id",
            ignore_duplicates=True,
        ).execute()
    except Exception as e:
        logging.error(f"activity event insert failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to record event")

    return {"recorded": True}


def _is_unique_violation(e: Exception) -> bool:
    """messages 멱등 unique index 위반인지 (동시 중복 요청의 진 쪽)."""
    s = str(e).lower()
    return "23505" in s or "duplicate key" in s or "messages_session_idem" in s


def _replayed_turn(sb, conversation_id: str, u: dict) -> dict:
    """이미 저장된 turn(user 행 u)을 replayed 응답으로. dedup·동시중복 진 쪽 공용.
    feedback_pending: 저장된 feedback 이 null(생성 실패/미완)인지 → [] (교정 없음) 와 구분."""
    return {
        "conversation_id": conversation_id,
        "turn_id": u["id"],
        "status": "completed",
        "replayed": True,
        "created_at": u["created_at"],
        "user": {"transcript": u["transcript"]},
        "pally": {"text": _paired_reply(sb, conversation_id, u["created_at"]), "audio": None},
        "axes": u.get("axes"),
        "character": u.get("character"),
        "feedback": u.get("feedback") or [],
        "feedback_pending": u.get("feedback") is None,
        "warnings": [],
    }


@app.post("/api/conversations/{conversation_id}/turns", status_code=201)
async def create_turn(
    conversation_id: str,
    request: Request,
    audio: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    idem_key: str = Depends(require_idempotency_key),
):
    """
    음성 turn 1개 처리: 오디오 → STT → 5축/EMA → Gemini 답변 → TTS → 저장.
    - 소유권: 본인 conversation 이 아니면 404.
    - 실패/완료 구분: STT 무음/실패는 저장하지 않고 명시적 에러(빈 데이터로 숨기지 않음).
    - 중복방지: 같은 conversation·같은 Idempotency-Key 재시도는 외부 재호출 없이 저장된 turn 재반환.
    - 관측성: STT/Gemini/TTS/save 단계별 latency 를 측정해 로그 + /api/metrics 에 노출.
    """
    if not GOOGLE_CLOUD_API_KEY or not GOOGLE_AI_API_KEY:
        raise AppError(503, "service_unavailable", "Speech/AI provider not configured")

    turn_t0 = time.perf_counter()

    sb = get_supabase()

    # 1. conversation 소유권 (타인 소유는 존재 숨김 → 404)
    try:
        sess = sb.table("sessions").select("id, character_name, level, user_id, ended_at").eq("id", conversation_id).execute()
    except Exception as e:
        logging.error(f"turn session read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read conversation")
    if not sess.data or sess.data[0].get("user_id") != user_id:
        raise AppError(404, "not_found", "Conversation not found")
    session = sess.data[0]
    if session.get("ended_at"):
        raise AppError(409, "conversation_closed", "Conversation is already completed")

    # 2. dedup — 같은 (conversation, idem_key) user turn 이 이미 있으면 재반환
    try:
        dup = sb.table("messages").select("*").eq("session_id", conversation_id).eq("idempotency_key", idem_key).execute()
    except Exception as e:
        logging.error(f"turn dedup read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to check idempotency")
    if dup.data:
        return _replayed_turn(sb, conversation_id, dup.data[0])

    # 3. 오디오
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise AppError(400, "invalid_audio", "Empty audio file")

    # 3.5. quota 원자적 예약 — AI 부르기 전에 차단 (초과면 여기서 429, 외부 호출 0).
    #      아래에서 turn 이 실패하면 _release_turn 으로 롤백해 차감을 취소한다.
    quota_used = _reserve_turn(sb, user_id)
    if quota_used < 0:
        raise AppError(429, "quota_exceeded", "오늘 사용할 수 있는 대화를 모두 사용했어요.",
                       {"reset_at": _kst_reset_at(), "daily_limit": FREE_DAILY_TURNS})

    # 4. STT (실패는 저장하지 않고 명시적 에러 + quota 롤백) — latency 측정
    stt_t0 = time.perf_counter()
    try:
        transcript, _conf = await _stt_from_bytes(audio_bytes, audio.content_type or "")
    except Exception as e:
        logging.warning(f"turn STT failed: {e}")
        _release_turn(sb, user_id)
        raise AppError(502, "stt_failed", "Speech recognition failed")
    stt_ms = round((time.perf_counter() - stt_t0) * 1000)
    if not transcript:
        _release_turn(sb, user_id)
        raise AppError(422, "speech_not_recognized", "No recognizable speech in audio")

    # 5. 이전 이력 + 누적 axes 로드
    try:
        prior = sb.table("messages").select("role, transcript, axes, created_at").eq("session_id", conversation_id).order("created_at").execute()
    except Exception as e:
        logging.error(f"turn history read failed: {e}")
        _release_turn(sb, user_id)
        raise AppError(503, "persistence_failed", "Failed to load history")
    prior_rows = prior.data or []
    history = [ChatMessage(role=m["role"], content=m["transcript"]) for m in prior_rows]
    current_axes = None
    for m in reversed(prior_rows):
        if m["role"] == "user" and m.get("axes"):
            current_axes = m["axes"]
            break

    # 6. 5축 → EMA → character (분석 어댑터: rule|ml|hybrid, 기본 rule)
    raw_axes = _analyze_axes(transcript)
    smoothed = apply_ema(current_axes, raw_axes) if current_axes else raw_axes
    character = compute_character(smoothed)

    # 7. Gemini 답변 (기존 함수 호출; 실패 시 silent fallback 없이 명시적 실패) — latency 측정
    gemini_t0 = time.perf_counter()
    try:
        reply = await _call_gemini_chat(transcript, history, session["character_name"], session["level"])
    except Exception as e:
        logging.warning(f"turn Gemini failed: {e}")
        _release_turn(sb, user_id)
        raise AppError(502, "ai_engine_failed", "Reply generation failed")
    gemini_ms = round((time.perf_counter() - gemini_t0) * 1000)
    # 답변 길이 정형화: 이후 TTS·저장·응답이 모두 shaped 버전을 써서 화면/음성 불일치 방지.
    reply = shape_reply(reply)

    # 8. TTS + feedback 병렬 (둘 다 reply 만 있으면 됨 → asyncio.gather).
    #    feedback 은 AI 담당(동기 함수)이라 to_thread 로 offload 해 이벤트 루프를 막지 않는다.
    #    TTS 가 보통 long pole 이라, feedback 을 병렬로 붙여도 turn latency 는 거의 안 늘어난다.
    timings: Dict[str, int] = {}

    async def _timed_tts():
        t0 = time.perf_counter()
        try:
            return await _call_google_tts(_strip_emoji(reply))
        finally:
            timings["tts_ms"] = round((time.perf_counter() - t0) * 1000)

    async def _timed_feedback():
        t0 = time.perf_counter()
        try:
            return await _gen_feedback(transcript, reply, session["level"])
        finally:
            timings["feedback_ms"] = round((time.perf_counter() - t0) * 1000)

    tts_result, fb_result = await asyncio.gather(
        _timed_tts(), _timed_feedback(), return_exceptions=True,
    )
    tts_ms = timings.get("tts_ms", 0)
    feedback_ms = timings.get("feedback_ms", 0)

    # TTS: 실패해도 turn 은 완료, audio 만 null.
    tts_audio: Optional[str] = None
    if isinstance(tts_result, Exception):
        logging.warning(f"turn TTS failed (non-fatal): {tts_result}")
    else:
        tts_audio = tts_result

    # feedback: 성공(list) / 실패(Exception → partial+warning) / 미구현(None 반환 → [])
    feedback_items: list = []
    feedback_failed = False
    if isinstance(fb_result, Exception):
        feedback_failed = True
        logging.warning(f"turn feedback failed (non-fatal): {fb_result}")
    elif fb_result:
        feedback_items = fb_result
    # 저장은 실패/무교정을 구분: 실패 → null(History 재생성 대상), 성공 → list([] 는 "교정 없음").
    feedback_to_store = None if feedback_failed else feedback_items

    # 9. 저장 — user 행에만 idem_key (unique index 로 중복 저장 차단) — latency 측정
    save_t0 = time.perf_counter()
    try:
        save = sb.table("messages").insert([
            {
                "session_id": conversation_id,
                "role": "user",
                "transcript": transcript,
                "axes": smoothed,
                "character": character,
                "idempotency_key": idem_key,
                "feedback": feedback_to_store,
            },
            {
                "session_id": conversation_id,
                "role": "pally",
                "transcript": reply,
                "axes": None,
                "character": character,
            },
        ]).execute()
    except Exception as e:
        if _is_unique_violation(e):
            # 동시 중복 요청의 진 쪽: 이긴 요청이 이미 저장함 → 내 예약분 환불 후 저장된 turn 재반환.
            # (503 을 주던 기존 동작 대신 replayed 로 정상 결과 반환)
            _release_turn(sb, user_id)
            try:
                ex = sb.table("messages").select("*").eq("session_id", conversation_id).eq("idempotency_key", idem_key).execute()
            except Exception:
                ex = None
            if ex and ex.data:
                return _replayed_turn(sb, conversation_id, ex.data[0])
            raise AppError(409, "duplicate_turn", "Duplicate turn already being processed")
        logging.error(f"turn save failed: {e}")
        _release_turn(sb, user_id)
        raise AppError(503, "persistence_failed", "Failed to save turn")
    save_ms = round((time.perf_counter() - save_t0) * 1000)

    # turn 식별: user 행이 곧 turn. turn_id/created_at 을 저장 결과에서 가져온다.
    user_row = next((r for r in (save.data or []) if r.get("role") == "user"), None)
    turn_id = user_row["id"] if user_row else None
    turn_created = user_row["created_at"] if user_row else None

    # TTS·feedback 부가 실패는 partial + warnings (계약 §4.6). 대화 텍스트는 정상.
    status = "completed"
    warnings: list = []
    if tts_audio is None:
        status = "partial"
        warnings.append({
            "code": "tts_failed",
            "message": "음성 생성에 실패했어요. 텍스트로 계속할 수 있어요.",
        })
    if feedback_failed:
        status = "partial"
        warnings.append({
            "code": "feedback_failed",
            "message": "피드백 생성에 실패했어요. 대화는 계속할 수 있어요.",
        })

    # 관측성: 단계별 latency 를 링버퍼에 저장 + 구조화 로그로 emit.
    metric = {
        "request_id": getattr(request.state, "request_id", None),
        "ts": _now_iso(),
        "conversation_id": conversation_id,
        "transcript_chars": len(transcript),
        "stt_ms": stt_ms,
        "gemini_ms": gemini_ms,
        "tts_ms": tts_ms,
        "feedback_ms": feedback_ms,
        "save_ms": save_ms,
        "total_ms": round((time.perf_counter() - turn_t0) * 1000),
        "status": status,
    }
    _TURN_METRICS.append(metric)
    _log_event("turn_metrics", **metric)

    return {
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "status": status,
        "replayed": False,
        "created_at": turn_created,
        "user": {"transcript": transcript},
        "pally": {"text": reply, "audio": tts_audio},  # audio = base64 inline (signed URL 미구현)
        "axes": smoothed,
        "character": character,
        "feedback": feedback_items,
        "feedback_pending": feedback_failed,
        "warnings": warnings,
        "quota": {
            "used_turns": quota_used,
            "remaining_turns": max(FREE_DAILY_TURNS - quota_used, 0),
            "daily_limit": FREE_DAILY_TURNS,
            "exhausted": quota_used >= FREE_DAILY_TURNS,
            "resets_at": _kst_reset_at(),
        },
    }


# ── History & Detail & Complete & Reopen — 4주차 ─────────────────────────────


def _truncate(text: str, n: int) -> Optional[str]:
    t = " ".join((text or "").split())
    return t[:n] if t else None


def _owned_session(sb, conversation_id: str, user_id: str) -> dict:
    """conversation 소유권 확인. 없거나 타인 소유면 404 (존재 숨김)."""
    try:
        res = sb.table("sessions").select("*").eq("id", conversation_id).execute()
    except Exception as e:
        logging.error(f"session read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read conversation")
    if not res.data or res.data[0].get("user_id") != user_id:
        raise AppError(404, "not_found", "Conversation not found")
    return res.data[0]


def _latest_user_axes(messages: list) -> dict:
    """Return the most recent persisted user axes, or the initial shape when no turn exists."""
    for message in reversed(messages):
        if message["role"] == "user" and message.get("axes"):
            return message["axes"]
    return dict(_INITIAL_AXES)


@app.get("/api/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_user_id),
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    status: Optional[str] = Query(None),
):
    """History 목록. 최근 생성순, cursor(created_at) 기반 pagination, 본인 것만."""
    sb = get_supabase()
    q = sb.table("sessions").select("*").eq("user_id", user_id)
    if status == "active":
        q = q.is_("ended_at", "null")
    elif status == "completed":
        q = q.not_.is_("ended_at", "null")
    if cursor:
        q = q.lt("created_at", cursor)
    q = q.order("created_at", desc=True).limit(limit)
    try:
        sess = q.execute()
    except Exception as e:
        logging.error(f"list_conversations failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to list conversations")

    rows = sess.data or []
    ids = [s["id"] for s in rows]
    msgs_by_session: Dict[str, list] = {sid: [] for sid in ids}
    if ids:
        try:
            msgs = sb.table("messages").select("session_id, role, transcript, axes, feedback, created_at").in_("session_id", ids).order("created_at").execute()
        except Exception as e:
            logging.error(f"list_conversations messages failed: {e}")
            raise AppError(503, "persistence_failed", "Failed to load conversation summaries")
        for m in (msgs.data or []):
            msgs_by_session.setdefault(m["session_id"], []).append(m)

    items = []
    for s in rows:
        ms = msgs_by_session.get(s["id"], [])
        user_msgs = [m for m in ms if m["role"] == "user"]
        items.append({
            "id": s["id"],
            "status": "completed" if s.get("ended_at") else "active",
            "title": _truncate(user_msgs[0]["transcript"], 60) if user_msgs else None,
            "started_at": s["created_at"],
            "last_turn_at": ms[-1]["created_at"] if ms else None,
            "completed_at": s.get("ended_at"),
            "turn_count": len(user_msgs),
            "current_axes": _latest_user_axes(ms),
            "feedback_count": sum(len(m.get("feedback") or []) for m in user_msgs),
            "preview": _truncate(user_msgs[-1]["transcript"], 120) if user_msgs else None,
        })

    next_cursor = rows[-1]["created_at"] if len(rows) == limit else None
    return {"items": items, "next_cursor": next_cursor}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
):
    """대화 상세: conversation + turns(각 turn 의 feedback 포함). 본인 것만."""
    sb = get_supabase()
    session = _owned_session(sb, conversation_id, user_id)

    q = sb.table("messages").select("id, role, transcript, feedback, axes, created_at").eq("session_id", conversation_id)
    if cursor:
        q = q.gt("created_at", cursor)
    try:
        msgs = q.order("created_at").execute()
    except Exception as e:
        logging.error(f"get_conversation messages failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to load turns")
    ms = msgs.data or []
    turns = _conversation_turns(ms)

    page = turns[:limit]
    next_cursor = page[-1]["created_at"] if len(turns) > limit else None

    user_msgs = [m for m in ms if m["role"] == "user"]
    conv = {
        "id": session["id"],
        "status": "completed" if session.get("ended_at") else "active",
        "title": _truncate(user_msgs[0]["transcript"], 60) if user_msgs else None,
        "started_at": session["created_at"],
        "last_turn_at": ms[-1]["created_at"] if ms else None,
        "completed_at": session.get("ended_at"),
        "reopened_at": session.get("reopened_at"),
        "reopen_count": session.get("reopen_count", 0),
        "turn_count": len(user_msgs),
        "current_axes": _latest_user_axes(ms),
    }
    return {"conversation": conv, "turns": page, "next_cursor": next_cursor}


def _conversation_turns(messages: list[dict]) -> list[dict]:
    """Build user→pally turns even when equal timestamps arrive out of order."""
    role_order = {"user": 0, "pally": 1}
    ordered = sorted(
        messages,
        key=lambda message: (
            message["created_at"],
            role_order[message["role"]],
            message["id"],
        ),
    )

    # user→pally 쌍으로 turn 구성. turn_id = user 메시지 id.
    turns = []
    seq = 0
    pending_user = None
    for m in ordered:
        if m["role"] == "user":
            if pending_user is not None:
                seq += 1
                turns.append(_turn_detail(pending_user, None, seq))
            pending_user = m
        else:
            seq += 1
            turns.append(_turn_detail(pending_user, m, seq))
            pending_user = None
    if pending_user is not None:
        seq += 1
        turns.append(_turn_detail(pending_user, None, seq))
    return turns


def _turn_detail(user_msg: Optional[dict], pally_msg: Optional[dict], seq: int) -> dict:
    return {
        "id": user_msg["id"] if user_msg else (pally_msg["id"] if pally_msg else None),
        "sequence": seq,
        "status": "completed",
        "user_transcript": user_msg["transcript"] if user_msg else None,
        "pally_text": pally_msg["transcript"] if pally_msg else None,
        "feedback": (user_msg.get("feedback") if user_msg else None) or [],
        "feedback_pending": (user_msg.get("feedback") is None) if user_msg else False,
        "created_at": (user_msg or pally_msg)["created_at"],
    }


@app.post("/api/conversations/{conversation_id}/complete")
async def complete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    _idem: str = Depends(require_idempotency_key),
):
    """대화 종료. 재호출해도 같은 결과(멱등)."""
    sb = get_supabase()
    session = _owned_session(sb, conversation_id, user_id)

    if not session.get("ended_at"):
        try:
            res = sb.table("sessions").update({"ended_at": _now_iso()}).eq("id", conversation_id).eq("user_id", user_id).execute()
        except Exception as e:
            logging.error(f"complete_conversation failed: {e}")
            raise AppError(503, "persistence_failed", "Failed to complete conversation")
        session = res.data[0] if res.data else session

    return {"conversation": {
        "id": session["id"],
        "status": "completed",
        "completed_at": session.get("ended_at"),
    }}


@app.post("/api/conversations/{conversation_id}/reopen")
async def reopen_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    _idem: str = Depends(require_idempotency_key),
):
    """완료된 대화를 같은 id 로 재개. 기존 turn/feedback 보존, 이후 turn append."""
    sb = get_supabase()
    session = _owned_session(sb, conversation_id, user_id)

    if not session.get("ended_at"):
        raise AppError(409, "conversation_already_active", "Conversation is already active")

    try:
        res = sb.table("sessions").update({
            "ended_at": None,
            "reopened_at": _now_iso(),
            "reopen_count": (session.get("reopen_count") or 0) + 1,
        }).eq("id", conversation_id).eq("user_id", user_id).execute()
    except Exception as e:
        logging.error(f"reopen_conversation failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to reopen conversation")

    row = res.data[0] if res.data else session
    return {"conversation": {
        "id": row["id"],
        "status": "active",
        "completed_at": None,
        "reopened_at": row.get("reopened_at"),
        "reopen_count": row.get("reopen_count", 0),
    }}


# ── Achievements — 일일 Task 3개 + Streak (5주차, A단계) ──────────────────────
#
# PM v2.0: 30개 마스터 풀에서 매일 A1 고정 + hash 로 2개 결정적 선택.
# Streak = 그날 3개 모두 완료한 날의 연속 수. 완료 판정은 서버 계산(클라이언트 못 씀).
# 30개 Task 전부 서버에서 판정: 오늘 범위(A/B/C/D + E6)와 교차일/주간/추세(A5 reopen,
# D1 톤변화, E1 어제자격, E2/E3 주간, E4 Intimacy 상승, E5 문장길이 추세)까지 포함.

# (category, title, description)
_TASK_CATALOG: Dict[str, tuple] = {
    "A1": ("A", "오늘 Pally와 대화 시작하기", "오늘 Pally와 새 대화를 시작해보세요"),
    "A2": ("A", "오늘 대화에서 3턴 이상 주고받기", "오늘 대화에서 3턴 이상 주고받아보세요"),
    "A3": ("A", "오늘 대화에서 5턴 이상 주고받기", "오늘 대화에서 5턴 이상 주고받아보세요"),
    "A4": ("A", "오늘 대화 세션 2개 이상 만들기", "오늘 새 대화를 2개 이상 시작해보세요"),
    "A5": ("A", "History에서 이전 대화 이어가기", "이전에 완료한 대화를 다시 이어가보세요"),
    "A6": ("A", "오늘 대화를 끝까지 완료하기", "오늘 대화를 완료 상태로 마무리해보세요"),
    "B1": ("B", "대화 중 질문 담긴 발화 하기", "물음표가 담긴 발화를 한 번 이상 해보세요"),
    "B2": ("B", "한 턴에 30단어 이상 길게 말해보기", "한 턴에 30단어 이상 길게 말해보세요"),
    "B3": ("B", "Energy 축 60 이상 기록하기", "활기찬 말투로 Energy를 올려보세요"),
    "B4": ("B", "Humor 축 60 이상 기록하기", "유머러스한 말투로 Humor를 올려보세요"),
    "B5": ("B", "Curiosity 축 60 이상 기록하기", "호기심 담긴 말투로 Curiosity를 올려보세요"),
    "B6": ("B", "나만의 톤으로 대화하기", "격식/비격식 어느 쪽이든 뚜렷한 톤으로 말해보세요"),
    "C1": ("C", "오늘 대화에서 교정 표현 받아보기", "오늘 대화에서 피드백을 받아보세요"),
    "C2": ("C", "지난 대화 기록 다시 열어보기", "이전 대화 상세를 다시 열어보세요"),
    "C3": ("C", "대화 로그 펼쳐서 다시 읽어보기", "대화 로그를 펼쳐서 읽어보세요"),
    "C4": ("C", "대화 로그 2번 이상 펼쳐보기", "대화 로그를 2번 이상 펼쳐보세요"),
    "C5": ("C", "대화 중 피드백 2개 이상 만들기", "오늘 피드백을 2개 이상 받아보세요"),
    "C6": ("C", "오늘 나온 교정 표현 확인하기", "오늘 받은 교정 표현을 열어 확인해보세요"),
    "D1": ("D", "대화 속에서 Pally 톤 변화 느껴보기", "말투를 바꿔 Pally의 톤 변화를 만들어보세요"),
    "D2": ("D", "오전에 대화하기", "오전(06~12시)에 대화해보세요"),
    "D3": ("D", "저녁에 대화하기", "저녁(18~24시)에 대화해보세요"),
    "D4": ("D", "주말에도 대화하기", "주말에도 대화를 이어가보세요"),
    "D5": ("D", "My Pally에서 내 프로필 확인하기", "My Pally에서 프로필을 확인해보세요"),
    "D6": ("D", "Achievements에서 Streak 확인하기", "Achievements에서 오늘의 Streak을 확인해보세요"),
    "E1": ("E", "어제에 이어 오늘도 Streak 이어가기", "어제에 이어 오늘도 3개 Task를 완료해보세요"),
    "E2": ("E", "이번 주 3일 이상 대화하기", "이번 주에 3일 이상 대화해보세요"),
    "E3": ("E", "이번 주 첫 대화 시작하기", "이번 주 첫 대화를 시작해보세요"),
    "E4": ("E", "Intimacy 축이 어제보다 상승하기", "어제보다 Intimacy를 더 올려보세요"),
    "E5": ("E", "지난 세션보다 더 긴 문장으로 말해보기", "지난 대화보다 평균적으로 더 길게 말해보세요"),
    "E6": ("E", "오늘 무료 대화량 절반 이상 채우기", "오늘 무료 대화량의 절반 이상을 사용해보세요"),
}
_FIXED_TASK = "A1"


def _select_daily_task_ids(user_id: str, date_kst: str) -> list:
    """A1 고정 + 나머지 29개 중 hash(user_id+date) 로 2개 결정적 선택 (같은 날 불변)."""
    pool = [t for t in _TASK_CATALOG if t != _FIXED_TASK]
    ranked = sorted(pool, key=lambda t: hashlib.sha256(f"{user_id}:{date_kst}:{t}".encode()).hexdigest())
    return [_FIXED_TASK, ranked[0], ranked[1]]


def _kst_day_window_utc(date_kst: str) -> tuple:
    d = datetime.fromisoformat(date_kst).date()
    start = datetime.combine(d, dtime.min, tzinfo=_KST).astimezone(timezone.utc)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def _gather_achievement_context(sb, user_id: str, date_kst: str) -> dict:
    start, end = _kst_day_window_utc(date_kst)
    try:
        sess = sb.table("sessions").select("id, created_at, ended_at, reopened_at").eq("user_id", user_id).execute()
    except Exception as e:
        logging.error(f"achievements sessions read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to load achievements data")
    sessions = sess.data or []
    sess_ids = [s["id"] for s in sessions]
    sessions_today = [s for s in sessions if start <= s["created_at"] < end]
    completed_today = [s for s in sessions if s.get("ended_at") and start <= s["ended_at"] < end]

    user_msgs = []
    if sess_ids:
        msgs = sb.table("messages").select("session_id, role, transcript, axes, character, created_at, feedback").in_("session_id", sess_ids).gte("created_at", start).lt("created_at", end).order("created_at").execute()
        user_msgs = [m for m in (msgs.data or []) if m["role"] == "user"]

    ev = sb.table("activity_events").select("event_type").eq("user_id", user_id).gte("received_at", start).lt("received_at", end).execute()
    event_counts: Dict[str, int] = {}
    for e in (ev.data or []):
        event_counts[e["event_type"]] = event_counts.get(e["event_type"], 0) + 1

    usage = sb.table("usage_daily").select("used_turns").eq("user_id", user_id).eq("date_kst", date_kst).execute()
    used_turns = usage.data[0]["used_turns"] if usage.data else 0

    # 이번 주(월~일 KST) conversation 생성 distinct 날짜 (E2/E3용)
    monday = datetime.fromisoformat(date_kst).date() - timedelta(days=datetime.fromisoformat(date_kst).weekday())
    week_dates = {
        datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")).astimezone(_KST).date()
        for s in sessions
    }
    week_conv_dates = {d for d in week_dates if monday <= d <= monday + timedelta(days=6)}

    return {
        "date_kst": date_kst,
        "window": (start, end),
        "sessions": sessions,
        "sess_ids": sess_ids,
        "sessions_today": sessions_today,
        "completed_today": completed_today,
        "user_msgs": user_msgs,
        "event_counts": event_counts,
        "used_turns": used_turns,
        "week_conv_dates": week_conv_dates,
    }


def _msg_in_kst_hour(msgs: list, h_start: int, h_end: int) -> bool:
    for m in msgs:
        dt = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")).astimezone(_KST)
        if h_start <= dt.hour < h_end:
            return True
    return False


def _avg_words(msgs: list) -> float:
    counts = [len((m.get("transcript") or "").split()) for m in msgs]
    return (sum(counts) / len(counts)) if counts else 0.0


def _last_user_axis(sb, sess_ids: list, win_start: str, win_end: str, key: str):
    """윈도우 내 마지막 user 메시지의 특정 축 값 (없으면 None)."""
    if not sess_ids:
        return None
    r = (
        sb.table("messages").select("axes, created_at")
        .in_("session_id", sess_ids).eq("role", "user")
        .gte("created_at", win_start).lt("created_at", win_end)
        .order("created_at", desc=True).limit(1).execute()
    )
    if r.data and r.data[0].get("axes"):
        return r.data[0]["axes"].get(key)
    return None


def _eval_task(sb, user_id: str, date_kst: str, task_id: str, ctx: dict) -> bool:
    um = ctx["user_msgs"]
    ec = ctx["event_counts"]
    start, end = ctx["window"]

    def axis_any(key, pred) -> bool:
        return any(pred((m.get("axes") or {}).get(key)) for m in um if m.get("axes"))

    # A — 대화 세션
    if task_id == "A1":
        return len(ctx["sessions_today"]) >= 1
    if task_id == "A2":
        return len(um) >= 3
    if task_id == "A3":
        return len(um) >= 5
    if task_id == "A4":
        return len(ctx["sessions_today"]) >= 2
    if task_id == "A5":
        # reopen 이 오늘 있었고, 그 이후 오늘 user turn 이 추가됨
        for s in ctx["sessions"]:
            r = s.get("reopened_at")
            if r and start <= r < end and any(m["session_id"] == s["id"] and m["created_at"] >= r for m in um):
                return True
        return False
    if task_id == "A6":
        return len(ctx["completed_today"]) >= 1

    # B — 품질 / 축
    if task_id == "B1":
        return any("?" in (m.get("transcript") or "") for m in um)
    if task_id == "B2":
        return any(len((m.get("transcript") or "").split()) >= 30 for m in um)
    if task_id == "B3":
        return axis_any("Energy", lambda v: v is not None and v >= 60)
    if task_id == "B4":
        return axis_any("Humor", lambda v: v is not None and v >= 60)
    if task_id == "B5":
        return axis_any("Curiosity", lambda v: v is not None and v >= 60)
    if task_id == "B6":
        return axis_any("Formality", lambda v: v is not None and (v <= 20 or v >= 80))

    # C — 피드백 / 열람
    if task_id == "C1":
        return sum(len(m.get("feedback") or []) for m in um) >= 1
    if task_id == "C5":
        return sum(len(m.get("feedback") or []) for m in um) >= 2
    if task_id == "C2":
        return ec.get("conversation_detail_opened", 0) >= 1
    if task_id == "C3":
        return ec.get("transcript_expanded", 0) >= 1
    if task_id == "C4":
        return ec.get("transcript_expanded", 0) >= 2
    if task_id == "C6":
        return ec.get("feedback_item_opened", 0) >= 1

    # D — 캐릭터 변화 / 시간대
    if task_id == "D1":
        # 직전 user turn 대비 tone_casual 15 이상 변화
        prev = None
        for m in um:
            tc = (m.get("character") or {}).get("tone_casual")
            if tc is None:
                continue
            if prev is not None and abs(tc - prev) >= 15:
                return True
            prev = tc
        return False
    if task_id == "D2":
        return _msg_in_kst_hour(um, 6, 12)
    if task_id == "D3":
        return _msg_in_kst_hour(um, 18, 24)
    if task_id == "D4":
        return datetime.fromisoformat(ctx["date_kst"]).weekday() >= 5 and len(um) >= 1
    if task_id == "D5":
        return ec.get("profile_opened", 0) >= 1
    if task_id == "D6":
        return ec.get("achievements_opened", 0) >= 1

    # E — 연속 / 누적
    if task_id == "E1":
        # 어제 자격(qualified) 이었는지
        y = (datetime.fromisoformat(date_kst).date() - timedelta(days=1)).isoformat()
        r = sb.table("streak_days").select("qualified").eq("user_id", user_id).eq("date_kst", y).execute()
        return bool(r.data and r.data[0]["qualified"])
    if task_id == "E2":
        return len(ctx["week_conv_dates"]) >= 3
    if task_id == "E3":
        return len(ctx["week_conv_dates"]) >= 1
    if task_id == "E4":
        # 오늘 마지막 Intimacy > 어제 마지막 Intimacy
        today_intimacy = None
        for m in reversed(um):
            v = (m.get("axes") or {}).get("Intimacy")
            if v is not None:
                today_intimacy = v
                break
        if today_intimacy is None:
            return False
        y_start = (datetime.fromisoformat(start) - timedelta(days=1)).isoformat()
        y_intimacy = _last_user_axis(sb, ctx["sess_ids"], y_start, start, "Intimacy")
        return y_intimacy is not None and today_intimacy > y_intimacy
    if task_id == "E5":
        # 오늘 평균 단어수 > 직전(오늘 이전 가장 최근) conversation 평균
        today_avg = _avg_words(um)
        if today_avg <= 0:
            return False
        prior = [s for s in ctx["sessions"] if s["created_at"] < start]
        if not prior:
            return False
        prev_session = max(prior, key=lambda s: s["created_at"])
        r = sb.table("messages").select("transcript").eq("session_id", prev_session["id"]).eq("role", "user").execute()
        prev_avg = _avg_words(r.data or [])
        return prev_avg > 0 and today_avg > prev_avg
    if task_id == "E6":
        return ctx["used_turns"] >= max(1, FREE_DAILY_TURNS // 2)

    return False


def _compute_streak(sb, user_id: str, today_kst: str) -> int:
    try:
        rows = sb.table("streak_days").select("date_kst, qualified").eq("user_id", user_id).order("date_kst", desc=True).limit(400).execute()
    except Exception as e:
        logging.warning(f"streak read failed: {e}")
        return 0
    qualified = {r["date_kst"] for r in (rows.data or []) if r["qualified"]}
    today = datetime.fromisoformat(today_kst).date()
    cursor = today if today_kst in qualified else today - timedelta(days=1)
    count = 0
    while cursor.isoformat() in qualified:
        count += 1
        cursor -= timedelta(days=1)
    return count


@app.get("/api/achievements")
async def get_achievements(user_id: str = Depends(get_current_user_id)):
    """
    오늘의 Daily Task 3개(완료 상태 포함) + Streak. 서버 계산만 신뢰 (클라이언트 못 씀).
    D6(achievements_opened)은 이 화면 진입 이벤트라, 이 API 자체로는 완료되지 않는다
    — 프론트가 POST /api/activity-events(achievements_opened)를 보낸 뒤 반영됨.
    """
    sb = get_supabase()
    date_kst = _kst_date()

    # 1. 오늘 선택 3개 (snapshot 고정). 선택은 결정적이라 경합해도 동일.
    try:
        snap = sb.table("daily_task_snapshots").select("task_ids").eq("user_id", user_id).eq("date_kst", date_kst).execute()
    except Exception as e:
        logging.error(f"daily_task_snapshots read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to load daily tasks")
    if snap.data:
        task_ids = snap.data[0]["task_ids"]
    else:
        task_ids = _select_daily_task_ids(user_id, date_kst)
        try:
            sb.table("daily_task_snapshots").upsert(
                {"user_id": user_id, "date_kst": date_kst, "task_ids": task_ids},
                on_conflict="user_id,date_kst", ignore_duplicates=True,
            ).execute()
        except Exception as e:
            logging.error(f"daily_task_snapshots write failed: {e}")
            raise AppError(503, "persistence_failed", "Failed to persist daily tasks")

    # 2. 완료 평가
    ctx = _gather_achievement_context(sb, user_id, date_kst)
    completed_at = _now_iso()
    daily_tasks = []
    all_done = True
    for tid in task_ids:
        _cat, title, desc = _TASK_CATALOG.get(tid, ("?", tid, ""))
        done = _eval_task(sb, user_id, date_kst, tid, ctx)
        if not done:
            all_done = False
        daily_tasks.append({
            "id": tid,
            "title": title,
            "description": desc,
            "status": "completed" if done else "default",
            "completed_at": completed_at if done else None,
        })

    # 3. Streak: 오늘 자격 여부 기록 + 연속 카운트
    try:
        sb.table("streak_days").upsert(
            {"user_id": user_id, "date_kst": date_kst, "qualified": all_done},
            on_conflict="user_id,date_kst",
        ).execute()
    except Exception as e:
        logging.warning(f"streak_days upsert failed: {e}")
    streak_count = _compute_streak(sb, user_id, date_kst)

    return {
        "date": date_kst,
        "timezone": "Asia/Seoul",
        "streak_count": streak_count,
        "daily_tasks": daily_tasks,
    }


# ── Billing / Subscription — 5주차 (provider-neutral, 카카오페이 예정) ─────────
#
# 실제 결제사(카카오페이)는 가맹점 키 + sandbox 실호출 검증 후 어댑터를 채운다.
# 지금은 mock 어댑터로 요금제 화면·구독 흐름을 붙일 수 있게 하고, provider 는
# BILLING_PROVIDER env(mock|kakaopay, 기본 mock)로 고른다. Pro 권한은 클라이언트
# 영수증이 아니라 subscriptions.entitled(서버 값)만 신뢰한다.

# 상품 catalog (config). 통화는 Figma 기준 USD placeholder — 카카오페이(KRW) 확정 시 조정.
_BILLING_PRODUCTS = [
    {"id": "pro_monthly", "name": "Monthly", "interval": "month", "amount_minor": 999, "currency": "USD", "display_price": "$9.99", "trial_days": 0},
    {"id": "pro_yearly", "name": "Yearly", "interval": "year", "amount_minor": 9999, "currency": "USD", "display_price": "$99.99", "trial_days": 7},
]
_PRODUCT_IDS = {p["id"] for p in _BILLING_PRODUCTS}


class WebhookSignatureError(Exception):
    pass


class BillingProvider:
    """provider-neutral 인터페이스. 실제 provider 는 이 메서드들을 채운다."""
    name = "base"

    def list_products(self) -> list:
        return list(_BILLING_PRODUCTS)

    def create_checkout(self, user_id: str, product_id: str, success_url: str, cancel_url: str) -> dict:
        raise NotImplementedError

    def refresh_subscription(self, user_id: str) -> Optional[dict]:
        """provider 에서 최신 구독 상태를 조회. mock 은 None(변화 없음)."""
        return None

    def verify_and_parse_webhook(self, headers: dict, raw_body: bytes) -> tuple:
        """(provider_event_id, event dict) 반환. 서명 실패는 WebhookSignatureError."""
        raise NotImplementedError


class MockBillingProvider(BillingProvider):
    """개발용. 실제 결제 없이 흐름만. webhook 은 서명 없이 body 를 신뢰(테스트 전용)."""
    name = "mock"

    def create_checkout(self, user_id: str, product_id: str, success_url: str, cancel_url: str) -> dict:
        expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        return {
            "product_id": product_id,
            "checkout_url": f"https://mock-checkout.local/session/{uuid.uuid4().hex}",
            "expires_at": expires,
        }

    def verify_and_parse_webhook(self, headers: dict, raw_body: bytes) -> tuple:
        try:
            event = json.loads(raw_body.decode() or "{}")
        except Exception:
            raise WebhookSignatureError("invalid payload")
        event_id = event.get("event_id")
        if not event_id:
            raise WebhookSignatureError("missing event_id")
        return event_id, event


class KakaoPayBillingProvider(BillingProvider):
    """카카오페이 어댑터 자리. 가맹점 키 확보 + sandbox 실호출 검증 전에는 미설정."""
    name = "kakaopay"

    def create_checkout(self, user_id: str, product_id: str, success_url: str, cancel_url: str) -> dict:
        raise AppError(503, "billing_not_configured", "KakaoPay is not configured yet")

    def refresh_subscription(self, user_id: str) -> Optional[dict]:
        raise AppError(503, "billing_not_configured", "KakaoPay is not configured yet")

    def verify_and_parse_webhook(self, headers: dict, raw_body: bytes) -> tuple:
        raise AppError(503, "billing_not_configured", "KakaoPay is not configured yet")


_BILLING_PROVIDERS = {"mock": MockBillingProvider(), "kakaopay": KakaoPayBillingProvider()}
_BILLING_PROVIDER_NAME = os.getenv("BILLING_PROVIDER", "mock")


def _billing_provider_by_name(name: str) -> BillingProvider:
    p = _BILLING_PROVIDERS.get(name)
    if p is None:
        raise AppError(404, "not_found", "Unknown billing provider")
    return p


def _get_billing_provider() -> BillingProvider:
    return _billing_provider_by_name(_BILLING_PROVIDER_NAME)


def _subscription_to_response(row: Optional[dict]) -> dict:
    if not row or not row.get("entitled"):
        return {
            "plan": (row or {}).get("plan", "free") if row else "free",
            "status": (row or {}).get("status", "none") if row else "none",
            "entitled": False,
            "product_id": (row or {}).get("product_id") if row else None,
            "current_period_end": (row or {}).get("current_period_end") if row else None,
            "will_renew": bool((row or {}).get("will_renew")) if row else False,
            "entitlements": [],
            "updated_at": (row or {}).get("updated_at") if row else None,
        }
    return {
        "plan": row.get("plan", "pro"),
        "status": row.get("status", "active"),
        "entitled": True,
        "product_id": row.get("product_id"),
        "current_period_end": row.get("current_period_end"),
        "will_renew": bool(row.get("will_renew")),
        "entitlements": ["unlimited_turns"],
        "updated_at": row.get("updated_at"),
    }


def _read_subscription(sb, user_id: str) -> Optional[dict]:
    try:
        r = sb.table("subscriptions").select("*").eq("user_id", user_id).execute()
    except Exception as e:
        logging.error(f"subscription read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read subscription")
    return r.data[0] if r.data else None


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str
    success_url: str
    cancel_url: str


@app.get("/api/billing/products")
async def billing_products(user_id: str = Depends(get_current_user_id)):
    """플랫폼별 상품 목록. 가격은 서버에서 (프론트 하드코딩 금지)."""
    return {"products": _get_billing_provider().list_products()}


@app.post("/api/billing/checkout", status_code=201)
async def billing_checkout(
    req: CheckoutRequest,
    user_id: str = Depends(get_current_user_id),
    _idem: str = Depends(require_idempotency_key),
):
    """결제 시작. checkout 생성만으로 Pro 활성화 안 됨 — webhook/refresh 로 검증 후 entitled."""
    if req.product_id not in _PRODUCT_IDS:
        raise AppError(422, "invalid_product", "Unknown product_id")
    checkout = _get_billing_provider().create_checkout(user_id, req.product_id, req.success_url, req.cancel_url)
    return {"checkout": checkout}


@app.get("/api/subscription")
async def get_subscription(user_id: str = Depends(get_current_user_id)):
    """서버 기준 구독 권한. 화면·quota 는 이 값만 신뢰."""
    sb = get_supabase()
    return {"subscription": _subscription_to_response(_read_subscription(sb, user_id))}


@app.post("/api/subscription/refresh")
async def refresh_subscription(
    user_id: str = Depends(get_current_user_id),
    _idem: str = Depends(require_idempotency_key),
):
    """결제 성공 callback 후 등 — provider 에서 최신 상태 동기화."""
    sb = get_supabase()
    updated = _get_billing_provider().refresh_subscription(user_id)
    if updated:
        try:
            sb.table("subscriptions").upsert({**updated, "user_id": user_id, "updated_at": _now_iso()},
                                             on_conflict="user_id").execute()
        except Exception as e:
            logging.error(f"subscription refresh upsert failed: {e}")
            raise AppError(503, "persistence_failed", "Failed to sync subscription")
    return {"subscription": _subscription_to_response(_read_subscription(sb, user_id))}


@app.post("/api/webhooks/billing/{provider}", status_code=204)
async def billing_webhook(provider: str, request: Request):
    """provider 결제 이벤트 반영. 사용자 JWT 없음, provider 서명 검증. 같은 event 재전송은 204(무시)."""
    prov = _billing_provider_by_name(provider)
    raw = await request.body()
    try:
        event_id, event = prov.verify_and_parse_webhook(dict(request.headers), raw)
    except WebhookSignatureError:
        raise AppError(401, "webhook_signature_invalid", "Webhook signature verification failed")

    sb = get_supabase()
    # 멱등: 같은 (provider, event_id) 이미 처리했으면 재처리 안 함
    try:
        dup = sb.table("billing_events").select("provider_event_id").eq("provider", provider).eq("provider_event_id", event_id).execute()
    except Exception as e:
        logging.error(f"billing_events read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to process webhook")
    if dup.data:
        return Response(status_code=204)

    try:
        sb.table("billing_events").insert({"provider": provider, "provider_event_id": event_id, "payload": event}).execute()
    except Exception as e:
        logging.error(f"billing_events insert failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to record webhook")

    # 구독 상태 반영 (mock: event 의 user_id/action/product_id 로)
    target_user = event.get("user_id")
    action = event.get("action")
    if target_user and action in ("activate", "cancel"):
        entitled = action == "activate"
        try:
            sb.table("subscriptions").upsert({
                "user_id": target_user,
                "plan": "pro" if entitled else "free",
                "status": "active" if entitled else "canceled",
                "entitled": entitled,
                "product_id": event.get("product_id"),
                "will_renew": entitled,
                "provider": provider,
                "updated_at": _now_iso(),
            }, on_conflict="user_id").execute()
        except Exception as e:
            logging.error(f"subscription apply failed: {e}")
            raise AppError(503, "persistence_failed", "Failed to apply subscription")

    return Response(status_code=204)


# ── Account deletion — 스캐폴드 (플래그 off + 재인증 fail-closed, 하드삭제 없음) ──
# W7: 엔드포인트 골격만. 실제 활성화는 (1) PM 재인증 방식 확정 (2) 2년 보존 후 purge 잡
# 구현 후. 그 전까지는 어떤 경로로도 데이터를 지우지 않는다 (이중 fail-closed).

_ACCOUNT_DELETION_ENABLED = os.getenv("ACCOUNT_DELETION_ENABLED") == "1"
_DELETION_RETENTION_DAYS = 730  # 2년 보존 (PM 확정)


def _verify_reauth(user, payload: dict) -> bool:
    """계정 삭제용 재인증 검증. PM 이 방식(비밀번호 재입력/OAuth 재동의/OTP)을 확정하기
    전까지는 미구현 → 항상 False (fail-closed: 재인증 없이는 삭제를 절대 진행하지 않음)."""
    return False


class AccountDeletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Optional[str] = None
    reauth_token: Optional[str] = None


@app.post("/api/account/deletion-request", status_code=202)
async def request_account_deletion(
    req: AccountDeletionRequest,
    user=Depends(get_current_user),
    _idem: str = Depends(require_idempotency_key),
):
    """계정 삭제 요청 (스캐폴드). 즉시 삭제하지 않고 2년 보존 후 정리 대상으로만 기록.
    - 기능 플래그 off → 503 (기본값).
    - 재인증 미구현 → 501 (fail-closed). PM 방식 확정 후 _verify_reauth 구현.
    """
    if not _ACCOUNT_DELETION_ENABLED:
        raise AppError(503, "account_deletion_not_enabled",
                       "계정 삭제 기능이 아직 활성화되지 않았어요.")
    if not _verify_reauth(user, req.model_dump()):
        raise AppError(501, "reauth_not_implemented",
                       "삭제 전 재인증 방식이 확정되지 않았어요.")
    sb = get_supabase()
    now = datetime.now(timezone.utc)
    purge_after = (now + timedelta(days=_DELETION_RETENTION_DAYS)).isoformat()
    try:
        sb.table("deletion_requests").upsert({
            "user_id": user.id,
            "requested_at": now.isoformat(),
            "purge_after": purge_after,
            "status": "pending",
            "updated_at": now.isoformat(),
        }, on_conflict="user_id").execute()
    except Exception as e:
        logging.error(f"deletion request save failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to record deletion request")
    return {"status": "pending", "purge_after": purge_after, "retention_days": _DELETION_RETENTION_DAYS}


@app.get("/api/account/deletion-request")
async def get_account_deletion(user_id: str = Depends(get_current_user_id)):
    """본인 삭제 요청 상태 조회 (없으면 status=none)."""
    sb = get_supabase()
    try:
        r = sb.table("deletion_requests").select("status, requested_at, purge_after").eq("user_id", user_id).execute()
    except Exception as e:
        logging.error(f"deletion request read failed: {e}")
        raise AppError(503, "persistence_failed", "Failed to read deletion request")
    if not r.data:
        return {"status": "none"}
    row = r.data[0]
    return {"status": row["status"], "requested_at": row.get("requested_at"), "purge_after": row.get("purge_after")}
