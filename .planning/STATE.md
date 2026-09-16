---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: "Phase 2 shipped — PR #61"
last_updated: "2026-09-06T11:24:20.077Z"
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 6
  completed_plans: 5
  percent: 83
---

# STATE: Pally — CharaShift MVP

**Last updated:** 2026-05-22 (Phase 1C complete; 1A/1B 진행 중)

## Project Reference

- **Core Value:** 내 영어 발화 스타일에 반응하는 Pally — 5축 분석 → Pally 시각·말투 변화 루프
- **Demo deadline:** 2026-06-07
- **Current focus:** Phase 01A — fe-screens-audio-shell
- **Planning source of truth:** `.planning/ROADMAP.md`
- **Synchronized planning docs:** `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`

## Current Position

Phase: 01A (fe-screens-audio-shell) — EXECUTING
Plan: 1 of 5
Phase 1C — COMPLETE (2026-05-22, 백은혜)

- **Milestone:** MVP v1 (June 7 demo)
- **Progress:** ▰▰▱▱▱ 2 / 5 phases complete (40%)

| Phase | Status | Notes |
|-------|--------|-------|
| 0. Foundation (Minimal) | Complete (2026-05-21) | Next.js scaffold + types + Supabase anon client + Tailwind/cn() + /api/health |
| 1A. FE Screens & Audio Shell | In progress | 이찬희 담당. 메인 화면 + rec/audio mock transport |
| 1B. Pally Canvas2D + Python Engine Integration | In progress | 김민주 담당. Pally renderer + character types + D+1 engine ADR |
| 1C. Voice + Inline Feedback Backend + Supabase Schema | **Complete (2026-05-22)** | 백은혜 담당. FastAPI 전 엔드포인트 + Supabase + Railway 배포 완료 |
| 2. Integration & Demo Polish | Not started | 1A + 1B + 1C 머지 후 시작 |

## Phase 1C 완료 상세 (2026-05-22)

### 구현

- `backend/main.py`: `/api/stt` (Google Cloud STT), `/api/tts` (Google Cloud TTS), `/api/feedback` (Gemini 2.5 Flash), `/api/chat` (5축→EMA→캐릭터→Gemini→TTS+한국어힌트)
- `backend/lib/supabase.py`: service-role 싱글톤 클라이언트
- `InlineHintKo` 모델: `hint_ko` 필드로 `/api/chat` 응답에 한국어 인라인 힌트 포함 (TTS와 asyncio.gather() 병렬)
- EMA alpha=0.7 (데모에서 캐릭터 변화 빠르게 보이기 위해)
- Supabase: session_id 기반 대화 이력 로드/저장, graceful degradation (미설정 시에도 동작)

### DB

- Supabase 마이그레이션 실행 완료: `sessions` + `messages` 테이블, RLS 활성화, `(session_id, created_at)` 인덱스
- `supabase/migrations/20260522000000_sessions_messages.sql`

### 배포

- **Railway**: `https://web-production-8dee5.up.railway.app` — Online
  - `/api/health` → `{"status":"ok"}` 확인
  - 환경변수 4개 등록: GOOGLE_AI_API_KEY, GOOGLE_CLOUD_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  - Root Directory 없음 (repo 전체 빌드, 루트 Procfile + requirements.txt 사용)
- **Vercel**: `capstone-eight-virid.vercel.app`
  - `NEXT_PUBLIC_BACKEND_URL=https://web-production-8dee5.up.railway.app` 등록 필요
  - 현재 배포 번들은 이전 Railway URL을 사용해 대화 요청이 실패함

### Phase 1C wire format (`/api/chat` 응답)

```json
{
  "status": "ok",
  "transcript": "사용자 발화",
  "reply": "Pally 응답",
  "tts_audio": "base64 MP3",
  "axes": {"Formality": 0, "Energy": 0, "Intimacy": 0, "Humor": 0, "Curiosity": 0},
  "character": {"tone_casual": 0, "energy_level": 0, "humor_level": 0},
  "character_labels": {"tone": "...", "energy": "...", "humor": "..."},
  "hint_ko": {"hint": "한국어 힌트", "expression": "올바른 영어 표현"}
}
```

## Performance Metrics

- **Requirements coverage:** 11/11 v1 requirements mapped ✓
- **Phase 1C SC 달성:** SC1~SC6 전부 ✓
- **Critical path 잔여:** 1A/1B(5d) + Integration(3d) = ~8d (데모까지 약 16일 남음)

