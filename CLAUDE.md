# Pally — CharaShift MVP · Team CLAUDE.md
> 이 파일은 Claude Code(AI 코딩 도구)용 프로젝트 컨텍스트 파일입니다. 일반 방문자는 무시하세요.

> 사람 팀원 + AI 에이전트(Claude Code / Codex / Cursor) 공용 가이드.
> 현재 작업은 사용자의 최신 요청과 실제 코드·배포 상태를 기준으로 한다. `.planning/`의 과거 계획은 참고 자료이며 현재 작업 절차를 강제하지 않는다.
> **AGENTS.md는 이 파일의 symlink.** Codex도 동일 규칙.
> **공유 프로젝트 식별자는 §2, Railway·Vercel·Supabase 연결 방법은 §8 참조.**

## Codex bootstrap

- Codex는 repo root의 `AGENTS.md`를 먼저 읽는다.
- 이 repo에서는 `AGENTS.md -> CLAUDE.md` symlink를 유지한다. 즉 Codex가 `AGENTS.md`를 읽으면 항상 이 `CLAUDE.md` 전체 규칙을 읽는다.
- `AGENTS.md`를 별도 문서로 복사해 관리하지 않는다. 규칙 변경은 `CLAUDE.md`에만 한다.
- symlink가 깨졌거나 일반 파일로 바뀌었으면 작업 전에 `ln -sf CLAUDE.md AGENTS.md`로 복구한다.

---

## 0. 작업 시작

1. 이 파일과 작업에 관련된 기존 코드·문서를 읽는다.
2. `git status --short --branch`로 현재 브랜치와 미커밋 변경을 확인한다. 다른 사람의 변경을 덮어쓰지 않는다.
3. 필요한 경우 원격 변경을 확인하고 현재 작업과 충돌하지 않게 동기화한다. 세션 시작만을 이유로 `main`을 현재 브랜치에 합치거나 브랜치를 바꾸지 않는다.
4. 외부 서비스 작업이면 현재 세션의 도구·로그인·프로젝트 접근을 §8에 따라 확인한다. 과거 연결 성공 기록만으로 현재 권한을 가정하지 않는다.

---

## 1. 팀 & 작업 영역

| 사람 | 역할 | 주력 디렉토리 |
|------|------|--------------|
| 최윤서 | PM · 기획 · QA | `docs/`, 전체 검수 |
| 이찬희 | FE · 디자인 | `frontend/` (Pally 영역 제외) |
| 김민주 | AI · 데이터 | `ai/`, `frontend/components/pally/`, `frontend/app/dev/pally/`, `frontend/lib/types/character.ts` |
| 백은혜 | BE · AI | `backend/`, Supabase 마이그레이션 |
| 전원 | Integration | 전체 |

**충돌 회피 (중요):** 프론트엔드 작업 영역이 겹칠 수 있다.
- 이찬희 = 메인 화면, audio shell, 네비게이션
- 김민주 = Pally renderer, character types, dev 페이지
- 다른 영역 만져야 하면 → 팀 채널 공지 + 짧은 PR

---

## 2. 공유 리소스 ID

CLI와 MCP의 접근 범위는 로그인한 계정·토큰의 권한에 따라 달라진다. 아래 식별자로 **대상 프로젝트**를 확인한다. 식별자가 문서에 있다는 사실은 접근 권한을 뜻하지 않는다.

| 리소스 | 식별자 |
|--------|-------|
| Supabase project | `jxmdtrydtjlzglqwcofs` |
| GitHub repo | `puter8/capstone` |
| GCP project | `capstone-puter8` |
| KakaoPay test application | `Pally` / `A71A327B1FDF08B4FFBF` (sandbox recurring CID `TCSUBSCRIP`) |
| Vercel workspace / project | 기존 기록: `hunheay123s-projects` / `yourpally` → `https://capstone-eight-virid.vercel.app` (**현재 팀 접근 재확인 필요**, §8) |
| Railway workspace | `김민주's Projects` (`6d007f5d-ab0a-4c91-871f-357fe3681d8d`) |
| Railway project | `powerful-laughter` (`f9d8024f-96aa-4f83-b052-ed7c7fc1da4a`) |
| Railway environment / service | `production` / `web` |
| Railway deployment | `https://web-production-8dee5.up.railway.app` |

