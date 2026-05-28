# Pally Backend API 명세서

> 작성일: 2026-05-19  
> 담당: 백은혜 (파트 C)  
> Base URL (로컬): `http://localhost:8000`  
> Base URL (배포 후): Railway URL로 교체 예정

---

## 목차

1. [공통 사항](#1-공통-사항)
2. [GET /api/health](#2-get-apihealth)
3. [POST /api/stt](#3-post-apistt)
4. [POST /api/feedback](#4-post-apifeedback)
5. [POST /api/chat](#5-post-apichat)
6. [POST /api/tts](#6-post-apitts)
7. [파트 A 연동 가이드](#7-파트-a-연동-가이드)
8. [파트 B 연동 가이드](#8-파트-b-연동-가이드)
9. [에러 코드](#9-에러-코드)

---

## 1. 공통 사항

- **Content-Type**: `application/json` (파일 업로드는 `multipart/form-data`)
- **CORS**: 모든 origin 허용 (개발 환경)
- **인증**: MVP에서는 없음

---

## 2. GET /api/health

서버 상태 확인. 연동 전 서버가 떠 있는지 확인할 때 사용.

**Response**
```json
{ "status": "ok" }
```

---

## 3. POST /api/stt

오디오 파일 → 텍스트 변환 (Google Cloud Speech-to-Text)

### Request

- Content-Type: `multipart/form-data`
- Body: `audio` 필드에 오디오 파일

```
Form field: audio (file)
  - 지원 형식: webm, opus, mp3, wav, flac
  - 브라우저 MediaRecorder 기본 출력(webm/opus) 그대로 전송 가능
  - 제한: 최대 60초
```

### Response `200`

```json
{
  "transcript": "yo what's up, you wanna hang out?",
  "confidence": 0.94
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `transcript` | string | 인식된 텍스트. 음성이 없으면 빈 문자열 `""` |
| `confidence` | float | 인식 신뢰도 0.0~1.0 |

### 파트 A 사용 예시 (JavaScript)

```javascript
const formData = new FormData();
formData.append('audio', audioBlob, 'recording.webm');

const res = await fetch('http://localhost:8000/api/stt', {
  method: 'POST',
  body: formData,
});
const { transcript, confidence } = await res.json();
```

---

## 4. POST /api/feedback

핵심 엔드포인트. utterance → 5축 분석 → EMA → 캐릭터 파라미터 → Gemini 피드백 → TTS

### Request

```json
{
  "utterance": "yo what's up lol, u wanna hang or nah?",
  "session_id": "optional-session-uuid",
  "current_axes": {
    "Formality": 30,
    "Energy": 55,
    "Intimacy": 40,
    "Humor": 45,
    "Curiosity": 25
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `utterance` | string | ✅ | 사용자가 입력한 영어 문장 |
| `session_id` | string | ❌ | 세션 식별자 (로깅용, 현재 저장 안 함) |
| `current_axes` | object | ❌ | 이전 누적 5축 점수. **있으면 EMA 적용, 없으면 raw 점수 그대로 사용** |

> **`current_axes` 사용 방법**: 첫 번째 메시지는 `current_axes` 없이 보내고, 이후 응답의 `axes` 값을 저장했다가 다음 요청의 `current_axes`로 전달하면 됩니다.

### Response `200`

```json
{
  "status": "ok",
  "axes": {
    "Formality": 12,
    "Energy": 58,
    "Intimacy": 44,
    "Humor": 40,
    "Curiosity": 25
  },
  "character": {
    "tone_casual": 68,
    "energy_level": 54,
    "humor_level": 36
  },
  "character_labels": {
    "tone": "Very casual (slang freely used)",
    "energy": "Moderate",
    "humor": "Occasional wit"
  },
  "feedback": {
    "correction": "Instead of 'u wanna hang or nah', try 'Do you want to hang out?'",
    "tone_feedback": "Your casual, energetic tone comes through clearly — very natural!",
    "practice_prompt": "Can you tell me about your favorite place to hang out and why you like it?"
  },
  "tts_audio": "//NExAA...base64encodedMP3..."
}
```

#### `axes` — EMA 적용 후 누적 5축 점수 (0~100)

| 키 | 설명 |
|----|------|
| `Formality` | 격식도. 낮을수록 캐주얼 |
| `Energy` | 에너지. 높을수록 활발 |
| `Intimacy` | 친밀도. 높을수록 친근 |
| `Humor` | 유머 성향 |
| `Curiosity` | 탐구 성향. 질문이 많을수록 높음 |

#### `character` — 캐릭터 파라미터 (0~100)

| 키 | 설명 | Canvas2D 매핑 |
|----|------|--------------|
| `tone_casual` | 캐주얼 말투 정도 | 꼭짓점 수 (낮을수록 뾰족, 높을수록 둥글) |
| `energy_level` | 반응 에너지 | 크기 / 진동 주파수 |
| `humor_level` | 유머/장난기 | 색상 채도 / 불규칙성 |

> **파트 B**: Canvas2D 캐릭터 업데이트는 `character` 값 사용

#### `character_labels` — 사람이 읽을 수 있는 레이블

```
tone   : "Very casual" | "Neutral" | "Formal"
energy : "Very active" | "Moderate" | "Calm"
humor  : "Humor/meme mode" | "Occasional wit" | "Serious and direct"
```

#### `feedback` — Gemini 2.5 Flash 생성 피드백

| 키 | 설명 |
|----|------|
| `correction` | 대안 표현 또는 자연스러운 교정 문장 |
| `tone_feedback` | 발화 톤/에너지/유머에 대한 격려 피드백 |
| `practice_prompt` | 이어서 연습할 수 있는 질문/프롬프트 |

#### `tts_audio` — base64 MP3

`correction` 문장을 Google TTS로 변환한 결과. FE에서 바로 재생 가능.

```javascript
// 재생 방법
const audio = new Audio(`data:audio/mp3;base64,${tts_audio}`);
audio.play();
```

TTS 실패 시 `null` 반환 (피드백 텍스트는 정상 반환됨).

### 파트 A 사용 예시 (JavaScript)

```javascript
// 첫 번째 호출 — current_axes 없이
const res = await fetch('http://localhost:8000/api/feedback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ utterance: userInput }),
});
const data = await res.json();

// 다음 호출 — 이전 응답의 axes를 전달 (EMA 누적)
const res2 = await fetch('http://localhost:8000/api/feedback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    utterance: nextInput,
    current_axes: data.axes,  // 이전 응답 axes 그대로 전달
  }),
});
```

---

## 5. POST /api/chat

사용자의 텍스트 발화를 받아 Gemini 영어 응답, Google TTS 음성, 인라인 한국어 힌트, 5축/캐릭터 파라미터를 함께 반환합니다.

#### Request

```json
{
  "utterance": "Hello Pally, I want to practice English",
  "session_id": "optional-session-uuid",
  "current_axes": {
    "Formality": 30,
    "Energy": 55,
    "Intimacy": 40,
    "Humor": 45,
    "Curiosity": 25
  },
  "conversation_history": [
    { "role": "user", "content": "Hi" },
    { "role": "pally", "content": "Hello! How are you today?" }
  ],
  "character_name": "Pally",
  "level": "B1"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `utterance` | string | ✅ | 사용자의 텍스트 발화. |
| `session_id` | string | ❌ | 익명 세션 UUID. 있으면 같은 세션의 이전 대화 이력을 Supabase에서 로드하고 이후 메시지를 저장합니다. |
| `current_axes` | object | ❌ | 이전 누적 5축 점수. 있으면 EMA가 적용됩니다. |
| `conversation_history` | array | ❌ | 클라이언트가 이미 보유한 대화 이력. 서버에서 로드된 이력이 없을 때 참조됩니다. |
| `character_name` | string | ❌ | 응답에 사용할 캐릭터 이름. 기본값은 `Pally`. |
| `level` | string | ❌ | 응답 난이도. `A2` / `B1` / `B2` / `C1`. 기본값은 `B1`. |

#### Response `200`

```json
{
  "status": "ok",
  "transcript": "Hello Pally, I want to practice English",
  "reply": "That sounds great! What part do you want to work on first?",
  "tts_audio": "//base64 mp3...",
  "axes": {
    "Formality": 34,
    "Energy": 60,
    "Intimacy": 42,
    "Humor": 20,
    "Curiosity": 50
  },
  "character": {
    "tone_casual": 60,
    "energy_level": 55,
    "humor_level": 25
  },
  "character_labels": {
    "tone": "casual",
    "energy": "moderate",
    "humor": "light"
  },
  "hint_ko": {
    "hint": "좋은 문장이에요! 조금 더 자연스럽게 말하려면~",
    "expression": "That sounds great!"
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `transcript` | string | 입력된 발화를 그대로 에코한 텍스트. |
| `reply` | string | Pally의 영어 회화 응답. |
| `tts_audio` | string / null | Pally 응답을 MP3로 변환한 base64. 실패 시 `null`. |
| `axes` | object | EMA 적용 후 5축 점수. |
| `character` | object | Canvas/캐릭터에 사용할 파라미터. |
| `character_labels` | object | 사람이 읽을 수 있는 레이블. |
| `hint_ko` | object / null | 한국어 인라인 힌트. |

> `hint_ko`는 교정 설명 또는 칭찬과 함께, 올바른 영어 표현을 함께 제공합니다.

---

## 6. POST /api/tts

텍스트 → MP3 오디오 단독 호출용. `/api/feedback`에서 TTS가 자동 포함되므로, 별도 텍스트를 음성으로 변환할 때 사용.

### Request

```json
{
  "text": "Great job! Your sentence sounds very natural.",
  "voice": "en-US-Journey-F",
  "speaking_rate": 1.0
}
```

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `text` | string | — | 변환할 텍스트 |
| `voice` | string | `en-US-Journey-F` | Google TTS 음성 ID |
| `speaking_rate` | float | `1.0` | 말하기 속도 (0.25~4.0) |

**추천 voice 옵션:**

| voice ID | 특징 |
|----------|------|
| `en-US-Journey-F` | 자연스러운 여성 음성 (기본값) |
| `en-US-Journey-D` | 자연스러운 남성 음성 |
| `en-US-Neural2-F` | 고품질 여성 음성 |
| `en-US-Neural2-D` | 고품질 남성 음성 |

### Response `200`

```json
{
  "audio_b64": "//NExAA...base64encodedMP3...",
  "voice": "en-US-Journey-F",
  "encoding": "MP3"
}
```

### 파트 A 재생 예시 (JavaScript)

```javascript
const res = await fetch('http://localhost:8000/api/tts', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'Hello! How are you today?' }),
});
const { audio_b64 } = await res.json();
const audio = new Audio(`data:audio/mp3;base64,${audio_b64}`);
audio.play();
```

---

## 7. 파트 A 연동 가이드

### /feedback 페이지 구현 시 권장 흐름

```
[텍스트 입력 or 마이크 버튼]
        ↓
[마이크] → POST /api/stt → transcript
        ↓
[transcript or 직접 입력] → POST /api/feedback
        ↓
응답 처리:
  - feedback.correction     → 교정 문장 표시
  - feedback.tone_feedback  → 피드백 문장 표시
  - feedback.practice_prompt → 연습 질문 표시
  - tts_audio               → correction 음성 자동 재생
  - axes                    → 5축 점수 바 업데이트
  - character               → 파트 B Canvas2D로 전달
```

### 세션 내 EMA 누적 방법

```javascript
// Zustand 스토어 또는 useState로 관리
const [currentAxes, setCurrentAxes] = useState(null);

const sendFeedback = async (utterance) => {
  const res = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ utterance, current_axes: currentAxes }),
  });
  const data = await res.json();
  setCurrentAxes(data.axes); // 다음 요청에서 사용
  return data;
};
```

---

## 8. 파트 B 연동 가이드

`/api/feedback` 응답의 `character` 값을 Canvas2D에 전달하면 됩니다.

```typescript
// 파트 B가 받아야 하는 타입
interface CharacterParams {
  tone_casual: number;   // 0~100 → 꼭짓점 수 / 형태
  energy_level: number;  // 0~100 → 크기, 진동
  humor_level: number;   // 0~100 → 채도, 불규칙성
}

// 예시 값별 캐릭터 모양
// 캐주얼 발화: { tone_casual: 72, energy_level: 61, humor_level: 44 }
// 격식 발화:   { tone_casual: 16, energy_level: 39, humor_level: 13 }
// 유머 발화:   { tone_casual: 75, energy_level: 71, humor_level: 59 }
```

**기존 `visualizer.html`과의 연결:**
- `tone_casual` → `H` (Humor)와 같은 역할 (꼭짓점 수)
- `energy_level` → `E` (Energy)와 같은 역할 (크기/진동)
- `humor_level` → 채도/불규칙성 추가 반영 가능

---

## 9. 에러 코드

| 코드 | 상황 | 대응 |
|------|------|------|
| `400` | utterance/text 빈 값 | 입력 validation 추가 |
| `500` | GOOGLE_API_KEY 미설정 | .env 확인 |
| `502` | Google API 호출 실패 | 잠시 후 재시도 |
| `422` | 요청 body 형식 오류 | Content-Type, 필드명 확인 |

> **참고**: `/api/feedback`은 Gemini 또는 TTS 실패 시에도 `500`을 반환하지 않습니다.  
> Gemini 실패 → fallback 피드백 텍스트 반환  
> TTS 실패 → `tts_audio: null` 반환 (피드백은 정상)

---

## 로컬 실행 방법

```bash
# 1. .env 파일 생성
cp .env.example .env
# .env에 GOOGLE_API_KEY=실제키 입력

# 2. 의존성 설치
cd backend
pip install -r requirements.txt

# 3. 서버 실행
uvicorn main:app --reload --port 8000

# 4. API 문서 확인 (Swagger UI)
open http://localhost:8000/docs
```
