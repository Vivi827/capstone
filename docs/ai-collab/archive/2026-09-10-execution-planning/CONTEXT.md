# Pally 5-Axis ML Transition — Shared Context

> Claude Code와 Codex가 같은 전제에서 시작하기 위한 공용 컨텍스트 파일.
> 이 파일은 사실(fact)만 담는다. 진단/제안/의견은 `CLAUDE_REVIEW.md` / `CODEX_REVIEW.md` / `DECISION.md`에 쓴다.
> 갱신 시점: 2026-09-07 (gold-200 human review 완료 직후)

## 1. Pally 5축 시스템

- 5축: `Formality`, `Energy`, `Intimacy`, `Humor`, `Curiosity` (0-100 정수)
- CHARACTER MATRIX: `params = W(3x5) x axes + BIAS` -> `tone_casual` / `energy_level` / `humor_level`
- EMA 스무딩: `updated = alpha*new + (1-alpha)*prev`, `alpha=0.7` (데모용으로 표준값 0.3보다 크게 튜닝됨)
- 축은 대화창을 닫고 다시 들어갔을 때만 시각적으로 반영됨 (`revealAxes()` in `frontend/lib/hooks/usePally.ts`, `handleSessionEnd()` in `frontend/app/home/page.tsx`)

## 2. 분석기(Analyzer) 아키텍처

`ai/analyzers.py`, `get_axis_analyzer()` 팩토리, 환경변수 `PALLY_AXIS_ANALYZER=rule|ml|hybrid`.

- **RuleBasedAxisAnalyzer** — 현재 런타임 기본값 (`PALLY_AXIS_ANALYZER` 미설정 시 `rule`)
- **MLAxisAnalyzer** — TF-IDF + weighted k-NN (`ai/ml_baseline.py::TfidfKnnAxisRegressor`), 실패 시 rule로 fallback
- **HybridAxisAnalyzer** — 축마다 `round((rule_pred + ml_pred) / 2)`

**중요: 기본값은 여전히 `rule`이다. 이 문서 갱신 시점까지 코드에서 바뀐 적 없음.**

## 3. 학습 데이터 계보

- `data/axis_dataset_week2.jsonl` — 338개 시드 (LLM 3종 합성: Gemini 110 + GPT 99 + Claude 100 - 중복 1)
- 5개 실제 음성 코퍼스에서 표본 추출 후 **동일한 rubric 함수**로 draft 라벨링:
  - `scripts/draft_label_nict_jle_candidates.py::draft_axes()` — 이 함수가 NICT, AMI, CHiME-6, HCRC Map Task, Taskmaster-1 WoZ **5개 코퍼스 전부에 재사용됨** (각 코퍼스의 `*_label_candidates_*.jsonl`에 있는 `sample_bucket` 필드로 확인)
  - 코퍼스별 draft 산출물: `nict_jle_labeled_draft_600.jsonl`, `ami_labeled_draft_600.jsonl`, `chime6_labeled_draft_600.jsonl`, `hcrc_maptask_labeled_draft_500.jsonl`, `taskmaster1_woz_user_labeled_draft_500.jsonl`
  - NICT 600개는 사람 검수 완료(`nict_jle_labeled_human_600.jsonl`, "accepted-draft"), 나머지 코퍼스의 2,200개는 사람 검수 안 된 AI-draft 그대로
- 최종 실험용 학습셋: `data/fixtures/axis_dataset_combined_real_speech_experimental.jsonl` — 총 **3,137행** (338 시드 + 600 NICT accepted-draft + 2,200 AI-draft)
- 라이선스: NICT JLE(CC BY-SA 3.0), CHiME-6(CC BY-SA 4.0), Taskmaster-1(CC BY 4.0), AMI(CC BY 4.0) 확인 완료. **HCRC Map Task는 라이선스 충돌 미해결** (아카이브 페이지 NC-SA vs 현재 웹페이지 CC BY) — 상업적 학습셋에 포함 보류 상태.

## 4. Gold-200 (사람 검수 완료, 2026-09-07)

- 후보 풀: `data/fixtures/ml_transition_gold_candidates_600.jsonl` (600개, AMI/NICT/Taskmaster 각 200, 학습셋 3,137개와 텍스트 중복 없음, source group 분리됨)
- 그중 stratified 200개 추출: `data/fixtures/ml_transition_gold_stratified_candidates_200.jsonl` (NICT 68 / AMI 67 / Taskmaster 65, Energy x Curiosity 4분면 stratification)
- 사람 검수 결과: `data/fixtures/ml_transition_gold_blind_review_200.csv` -> 변환 후 `data/fixtures/ml_transition_gold_human_200.jsonl`
  - gold-0001~0100: 여러 검수자 평균(reviewer_id=`reviewer-avg`), 0.5 단위 점수
  - gold-0101~0200: 단일 검수자(reviewer_id=`reviewer-01`), 정수 점수
  - 200개 전부 `review_status=completed`, 원본 candidates jsonl과 utterance 텍스트/순서 1:1 대조 검증 완료(불일치 0건)