다른 본인 개인 계정 리소스와 혼동하지 않도록 위 ID로 명시. 새 리소스 추가 시 이 표를 먼저 업데이트하고 팀 채널 공지.

---

## 3. 작업 흐름

1. 요청 범위와 기존 구현을 확인한다. 비즈니스 로직이 모호하면 질문한다.
2. 기존 패턴을 따라 필요한 변경을 구현한다. 외부 API를 연동하는 코드는 §4의 실호출 확인을 먼저 한다.
3. 변경에 맞는 검증을 수행한다. 실제 서비스 흐름 검증은 §5를 따른다.
4. 변경 내용·검증 결과·남은 문제를 보고한다. 사용자 요청 없이 커밋·PR·머지·배포로 작업 범위를 확장하지 않는다.

스킬은 사용자가 명시적으로 요청한 경우에 사용한다. 특정 명령 실행이나 Plan / Build / Ship 세션 분리를 필수 절차로 두지 않는다.

---

## 4. 외부 API — 코드 전에 실호출

코드 한 줄 쓰기 전:

1. 실제 API 호출로 응답 구조/양/품질 확인 (Postman 역할)
2. 스키마만 맞추지 말 것. 기대 필드/데이터가 실제로 오는지
3. 후보 2-3개면 비교표(비용/품질/제한) → 사용자 승인
4. API key 없으면 deferred 금지 → 즉시 요청
5. 이 단계 건너뛰고 빌드 시작 **금지**

**음성·AI 연동:** Google Cloud STT/TTS/Gemini 2.5 Flash 각각 실제 호출 → latency, 응답 shape, 한국어 STT 인식률, TTS 자연도, structured output 안정성 확인 **후** 코드.

---

## 5. E2E 검증

사용자 흐름을 변경한 작업에는 아래 기준을 적용한다.

- 외부 API → 응답 → DB 저장 → UI 표시 **전체 흐름** 확인
- 실제 GCP 호출 + 실제 Supabase row (mock 아님)
- 타입체크 / 유닛테스트 통과만으로 검증 완료 처리 **금지**
- `/browse`(headed) 또는 Playwright MCP로 사용자가 실시간 확인 가능하게
- **모바일 폭 ~360px**에서 확인 (Pally MVP는 모바일 우선)
- 충분한 데이터로 (한 문장 말고 다양한 5축 분포)

---

## 6. Top 5 — 절대 지킨다

1. **외부 API는 코드 전에 실호출.** 스키마만 맞추고 넘어가지 않는다. (§4)
2. **"동작할 것이다"는 검증이 아니다.** 실제 출력 보여준다. (§5)
3. **에러 삼키지 않는다.** Empty `catch {}` 금지. `|| {}`, `?? []` 폴백 금지. 크래시가 침묵보다 낫다.
4. **`git add .` 금지.** 파일 개별 스테이징. `.env` / GCP JSON / Supabase service role 감지 시 즉시 중단.
5. **비즈니스 로직 추측 금지.** 모호하면 묻는다. auth / 결제 / 데이터 삭제는 확인 후 진행.

---

## 7. Code Rules

### TypeScript / Next.js (`frontend/`)

- TS strict. `any` 금지 (불가피하면 `// TODO: 사유`)
- 주석·변수명·함수명은 영어. 사용자 대화는 한국어
- 기본 Server Components. `'use client'`는 인터랙션/브라우저 API/훅 필요 시만
- 변이는 Server Actions. Route Handlers는 webhook/3rd-party만
- Tailwind + `cn()` 유틸 (문자열 연결 금지)
- Named export 선호. Default는 page/layout/route만
- 외부 입력(유저·API·URL params)은 **Zod로 boundary 검증**

### Python / FastAPI (`backend/`, `ai/`)

- Python 3.11. wire format은 **Pydantic v2**로 검증
- 루트 `ai/` import는 `sys.path` 조정 또는 `PYTHONPATH=.` (배포에도 반영)
- 동기 GCP client 기본. 비동기 필요하면 별도 ADR
- `backend/lib/supabase.py`는 service role — server only

### Error handling (공통)

