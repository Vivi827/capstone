# Roadmap: Pally — CharaShift MVP

**Created:** 2026-05-21
**Demo deadline:** 2026-06-07 (17 days)
**Granularity:** coarse (5 phases, parallel-friendly)
**Team:** 3 developers (이찬희 / 백은혜 / 김민주) building in parallel after Phase 0
**LLM vendor:** GCP Vertex AI (Gemini 2.5) — OpenAI 사용 안 함

## Core Value Alignment

**"내 영어 발화 스타일에 반응하는 Pally."**

Every phase exists to make the core loop (사용자 발화 → 5축 분석 → Pally 시각·말투 변화) demoable on a mobile browser by June 7. Phase 0 unblocks parallel work with minimal foundation; Phases 1A/1B/1C are the three slices of the core loop built simultaneously; Phase 2 stitches them into the demo flow.

## Repo Layout (Monorepo)

- `frontend/` — Next.js (Vercel 배포 root, 이찬희 작업 영역)
- `backend/` — FastAPI (Railway 배포 root, 백은혜 작업 영역, `sys.path`로 루트 `ai/`를 import)
- `ai/` — Python 5축 엔진 (`analyzer.py`, `matrix_engine.py`, 김민주 + 백은혜 공동)
- 루트 — 공통 문서(`CLAUDE.md`, `README.md`) + `.planning/`만. 루트에 `.env.example`을 두지 않음 (Vercel/Railway가 각자 root directory의 `.env.example`을 읽음).

기본 작업 영역은 이찬희=`frontend/`, 백은혜=`backend/`, 김민주=`ai/` + `frontend/components/pally/` + `frontend/app/dev/pally/` + `frontend/lib/types/character.ts`로 나눈다. 1A/1B가 둘 다 `frontend/`를 건드리므로 Pally 렌더러/캐릭터 타입/데모 컨트롤은 김민주 소유, 메인 화면/오디오 UX shell은 이찬희 소유로 분리한다.

## Phases

- [x] **Phase 0: Foundation (Minimal)** — Next.js 스캐폴드 + 공유 타입 + `.env.example` + Supabase 클라이언트 + Tailwind. 1A/1B/1C가 즉시 시작할 수 있게 최소만 (완료 2026-05-21)
- [ ] **Phase 1A: FE Screens & Audio Shell** — 메인 대화 화면 + rec/audio UX shell (이찬희)
- [ ] **Phase 1B: Pally Canvas2D + Python Engine Integration** — Superformula 렌더러 + 5축 엔진 통합 ADR (김민주)
- [ ] **Phase 1C: Voice + Inline Feedback Backend + Supabase Schema** — Google Cloud STT/TTS + Vertex AI Gemini로 `/api/chat` + Supabase 테이블/RLS (백은혜)
- [ ] **Phase 2: Integration & Demo Polish** — End-to-end wiring, Vercel deploy, demo rehearsal (전원)

## Phase Details

### Phase 0: Foundation (Minimal)
**Goal**: A/B/C 세 개발자가 본인 phase 첫 task부터 충돌 없이 병렬로 시작할 수 있도록 최소 공유 인프라만 깐다.
**Depends on**: Nothing (first phase)
**Owner**: 이찬희 (단독)
**Requirements**: SESSION-01
**Success Criteria** (what must be TRUE):
  1. Next.js 14 App Router 앱이 `frontend/` 폴더 안에 스캐폴드되고, `cd frontend && npm run dev` 한 번으로 띄울 수 있으며, `/api/health`가 200을 반환한다
  2. `frontend/lib/types/`에 1A가 mock 데이터로 화면을 그리는 데 필요한 최소 UI 타입 — 메시지(`Message`), 세션(`Session`) — 만 정의되어 있다. **`Axes`, `CharacterParams`는 Phase 1B에서 김민주가 엔진 기반으로 정의** (출처가 `ai/analyzer.py` + `matrix_engine.py`이므로 엔진을 다루는 사람이 소유). 백엔드(Python)는 자체 Pydantic 모델을 `backend/`에서 따로 정의하고, FE↔BE 사이의 공유 계약은 `POST /api/chat`의 JSON wire format으로 동기화 (Phase 1C에서 확정)
  3. `frontend/lib/supabase/client.ts`(anon 키)가 작성되어 있고, 실제 Supabase 프로젝트 URL/anon key로 연결만 확인된다 (server.ts와 테이블은 Phase 1C에서 추가)
  4. `frontend/.env.example`(Vercel 배포용, Root Directory = `frontend/`)에 프론트가 쓰는 키(`NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`)가 명시되어 있다. 백엔드 키(`GOOGLE_*`, `SUPABASE_SERVICE_ROLE_KEY`)는 `backend/.env.example`에서 별도 관리 (Phase 1C 배포 항목 참조). 루트에는 `.env.example`을 두지 않음
  5. Tailwind CSS + `cn()` 유틸이 `frontend/`에서 동작하고, `frontend/app/page.tsx`가 빈 placeholder만 렌더한다