## Accumulated Context

### Key Decisions Logged

- Monorepo split: `frontend/` (Vercel), `backend/` (Railway FastAPI), `ai/` (Python engine) — Accepted
- LLM/voice vendor: GCP only (Gemini 2.5 Flash + Google Cloud STT/TTS), no OpenAI — Accepted
- `/feedback` UI 없음; 피드백은 `/api/chat` 응답의 `hint_ko` inline payload — Accepted
- EMA alpha=0.7 (기본값 0.3 대신, 데모에서 캐릭터 변화를 빠르게 보이기 위해) — Accepted
- Railway: repo 전체를 빌드 컨텍스트로 사용 (root Procfile + root requirements.txt), Root Directory 설정 없음 — Accepted (ai/ 모듈 접근 필요)
- Vercel: Root Directory = `frontend/` (dashboard 설정), Hobby plan이므로 팀원 초대 불가 — Accepted
- Supabase: 백엔드 service-role key로만 접근 (RLS bypass), 프론트 직접 DB 접근 없음 — Accepted

### Outstanding Todos

- [x] Phase 0 — frontend scaffold
- [x] Phase 0 — minimal UI types (Message/Session)
- [x] Phase 0 — Supabase client/env
- [x] Phase 1C — `/api/stt`, `/api/tts`, `/api/feedback`, `/api/chat` 구현
- [x] Phase 1C — Supabase sessions/messages 마이그레이션 + RLS
- [x] Phase 1C — 인라인 한국어 힌트 (hint_ko)
- [x] Phase 1C — Railway 배포 (Online)
- [ ] Vercel `NEXT_PUBLIC_BACKEND_URL`을 현재 Railway URL로 동기화
- [ ] Phase 1A — 메인 대화 화면 + rec 버튼 + 오디오 UX shell (이찬희)
- [ ] Phase 1B — Python engine ADR (D+1 확정 필요, 김민주)
- [ ] Phase 1B — Canvas2D Pally renderer + 5축 파라미터 연동
- [ ] Phase 2 — mock transport → 실제 Railway `/api/chat` 교체
- [ ] Phase 2 — 모바일 실기기 E2E 검증 (demo device + backup)

### Blockers

- Phase 2 시작 전 1A + 1B 완료 필요
- Vercel 프로젝트 소유 계정/팀 권한이 없어 Production 환경변수 변경 대기

## Session Continuity

### Recent Sessions

| Date | Phase | Outcome |
|------|-------|---------|
| 2026-05-21 | Init | PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md 초기화 |
| 2026-05-21 | Roadmap review | GCP-only, Vercel/Railway split, /feedback UI 제거, 1A/1B/1C 병렬 구조 확정 |
| 2026-05-21 | Phase 0 build | 00-01 plan 실행, UAT 5/5 통과 |
| 2026-05-22 | Phase 1C build | `/api/chat` 구현, Supabase 연동, 인라인 한국어 힌트, Railway/Vercel 배포 완료 |

### Next Action

Phase 1A (이찬희) / Phase 1B (김민주) 완료 후 Phase 2 통합 시작.

- **이찬희**: 메인 대화 화면 + rec/audio UX shell → mock transport 완성 후 PR
- **김민주**: Pally Canvas2D renderer + D+1 engine ADR (`docs/adr/0001-python-engine-integration.md`) → 1C 엔진 연동 완료 확인
- **백은혜**: 1A/1B 완료 대기 → Phase 2 통합 참여 (mock transport → 실제 `/api/chat` 교체)

### Hand-off Notes (Phase 1C → Phase 1A/2)

- **Railway URL:** `https://web-production-8dee5.up.railway.app`
- **이찬희에게 전달할 env:**
  ```
  NEXT_PUBLIC_BACKEND_URL=https://web-production-8dee5.up.railway.app
  NEXT_PUBLIC_SUPABASE_URL=https://jxmdtrydtjlzglqwcofs.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```

- **`/api/chat` request 최소 필드:** `{ "utterance": "...", "session_id": "uuid", "level": "B1" }`
- **Supabase 테이블:** sessions (id, character_name, level, created_at), messages (id, session_id, role, transcript, axes, character, created_at)

---

*State initialized: 2026-05-21*
*Last synchronized: 2026-08-16 — Railway URL/Supabase project refs corrected; Vercel env sync pending project access.*