- 에러 삼키지 않는다 (§6 #3 재강조)
- Server: 전체 에러 로그, Client: 안전한 메시지만
- Server Actions: `{ data, error }` 반환. 클라이언트로 throw 금지

### Supabase

- **모든 테이블 RLS 활성화. 예외 없음.**
- 정책은 `session_id` 기반 (익명 세션). `true` 정책 금지
- 마이그레이션 forward-only. 적용된 건 수정 금지, 새로 생성
- 클라이언트 = anon key, 서버 = service role
- 스키마 변경 후: `supabase gen types` → 타입 갱신 → 팀 채널 공지

### Git

- `git add .` **금지** (재강조)
- 커밋: imperative mood, 72자 이내, **왜(why)** 설명
- Branch: 현재 작업 브랜치를 우선 사용한다. 새 브랜치가 필요하면 작업 목적이 드러나는 이름을 사용한다.
- `--no-verify` / `--force` 금지 (명시 허락 시만)
- Production = `main`. feature → main PR 머지로만

---

## 8. Railway · Vercel · Supabase 연결과 배포

### 팀 공통 연결 원칙

- 팀원은 각자 계정으로 같은 Railway workspace/project, Vercel team/project, Supabase organization/project에 초대받고 초대를 수락한다. 유료 플랜 결제와 팀원 접근 권한·도구 인증은 별개다.
- CLI는 터미널 명령 도구, MCP는 AI 앱이 서비스 기능을 호출하는 연결 방식이다. 실제 권한은 연결된 계정·토큰에서 온다. CLI 로그인과 MCP 인증은 각각 확인한다.
- **기본 경로:** Railway는 실제 조회가 검증된 CLI, Vercel·Supabase는 현재 세션에서 호출 가능한 공식 MCP를 우선한다. MCP가 없으면 설치·인증된 CLI 또는 승인된 API 접근을 확인한다.
- 저장소 `.mcp.json`에는 Supabase·Vercel HTTP 서버가 등록돼 있다. Codex의 `~/.codex/config.toml` 등 AI 앱별 설정과 인증 상태도 별도로 확인한다. 저장소를 받았다는 사실만으로 모든 앱에 연결이 완료되지는 않는다.
- 연결 완료는 **설정 등록 → 현재 세션에 도구 로드 → 인증된 대상 프로젝트 조회 성공**까지 확인한 상태다. 설정에만 있으면 시작·인증 오류를 확인하고, 필요하면 앱/IDE를 재시작해 새 세션에서 다시 확인한다.
- 로그인·OAuth 승인은 팀원 각자의 환경에서 수행한다. 토큰·비밀번호·서버 키를 문서, 채팅, 커밋으로 공유하지 않는다. 환경변수는 필요한 이름과 설정 여부만 확인하고 전체 값을 출력하지 않는다.

### Railway — CLI

대상은 §2의 `powerful-laughter` / `production` / `web`이다. 처음 연결하거나 로그인이 만료되었을 때 `railway login`으로 본인 계정을 인증한다. `railway whoami`와 `railway list`로 계정과 프로젝트를 확인한다. [공식 CLI 안내](https://docs.railway.com/cli)

프로젝트를 로컬 폴더에 연결하지 않고도 아래처럼 대상을 명시해 조회할 수 있다.

```bash
railway logs --project f9d8024f-96aa-4f83-b052-ed7c7fc1da4a \
  --environment production --service web --lines 100
```

같은 폴더에서 반복해서 작업하려면 한 번 연결한다.

```bash
railway link --project f9d8024f-96aa-4f83-b052-ed7c7fc1da4a \
  --environment production --service web
railway status
railway logs --lines 100
railway logs --build --lines 100
railway logs --http --lines 100
```

- `No linked project found`는 로컬 폴더 연결이 없다는 뜻이다. 로그인 실패와 구분하고, 명시적 프로젝트 조회 또는 `railway link`를 사용한다.
- `railway status`는 연결된 프로젝트 정보 확인용이다. 앱 건강 상태는 배포 상태·런타임 로그·실제 요청으로 확인한다.
- 런타임·빌드·HTTP 로그 접근과 앱이 내부 상세 로그를 남기는지는 별개다. 코드가 출력하지 않은 단계별 정보는 Railway에서 조회할 수 없다.

### Vercel — MCP 우선, CLI 보조

- 공식 MCP 주소는 `https://mcp.vercel.com`이다. 사용하는 AI 앱에서 서버를 등록하고 각자 Vercel 계정으로 OAuth 인증한다. Claude Code는 `/mcp`에서 인증할 수 있다. [공식 MCP 안내](https://vercel.com/docs/agent-resources/vercel-mcp)
- MCP가 로드되면 우리 팀·프로젝트를 조회하고 배포 상태/로그 도구를 사용한다. 도구 이름은 현재 세션에 노출된 목록을 기준으로 한다.
- CLI를 사용할 때는 최초 `vercel login` 후 아래 읽기 명령으로 확인한다. `--scope`는 `vercel teams list`에서 확인한 실제 팀 slug를 사용한다. 아래 값은 기존 문서의 팀을 재확인하는 예시다.

```bash
vercel whoami
vercel teams list
vercel projects inspect yourpally --scope hunheay123s-projects
```

- `The specified scope does not exist`가 나오면 로그인 계정, 팀 초대 수락, 현재 팀 slug를 확인한다. 프로젝트를 새로 만들거나 다른 개인 프로젝트로 대체하지 않는다.
- `vercel deploy --prod` 수동 **금지**. Production은 Git 연동을 통해 배포한다. 환경변수 변경은 승인된 작업 범위에서 CLI 또는 dashboard로 수행한다.

### Supabase — 팀원별 MCP 인증

- 각자 Supabase 계정으로 MCP OAuth 인증을 하고, 프로젝트 `jxmdtrydtjlzglqwcofs`가 속한 organization의 접근을 승인한다. 일반적인 브라우저 인증에는 PAT를 직접 만들 필요가 없다. [공식 MCP 안내](https://supabase.com/docs/guides/ai-tools/mcp)
- 프로젝트 조회용 연결 URL: `https://mcp.supabase.com/mcp?project_ref=jxmdtrydtjlzglqwcofs&read_only=true`. 조회 작업에는 이 범위를 권장한다. 현재 저장소 설정은 기본 URL만 등록돼 있으므로 프로젝트 고정·읽기 전용 설정이 이미 적용됐다고 가정하지 않는다.
- 인증 후 현재 세션에서 테이블 목록 같은 최소 읽기 요청으로 접근을 검증한다. 데이터·스키마 변경은 별도로 승인된 범위와 연결 권한을 확인한다.
- MCP OAuth는 개발 도구 인증이다. 앱의 `SUPABASE_SERVICE_ROLE_KEY`, 프론트의 anon key와 구분한다. 서버 키를 MCP 로그인용으로 재사용하지 않는다.
- API 접근을 확인할 때는 URL이 우리 프로젝트인지 먼저 확인하고, 사용자 레코드를 반환하지 않는 최소 요청을 사용한다. 401/403을 연결 성공으로 처리하지 않는다.

### 최근 연결 확인 — 2026-09-13

아래는 이 저장소를 작업한 **개발 환경 한 곳**에서 확인한 결과다. 모든 팀원·운영 서버의 상태를 뜻하지 않는다. 다음 작업에서는 필요한 연결을 다시 확인한다.

| 서비스 | 실제 확인 결과 | 남은 확인 |
|--------|----------------|-----------|
| Railway | 프로젝트를 명시한 CLI 조회 성공. 런타임 77개, 빌드 20개, HTTP 20개 조회. HTTP host도 §2의 배포 URL과 일치 | 해당 폴더의 로컬 프로젝트 연결은 당시 없었음. 팀원별 로그인·접근은 별도 확인 |
| Vercel | MCP 등록은 확인했으나 현재 세션에 호출 도구 없음. CLI 로그인 성공, 기존 team scope 조회는 `The specified scope does not exist` | 현재 팀 slug·팀 초대·프로젝트 접근 및 MCP 인증/로드 확인 |
| Supabase | MCP 등록은 확인했으나 현재 세션에 호출 도구 없음. 프론트의 프로젝트 URL과 로컬 백엔드 서버 키를 사용한 데이터 없는 읽기 요청은 HTTP 401 | MCP 인증/로드 및 로컬 서버 키 유효성 확인. 운영 서버 연결 상태는 이 결과로 판단하지 않음 |

### 배포 및 확인

| Surface | Platform | 코드 위치 | Owner |
|---------|----------|-----------|-------|
| Frontend | **Vercel** (Git 자동 배포) | `frontend/` | 이찬희 |
| Backend | **Railway** (Git 자동 배포) | `backend/` | 백은혜 |

- Production 변경은 feature → `main` PR 머지로 진행한다. 머지 후 실제 배포 결과를 확인한다.
- Railway에는 루트 `Procfile`과 `backend/Procfile`이 있고 시작 모듈이 다르다. 서비스의 실제 Root Directory/Start Command와 루트 `ai/` import 가능 여부를 확인한다.
- Railway URL이 바뀌면 `frontend/.env.local`의 `NEXT_PUBLIC_BACKEND_URL`과 Vercel 환경변수를 승인된 범위에서 동기화한다.

1. Vercel MCP 또는 인증된 CLI에서 대상 배포의 READY 상태를 확인한다.
2. Railway 배포 상태·런타임 로그·실제 응답을 확인한다.
3. 모바일 브라우저에서 배포 URL을 열어 rec → Pally 응답 → DB 저장 흐름을 확인한다.
4. 실패 시 **로그 먼저 확인**. 추측 금지.

---

## 9. 문서 저장 경로

| 종류 | 경로 |
|------|------|
| ADR (아키텍처 결정) | `docs/adr/0001-*.md` (`TEMPLATE.md` 참조) |
| Plan 리뷰 / office-hours | `docs/plan/{YYYY-MM-DD}-{feature}-*.md` |
| Design system | `DESIGN.md` (루트) + `docs/design/` |
| Code 컨벤션 | `docs/code-convention.md` |
| 팀 그라운드룰 · 셋업 가이드 | `docs/shared/` |

`.planning/`와 `docs/_archive/`는 과거 계획·진행 기록을 확인할 때만 참고한다. 현재 코드·사용자 요청과 다르면 과거 작업 순서나 완료 상태를 그대로 적용하지 않는다.

ADR은 **세션당 최대 3개**. 나머지는 해당 작업 설명에 "Minor Decision:" 인라인.

---

## 10. NEVER / ALWAYS

### NEVER

- `mcp__claude-in-chrome__*` — `/browse` 또는 Playwright MCP 사용
- `git add .` — 개별 스테이징만
- `.env*`, GCP service account JSON, Supabase `service_role` 커밋
- `--no-verify`, `--force push` (명시 허락 시만)
- `vercel deploy --prod` 수동 (Git 연동 사용)
- Empty `catch {}`, silent fallback (`|| {}`, `?? []`)
- "동작할 것이다" 식 미검증 완료 보고
- README.md / ARCHITECTURE.md / 문서 자동 생성 (요청 없으면)
- 코드 · 커밋 메시지에 이모지
- 현재 task와 무관한 리팩토링
- 새 의존성 사전 보고 누락
- 비즈니스 로직 추측 (모호하면 묻기)
- `feedback` 별도 page 만들기 (MVP는 inline payload만)
- OpenAI / Whisper / GPT-4o 호출 (MVP는 GCP 단일)

### ALWAYS

- 작업 시작 시 현재 브랜치·미커밋 변경 확인 (§0)
- 기존 코드 패턴 매칭 (재발명 금지)
- 외부 API 코드 전 실호출 (§4)
- E2E는 실제 모바일 + 실제 데이터 (§5)
- auth / 결제 / 데이터 삭제는 사용자 확인 후
- 3회 실패 시 stop & reassess
- 작업 중 진행 상황을 짧게 보고 (silent 금지)
- 외부 서비스는 대상 프로젝트의 실제 조회 성공까지 확인 (§8)
- 디렉토리 경계 지키기 (§1)

---

## 11. AI 에이전트별 차이

- **Claude Code**: 기본. 이 파일 + `docs/code-convention.md` + `DESIGN.md`(있으면) 매 세션 로드
- **Codex CLI**: `AGENTS.md`(이 파일 symlink)를 읽음. 주로 `/codex review`, `/codex challenge`로 2차 검토. Claude가 이미 만든 패턴과 충돌하면 **Claude 패턴 우선** (일관성)
- **Cursor / 기타**: 같은 규칙. 도구별 차이 있으면 이 파일 우선

---

*Last updated: 2026-09-13 · 작업 지침 정리 및 Railway·Vercel·Supabase 연결 안내 반영*