**Plans**: 1 plan, 1 wave
Plans:
- [x] 00-01-PLAN.md — Scaffold Next.js 14 frontend, minimal UI types (Message/Session), Supabase anon client + connection check, /api/health, Tailwind + cn(), per-key env migration (root → frontend/backend split per D-14), OpenAI key revoke checkpoint

**Estimated effort**: 0.5 day (2026-05-21 오후 ~ 2026-05-22 오전)
**UI hint**: minimal (scaffold만)

---

### Phase 1A: FE Screens & Audio Shell
**Goal**: 사용자가 모바일 브라우저에서 보게 될 메인 대화 화면이 시각적으로 완성되고, Phase 2에서 실제 백엔드로 교체 가능한 오디오 UX shell이 mock transport로 동작한다.
**Depends on**: Phase 0
**Owner**: 이찬희 (FE · 디자인)
**Requirements**: MAIN-01, CHAT-01
**화면 구성** (총 1 화면):
  - **메인 대화 화면**: 중앙에 Pally + 하단에 rec 버튼 + 최하단 네비게이션 (4 아이콘). 상단에는 토글로 펼쳤다/접었다 할 수 있는 대화 로그 영역 (이전 발화 내용 표시). `/feedback` 별도 화면은 MVP에서 제외한다.
**Success Criteria** (what must be TRUE):
  1. 모바일 폭(~360px)에서 메인 대화 화면이 보인다: Pally 영역(placeholder OK) + rec 버튼 + 하단 네비게이션 (4 아이콘)
  2. 메인 대화 화면 상단 영역이 토글(▲/▼) 가능하며, 펼치면 이전 발화 내용이 표시된다
  3. Phase 0에서 정의한 UI 타입을 import해서 사용하고, mock 데이터로 화면 동작이 검증된다
  4. rec 버튼은 idle → recording → processing → speaking → idle/error 상태를 가진다. 브라우저 오디오 권한 요청, 녹음 Blob 생성, 샘플/mock 오디오 재생은 프론트 mock transport 뒤에서 동작하며, 실제 `NEXT_PUBLIC_BACKEND_URL` 연결은 Phase 2에서 수행한다

> **Note — 온보딩 없음 (MVP)**: 별도 온보딩/랜딩 화면을 두지 않는다. Pally 이름과 영어 레벨은 v2에서 받기로 하고, MVP에서는 Phase 1C가 sessions row를 생성할 때 데모 기본값(`character_name = 'Pally'`, `level = 'B1'`)으로 채운다.
> **Note — 피드백 화면 없음 (MVP)**: `/feedback` route/page는 만들지 않는다. 한국어 힌트/피드백은 `/api/chat` 응답의 inline payload로만 전달하고, 메인 화면 안에서 필요한 만큼만 표시한다.
**Plans**: 5 plans, 3 waves
Plans:
- [x] 01A-01-PLAN.md — Tailwind color tokens + layout shell (viewport lock 402px, cream surface, Pally metadata)
- [x] 01A-02-PLAN.md — Wire types (chat.ts) + useReducer state machine + single-swap mock + MediaRecorder MIME probe
- [x] 01A-03-PLAN.md — Audio shell: useRecorder hook (getUserMedia + 30s auto-stop + cleanup) + 5-state TalkButton (96px disc + 132px ring)
- [x] 01A-04-PLAN.md — Chat surfaces: PallyPlaceholder (262×262 SVG) + ChatBubble + HistoryRow + HistorySheet + BottomNav (5 disabled tabs) + Toast
- [ ] 01A-05-PLAN.md — Main page assembly (app/page.tsx) + Playwright 402px E2E verification checkpoint
**Estimated effort**: 5 days (parallel with 1B/1C)
**UI hint**: yes