- 아직 사람 검수 안 된 나머지: 600 - 200 = **400개**가 gold candidate reservoir에 남아 있음 (미래 최종 blind test 후보)

## 5. 현재 성능 수치 (전부 실제로 실행해서 얻은 값, 추정치 아님)

### 5-1. 학습셋 내부 평가 (순환평가, in-domain — 실제 gold 아님)

`ai/evaluate_axis_analyzers.py --mode leave-one-out` / `--mode source-group-holdout` (3,137개 자체 내에서):

| Evaluation | ML MAE | Hybrid MAE | ML Spearman | Hybrid Spearman |
|---|---:|---:|---:|---:|
| Leave-one-out | 7.55 | 7.95 | 0.44 | 0.45 |
| Source-group holdout | 7.62 | 7.86 | 0.45 | 0.45 |

### 5-2. Gold-200 held-out 평가 (진짜 human label, 절대 학습에 안 씀)

`ai/evaluate_axis_analyzers.py --mode gold-holdout` (3,137개로 학습 -> gold-200으로 평가):

| | rule | ML | hybrid |
|---|---:|---:|---:|
| avg MAE | 14.54 | 14.90 | **14.26** |
| avg Spearman | 0.37 | 0.28 | **0.39** |

축별 Spearman (rule / ML / hybrid):

| Axis | rule | ML | hybrid |
|---|---:|---:|---:|
| Formality | 0.16 | 0.46 | 0.39 |
| Energy | 0.45 | 0.03 | 0.29 |
| Intimacy | 0.39 | 0.27 | 0.45 |
| Humor | 0.09 | -0.04 | 0.05 |
| Curiosity | 0.77 | 0.68 | 0.76 |

### 5-3. Teacher(AI-draft rubric) vs Human gold 직접 진단 (신규, 사람 검수 0개 추가 소요)

`scripts/diagnose_gold_vs_ai_draft.py` — `draft_axes()`를 gold-200 utterance에 그대로 적용해서 human label과 비교 (gold 후보는 `sample_bucket`이 없어 rubric이 기본 bucket으로 폴백됨 — 상수 오프셋만 영향, 순위에는 영향 없음):

| Axis | Spearman | MAE | bias | human_sd | draft_sd | sd_ratio |
|---|---:|---:|---:|---:|---:|---:|
| Formality | 0.49 | 10.68 | +7.47 | 13.16 | 7.11 | 0.54 |
| Energy | 0.22 | 12.51 | -8.64 | 13.64 | 6.11 | 0.45 |
| Intimacy | 0.09 | 28.91 | +27.39 | 17.03 | 4.69 | 0.28 |
| Humor | 0.00 | 6.44 | +4.64 | 6.35 | 0.78 | 0.12 |
| Curiosity | 0.83 | 25.79 | -6.87 | 37.06 | 9.30 | 0.25 |

Threshold=50 high/low confusion (전체 표는 `scripts/diagnose_gold_vs_ai_draft.py` 실행 결과 참고):
- Energy: draft가 threshold 50을 **넘은 적이 0번** (`human_high_draft_high=0`, `human_low_draft_high=0`)
- Humor: draft 값이 200개 중 199개가 동일값(6) — p10~p90 전부 6

## 6. ML Acceptance Gate (전환 조건, `docs/ml-transition-plan.md`에 정의됨)

`PALLY_AXIS_ANALYZER=ml`로 기본값을 바꾸려면 frozen human-reviewed, source-group-held-out test에서 아래 4개 전부 만족해야 함:

1. ML 평균 MAE가 hybrid보다 0.20 이상 나쁘지 않을 것
2. ML 평균 Spearman이 hybrid 이상일 것
3. 어떤 축도 hybrid보다 0.03 이상 Spearman이 나쁘지 않을 것
4. held-out 그룹을 바꿔도 결과가 재현될 것

**현재 gold-200 결과는 1, 2, 3 전부 탈락. 4번은 아직 검증 불가(gold 세트가 하나뿐).**

## 7. 미해결/보류 사항

- `data/fixtures/ml_transition_train_active_ec_review_120.csv` — Energy/Curiosity 120개 검수용으로 이미 추출됨, 아직 `pending` (검수 시작 안 함)
- HCRC Map Task 라이선스 문의 이메일 미발송
- gold-200 남은 400개 후보는 아직 손대지 않음 (미래 최종 blind test용으로 보존 중)
- 부분 라벨(5축 중 일부만 있는 row) 학습 지원이 `ai/ml_baseline.py`에 아직 없음

## 8. 제약 조건 (반드시 지킬 것)

- `PALLY_AXIS_ANALYZER` 기본값을 `ml`로 바꾸는 코드 변경은 4개 gate 기준을 전부 통과하고 **사용자(백은혜) 명시적 확인 후에만** 진행
- gold-200/train-120 검수 라벨을 AI가 대신 생성하거나 추측해서 채우지 않는다 (라벨 위조 금지)
- 5축 중 검수 안 된 축을 다른 축 draft 값으로 채우지 않는다 (partial label을 partial 그대로 유지)

## 9. 역할 분리 (Round 1-3 실제 협업으로 검증됨, 2026-09-07)