---

### Phase 1B: Pally Canvas2D + Python Engine Integration
**Goal**: Canvas2D Superformula로 렌더링된 Pally가 캐릭터 파라미터 변화에 부드럽게 반응하고, 응답 대기 중에는 생각 애니메이션을 보여준다. 또한 5축 Python 엔진 통합 방식이 ADR로 확정되어 1C가 그 결정을 따를 수 있게 한다.
**Depends on**: Phase 0
**Owner**: 김민주 (AI · 데이터)
**Requirements**: PALLY-01, PALLY-02, ENGINE-01 (engine integration portion)
**Success Criteria** (what must be TRUE):
  1. Python 엔진(`ai/analyzer.py` + `matrix_engine.py`) 통합 방식이 `docs/adr/0001-python-engine-integration.md`로 확정되어 있고 (FastAPI 직접 import / subprocess / 외부 Python 서비스 / TS 포팅 중 1개), 결정된 방식의 contract test에서 샘플 문장을 입력하면 5축 점수 + CHARACTER MATRIX가 JSON으로 반환된다. Next.js API route 구현은 본 phase 범위가 아니다
  2. Canvas2D 컴포넌트가 Pally를 Superformula 도형으로 렌더링하고, 60fps에 근접하게 동작한다 (모바일 브라우저 기준)
  3. `Formality` / `Energy` / `Intimacy` / `Humor` / `Curiosity` 값을 외부에서 주입하면 Pally의 형태·색·표정이 ~300ms 안에 부드럽게 트랜지션된다 (튐 없음)
  4. 데모용 컨트롤 페이지에서 슬라이더로 각 축을 움직여 시각 변화를 즉시 확인할 수 있다
  5. `frontend/lib/types/character.ts`에 본 phase에서 `Axes`(5축 점수)와 `CharacterParams`(Canvas2D에 주입되는 시각 파라미터) TS 타입을 추가하고 (`ai/analyzer.py`와 `matrix_engine.py`의 실제 출력 모양 기반), Canvas2D 컴포넌트가 그 `CharacterParams` 타입을 그대로 받아 렌더링한다 (별도 변환 레이어 없음). 이찬희(1A)는 본 phase 머지 후 같은 타입을 import해서 mock 데이터를 정밀화할 수 있다

**Plans**: TBD
**Estimated effort**: 5 days (parallel with 1A/1C)
**UI hint**: yes
**Task order**: ENGINE-01 ADR을 첫날 안에 끝낸다 (1C가 이 ADR을 critical input으로 기다림).

---

### Phase 1C: Voice + Inline Feedback Backend + Supabase Schema
**Goal**: 사용자의 음성 입력이 Vertex AI Gemini로 텍스트화 → 5축 분석 → 응답 생성 → TTS까지 흐르고, 대화 중 인라인 피드백이 `/api/chat` 응답에 포함된다. 또한 본 phase에서 사용할 Supabase `sessions`/`messages` 테이블 + `session_id` 기반 RLS를 정의한다.
**Depends on**: Phase 0 (scaffold + types + Supabase client). Phase 1B 전체 완료를 기다리지 않고, D+1에 확정되는 Python 엔진 통합 ADR만 coordination input으로 소비한다
**Owner**: 백은혜 (BE · AI)
**Requirements**: VOICE-01, VOICE-02, ENGINE-01, FB-01, FB-02, SESSION-01 (schema portion)
**LLM / 음성 벤더**: GCP 단일. STT = **Google Cloud Speech-to-Text**, 응답 생성 = **Gemini 2.5 Flash** via Vertex AI, TTS = **Google Cloud Text-to-Speech**, 인라인 한국어 힌트 = Gemini 2.5 Flash structured output. 백엔드는 FastAPI/Python이므로 Python Google Cloud client libraries를 사용한다 (Node `@google-cloud/*` 패키지 사용 안 함).
**Success Criteria** (what must be TRUE):
  1. Supabase에 `sessions` / `messages` 테이블이 `session_id` 기반 RLS와 함께 마이그레이션으로 생성되어 있고, 익명 세션 ID(클라이언트 UUID)로 insert/select가 정책 검사를 통과한다. `sessions` 테이블은 `character_name`(text, default `'Pally'`), `level`(text: A2 / B1 / B2 / C1, default `'B1'`), `created_at`, `ended_at?` 컬럼을 포함한다 (MVP에는 입력 UI가 없어서 기본값으로 채워지고, v2에서 사용자 입력으로 대체). `messages` 테이블은 `session_id`, `role`, `transcript`(text), `axes`(jsonb), `character`(jsonb), `created_at` 컬럼을 포함한다. `backend/lib/supabase.py`(service role server-only usage)도 본 phase에서 추가
  2. 사용자가 마이크로 영어 한 문장을 말하면 Google Cloud STT가 오디오를 텍스트화하고, 그 텍스트가 5축 분석 + CHARACTER MATRIX + EMA 보정(alpha=0.7 — 데모에서 캐릭터 변화를 빠르게 보이기 위해 기본값 0.3 대신 사용)을 거친 캐릭터 파라미터로 변환되어 응답 페이로드에 포함된다
  3. 같은 호출 흐름에서 Gemini 2.5 Flash가 영어 응답 텍스트를 생성하고, Google Cloud TTS가 그 텍스트를 음성으로 변환해 (스트리밍 또는 청크 단위로) 클라이언트에 도착한다
  4. `/api/chat` 호출 시 Gemini 프롬프트에 `character_name`(MVP 기본값 `'Pally'`, sessions row에서 조회), `level`(MVP 기본값 `'B1'` — 응답 난이도/어휘 조절용, sessions row에서 조회), `conversation_history`(같은 `session_id`의 이전 messages를 chronological order로) 가 전부 주입되어 응답이 (a) 그 이름으로 자신을 지칭하고 (b) 해당 레벨에 맞는 어휘/문장 길이로 나오고 (c) 직전 대화 맥락을 잇는 것이 출력으로 확인된다
  5. `/api/chat` 응답에는 별도 `/feedback` 화면 없이 메인 화면에 바로 표시할 수 있는 인라인 한국어 힌트/피드백 structured payload가 포함된다
  6. 모든 외부 API 호출은 서버 측에서만 이루어지며 (`service_role` / GCP 서비스 어카운트 JSON이 클라이언트 번들에 포함되지 않음), 호출 결과는 `messages` 테이블에 `axes`/`character` JSONB와 함께 저장된다