| | Claude Code | Codex |
|---|---|---|
| 담당 | repo 탐색, 실제 코드/스크립트 실행, 데이터 검증, 코드 수정, 테스트, 최종 synthesis | 방법론적 비판, 통계적 오류/leakage 탐지, 실험 설계 검증, 결과 해석 비평 |
| 이번 라운드 실적 | teacher rubric(`draft_axes()`) vs human gold 진단 스크립트 작성 및 실행, ML acceptance gate 평가 확장 | source_group 누수(72/200), reviewer/source 교란, `sample_bucket` 폴백의 축별 비대칭 영향, Energy/Humor 학습 데이터 부족을 "구조적 한계"로 과장한 부분 등 6개 지적 — **전부 실제 데이터 검증 결과 정확했음** |
| 코드 수정 권한 | O (review 라운드에서는 지정된 파일만) | X (review만, 코드/데이터 수정 안 함) |
| 이번 라운드에서 확인된 것 | Claude 혼자였다면 "Curiosity는 이미 괜찮다", "Energy는 rubric에 구조적 천장이 있다", "Humor는 teacher가 무정보"라고 과신했을 결론을, Codex의 비판이 정확히 교정함 (`DECISION.md` DISAGREED 절 참고) | |

**결론: 이 역할 분리는 1회차 실전에서 이미 가치를 증명했다** — Codex 없이 Claude 단독 진단(`CLAUDE_REVIEW.md`)만 있었다면 성급한 결론(특히 Curiosity/Energy/Humor에 대한 과잉 확신)을 그대로 `DECISION.md`에 반영할 뻔했다.

## 10. 오케스트레이터 (`scripts/dual_ai_review.py`)

Round 1/2/3 순서를 자동으로 감지해서 `claude -p ...` / `codex exec ...`를 **순차적으로만**
호출하는 스크립트. 두 에이전트를 동시에(병렬로) 호출하지 않는 것이 이 스크립트가 지키는
유일한 하드 룰 — 같은 `docs/ai-collab/*.md` 파일에 동시에 쓰다가 충돌하는 걸 막기 위함.

- `python scripts/dual_ai_review.py --status` — 각 라운드 완료 여부만 확인
- `python scripts/dual_ai_review.py --dry-run` — 실행할 명령만 출력, 실제 호출 안 함
- `python scripts/dual_ai_review.py` — 아직 안 끝난 라운드부터 순서대로 실행
- `python scripts/dual_ai_review.py --step codex_round2` — 특정 라운드만 강제 재실행

각 스텝은 대상 에이전트에게 `CONTEXT.md`와 `CURRENT_TASK.md`를 읽고 그 안의 라운드 지시를
따르라고만 시킨다 — **과제 내용 자체는 스크립트에 하드코딩돼 있지 않다.** 다음 리서치
사이클을 돌리려면 `CURRENT_TASK.md`만 갱신하고 이 스크립트를 다시 실행하면 된다.

실행 후 대상 파일(`CLAUDE_REVIEW.md`/`CODEX_REVIEW.md`/`DECISION.md`)의 해시가 실제로
바뀌었는지 확인하고, 안 바뀌었으면 다음 스텝으로 안 넘어가고 즉시 중단한다 (에이전트가
아무것도 안 쓰고 조용히 끝나는 실패를 막기 위함). 모든 실행 기록은
`docs/ai-collab/runs.log`에 타임스탬프/명령/성공여부로 누적 기록된다.

**주의:** 실제로(dry-run 없이) 실행하면 별도의 headless Claude Code 세션과 Codex 세션이
진짜로 API를 호출하고 과금이 발생하며, repo 파일을 실제로 수정한다 (지정된 review 파일만
쓰도록 프롬프트에 명시했지만, `--allowedTools`/`-s workspace-write`가 도구 접근 범위를
제한할 뿐 100% 보장은 아니다). git commit/push/reset 계열 명령은 프롬프트에서 명시적으로
금지했지만, 실제 라이브 실행 전에 결과를 검토하는 습관을 유지할 것.

## 11. 핵심 파일 경로

| 용도 | 경로 |
|---|---|
| 분석기 구현 | `ai/analyzers.py` |
| ML baseline | `ai/ml_baseline.py` |
| 평가 스크립트 (leave-one-out / source-group-holdout / gold-holdout) | `ai/evaluate_axis_analyzers.py` |
| Teacher vs Human 진단 스크립트 | `scripts/diagnose_gold_vs_ai_draft.py` |
| AI-draft teacher rubric (5개 코퍼스 공용) | `scripts/draft_label_nict_jle_candidates.py` |
| gold-200 원본/검수/변환 | `data/fixtures/ml_transition_gold_stratified_candidates_200.jsonl`, `ml_transition_gold_blind_review_200.csv`, `ml_transition_gold_human_200.jsonl` |
| train-120 (pending) | `data/fixtures/ml_transition_train_active_ec_review_120.csv` |
| 실험용 결합 학습셋 | `data/fixtures/axis_dataset_combined_real_speech_experimental.jsonl` |
| ML 전환 계획/gate 정의 | `docs/ml-transition-plan.md` |