**Plans**: TBD
**Estimated effort**: 6 days (parallel with 1A/1B)
**Task order**: GCP setup(API 활성화 `speech` / `texttospeech` / `aiplatform` + `pally-backend` service account 생성 + 필요 role 바인딩 + JSON 키 발급 → base64로 Railway env `GOOGLE_APPLICATION_CREDENTIALS_JSON`에 등록. PM이 GCP project `capstone-puter8`을 만들고 전원을 Owner로 초대해뒀으므로 1C 담당이 본인 손으로 진행) → Supabase 마이그레이션(sessions/messages + character_name·level 컬럼, 기본값 포함) → Google Cloud STT 연동 → 1B ADR 도착 후 엔진 호출 → Gemini 2.5 Flash 응답 + Google Cloud TTS → Railway 배포.
**배포 (백엔드 — 백은혜)**: FastAPI 백엔드는 **Railway**에 배포. 필요 파일: `Procfile` (`web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`), `runtime.txt` (`python-3.11.0`). Railway 환경변수: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`. 배포 완료 후 Railway URL을 파트 A(이찬희)에 공유해 프론트에서 API 호출 주소로 사용.

---

### Phase 2: Integration & Demo Polish
**Goal**: 세 슬라이스가 하나의 흐름으로 합쳐져 Vercel(프론트) + Railway(백엔드) 배포 URL에서 모바일로 데모 가능한 상태가 된다. **최종 MVP 대화 흐름**: 사용자가 자유롭게 대화(턴 수 제한 없음) → 세션 종료 버튼 누름 → 누적된 axes 기반으로 Pally 최종 변화 표시.
**배포 구조**: 프론트엔드(Next.js) → Vercel, Root Directory = `frontend/` (이찬희), 백엔드(FastAPI) → Railway, Root Directory = `backend/` (백은혜)
**Depends on**: Phase 1A, Phase 1B, Phase 1C
**Owner**: 전원
**Requirements**: DEPLOY-01
**Success Criteria** (what must be TRUE):
  1. Vercel main 브랜치에 push하면 자동 배포되고, 배포 URL을 모바일 브라우저(~360px)에서 열어 메인 대화 화면(rec→발화→Pally 응답 음성 재생→인라인 힌트 표시) 전체 흐름이 끊김 없이 동작한다
  2. Phase 1A의 mock audio transport를 실제 Railway `/api/chat` 호출로 교체하고, 브라우저 녹음 Blob 업로드 + TTS 음성 재생이 iOS/Android 모바일 브라우저에서 검증된다
  3. 아래 3가지 데모 케이스 각각에 대해 Pally의 시각·말투가 눈에 띄게 다르게 반응한다 (rehearsal 1회 이상 완료)
     - casual: 짧고 친근한 발화 → Energy/Intimacy 상승, 더 밝고 가까운 Pally 반응
     - formal: 정중하고 구조화된 발화 → Formality 상승, 차분하고 명료한 Pally 반응
     - persona drift: 같은 세션 안에서 casual → formal 또는 formal → casual로 바뀌는 발화 → EMA 보정 후 Pally가 서서히 이동
  4. STT/응답/TTS 평균 지연이 데모 가능 수준이며, 에러 시에는 사용자에게 명시적 메시지가 표시된다 (silent fail 없음)
  5. 발표자가 데모 디바이스 + 백업 디바이스 2대에서 동일 흐름을 재현했고, 알려진 에지 케이스 목록이 문서화되어 있다
  6. **세션 종료 UX**: 대화 화면 상단 좌측 X 버튼을 누르면 현재 세션이 종료되고 새 채팅 화면(idle)으로 전환된다. 새 채팅 화면의 Pally는 방금 끝난 세션에서 누적된 최종 axes 상태를 반영한 모습으로 표시된다 (별도 결과 화면 없음 — 새 채팅 화면이 캐릭터 변화 확인 화면 역할). 턴 수 제한 없음 — 사용자가 원할 때 X 버튼으로 종료.
**Plans**: TBD
**Estimated effort**: 3 days (2026-06-04 → 2026-06-06, 데모 전일 버퍼 1일 포함)
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Foundation | 1/1 | Complete | 2026-05-21 |
| 1A. FE Screens & Audio Shell | 5/5 | Complete | 2026-05-26 |
| 1B. Pally Canvas2D + Engine ADR | 1/1 | Complete | 2026-05-25 |
| 1C. Voice + Inline Feedback BE + Schema | 1/1 | Complete | 2026-05-26 |
| 2. Integration & Demo Polish | 0/1 | In progress | - |

## Coverage Validation

**v1 requirements:** 11 total
**Mapped:** 11 / 11 ✓
**Orphans:** 0

| Requirement | Phase |
|-------------|-------|
| MAIN-01 | Phase 1A |
| VOICE-01 | Phase 1C |
| VOICE-02 | Phase 1C |
| ENGINE-01 | Phase 1B (ADR + integration) + Phase 1C (consumer) |
| PALLY-01 | Phase 1B |
| PALLY-02 | Phase 1B |
| CHAT-01 | Phase 1A |
| FB-01 | Phase 1C |
| FB-02 | Phase 1C |
| SESSION-01 | Phase 0 (types) + Phase 1C (schema/RLS) |
| DEPLOY-01 | Phase 2 |

## Parallelization Plan

```
        Phase 0 (Foundation, 0.5d, 이찬희)
                         |
        +----------------+----------------+
        |                |                |
   Phase 1A (5d)   Phase 1B (5d)    Phase 1C (6d)
   (이찬희)         (김민주)          (백은혜)
        |                |                |
        |          ADR D+1 ──────► 1C uses ADR
        |                |                |
        +----------------+----------------+
                         |
                Phase 2 (Integration, 3d, 전원)
                         |
                  2026-06-07 demo
```

**Timeline check:** 0.5 (Foundation) + 6 (longest parallel slice = 1C) + 3 (Integration) = **9.5 days of critical path**, leaving ~7.5 days of buffer in the 17-day window.

**Branch strategy:** Each parallel phase on its own feature branch (`gsd/phase-1a-fe-audio-shell`, `gsd/phase-1b-pally-canvas`, `gsd/phase-1c-voice-backend`), merged into `main` before Phase 2 starts.

---

*Roadmap created: 2026-05-21*
*Last updated: 2026-05-26 — **Phase 2 SC #6 추가**: 최종 MVP 흐름 확정 — 세션 종료 버튼 → 누적 axes 기반 Pally 최종 변화 표시 (턴 수 제한 없음). Earlier: **Phase 2 In Progress** (백은혜): Part-C 브랜치에 mock→real 전환 완료 (STT `/api/stt` 실호출, `/api/chat` 실호출, TTS base64 재생, `hint_ko` 수신). 데모 3케이스(casual/formal/persona drift) 로컬 E2E 9/9 PASS. 빌드·타입 검사 통과. 미커밋 변경사항 main 머지 후 Vercel 자동 배포 예정. Earlier: **Phase 1C complete** (백은혜): `/api/stt`+`/api/tts`+`/api/feedback`+`/api/chat` 구현 완료, Supabase sessions/messages 마이그레이션 실행, 인라인 한국어 힌트(`hint_ko`) structured payload, Railway 배포 Online (`https://capstone-production-e8c2.up.railway.app`), Vercel `NEXT_PUBLIC_BACKEND_URL` 환경변수 등록 완료. Earlier: **Phase 0 complete** (00-01 plan shipped, UAT 5/5, see 00-01-SUMMARY.md); ready for parallel 1A/1B/1C start. Earlier history: Phase 0 minimized, OpenAI replaced with GCP Vertex AI, Supabase schema moved to Phase 1C, Python engine ADR moved to Phase 1B; Phase 1A reduced to one main screen, `/feedback` UI removed from MVP, onboarding removed from MVP (character_name/level use defaults until v2); **monorepo 폴더 분리 명시**: Repo Layout 섹션 추가(`frontend/` + `backend/` + `ai/` 역할 + 작업 충돌 방지), Phase 0 SC를 `frontend/` 기준으로 재작성 (`cd frontend && npm run dev`, `frontend/lib/types/`, `frontend/lib/supabase/client.ts`, `frontend/.env.example`, `frontend/app/page.tsx`), 루트 `.env.example` 제거, Phase 2 배포 구조에 Vercel/Railway Root Directory 명시; **공유 타입 소유권 분담**: Phase 0은 1A에 필요한 최소 UI 타입(`Message`/`Session`)만 정의, `Axes`/`CharacterParams`는 Phase 1B(김민주)로 이관 — 엔진(`ai/analyzer.py` + `matrix_engine.py`)을 다루는 사람이 정확한 타입을 정의하기 위해. 백엔드(Python)는 자체 Pydantic 모델 사용, FE↔BE 공유 계약은 JSON wire format으로; **2026-05-21 Codex review 반영**: 오디오 책임을 1A mock audio shell + 1C backend contract + Phase 2 real wiring으로 분리, 1C가 1B 전체가 아닌 D+1 ADR만 소비하도록 병렬성 보존, 김민주 frontend 작업 영역을 `components/pally`, `app/dev/pally`, `lib/types/character.ts`로 명시, FastAPI/Python 백엔드 기준으로 GCP SDK/환경변수 정리; **2026-05-21 Phase 0 planning**: 00-01-PLAN.md 작성, Plans/Progress 컬럼 갱신*
