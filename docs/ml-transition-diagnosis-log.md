# ML 전환 진단 로그 — Cycle 4 / 4b (2026-09-10 ~ 09-11)

> 이 문서는 "사람 라벨링을 최소화하면서 축 분석기를 ML로 전환할 수 있는가"를
> 판단하기 위한 진단 전 과정을 기록한다. Claude ↔ Codex 논의, 각 실험의
> 방법·결과·해석, 도중에 정정된 주장, 미결정 사항을 시간순으로 남긴다.
>
> - 권위 문서: `docs/ml-transition-contract.md` (평가·검수 계약).
> - 실행 계획: `docs/ai-collab/DECISION.md` (cycle 4b).
> - 이 로그는 "왜 그렇게 결정했는가"의 근거 기록이다.

---

## 0. 배경과 목표

### 프로젝트 맥락

Pally는 사용자 발화를 5축(Formality·Energy·Intimacy·Humor·Curiosity, 각 0~100)으로
수치화한다. 현재 런타임 기본값은 규칙 기반(`PALLY_AXIS_ANALYZER=rule`). 후보는
세 가지:

- `rule` — 손으로 만든 규칙/키워드 분석기
- `ml` — TF-IDF + 가중 k-NN 회귀 (`TfidfKnnAxisRegressor`)
- `hybrid` — rule과 ml의 축별 평균

`data/fixtures/ml_transition_gold_human_200.jsonl` (gold-200) 사람 검수 결과,
ML은 규칙·hybrid보다 뒤진다 (rule Spearman 0.37 / ML 0.28 / hybrid 0.39). ML 전환의
근거를 만들려면 왜 뒤지는지부터 규명해야 한다.

### 사용자가 고정한 목표 (우선순위)

1. **사람 라벨링 작업 최소화**
2. **ML로 전환** (런타임 분석기로)
3. **모든 과정에 타당한 근거**

### 표준 제약 (위반 금지)

- `PALLY_AXIS_ANALYZER` 기본값을 `rule`에서 바꾸지 않는다 (gate 통과 + 명시 승인 전까지).
- 사람 검수 라벨을 조작/합성하지 않는다. 미검수 축을 AI 초안으로 채우지 않는다.
- ML acceptance gate와 그 목표를 사용자 명시 승인 없이 바꾸지 않는다.
- 예약 최종 test pool(`ml_transition_reserved_final_test_pool.jsonl`)은 모델·분석
  계획이 확정될 때까지 열지 않는다.
- 새 런타임 의존성 금지. (openpyxl은 검수 워크북 생성용 dev 도구 의존성.)

---

## 1. Cycle 4 — 라벨 전략 논의 (2026-09-10)

### 1.1 발단: Codex의 권고

Calibration의 필요성을 설명하던 중, Claude가 "ML 점수가 낮으니 수백~수천 건의 사람
라벨링이 필요하다"고 서술했다. Codex가 이를 반박:

- ML이 낮다는 사실만으로 대량 사람 라벨링을 결론낼 수 없다. **모델 구조 / 기존 AI
  라벨 편향 / 입력 정보 부족** 중 무엇이 문제인지 먼저 구분해야 한다.
- 자동 라벨링(LLM 자동 라벨 → 소형 모델 학습, 약지도 학습, 선택적 사람 검수) 대안이
  있다. 다만 "AI와의 일치"가 "사람과의 일치"를 뜻하지 않는다.
- 권장 순서: (1) 새 라벨 없이 개선 가능한 부분 확인 → (2) 자동 라벨을 학습에 활용
  + 편향 확인 → (3) first-40 같은 작은 배치로 사람 검수 시작, 전후 효과 비교 →
  (4) 독립 사람 평가셋은 유지.

### 1.2 Claude Round 1 (독립 응답)

`docs/ai-collab/CLAUDE_REVIEW.md` (cycle 4). 요지:

- **과장 철회.** "ML 낮음 → 대량 라벨링" 서술 철회. 원인 진단 먼저.
- 합의점: 대량 라벨링 미확정, 새 라벨 없는 개선 먼저, AI 합의는 정답 아님, 독립
  사람 평가셋 유지 — 모두 이미 `docs/ml-transition-contract.md` §11-12에 있음.
- 이견:
  - "자동 라벨링"은 새 아이디어가 아니라 **현 상태** (3,137행 중 2,199행이
    `ai_draft_needs_human_review`). 그리고 그 현 상태가 dev-200에서 지고 있음.
    → 유용한 버전은 "자동화하되 더 잘, 그리고 외부 기준(사람)과 편향 측정".
  - first-40은 active-learning 선택이라 "어려운 사례에서 사람 라벨이 돕나"만
    측정 (일반적 주장 아님).
  - 최소 경로에서도 평가셋은 검수자 2명 이상 필요 (모델 오차 vs 라벨 노이즈 분리).
  - "교사 재현" 목표 전환은 **사용자 결정** (gate·평가지표 자체가 바뀜).

### 1.3 Codex Round 2 (적대적 방법론 검토)

`docs/ai-collab/CODEX_REVIEW.md` (cycle 4). 실제 저장소 데이터로 검증한 지적:

| # | 지적 | 검증 |
|---|---|---|
| 1 | **dev-200이 깨끗한 holdout이 아님** — 200행 중 100행이 학습 canonical 그룹과 겹침 (AMI 65 / NICT 28 / Taskmaster 7). `evaluate_axis_analyzers.py --mode gold-holdout`은 그룹 제외 미강제. | Codex 재현, 이후 Claude도 재확인 |
| 2 | **338 / 938 / 3,137 학습 비교로는 teacher vs capacity 구분 불가.** Codex가 직접 실행: 3,137 → dev MAE 14.90/rho 0.28, 338 → 17.07/0.32, 938 → 15.46/0.29. AI-draft 제거하면 rank 약간↑ MAE↓, non-overlap 슬라이스에서 방향 뒤집힘. CI 없음. | Codex 실행 |
| 3 | **calibration 샘플러 버그.** `_take_by_hash`는 행 해시로 정렬 → 큰 그룹 편애. residual arm의 `rng.shuffle`은 무효 (`_take_by_hash`가 다시 정렬). | Codex 코드 검토 |
| 4 | **`0.9^n = 95%` 확률 주장이 틀림.** 고정 A/B 쌍 기준으로는 출처당 `1-0.9^10 = 65%`, 세 출처 동시 ~28%. | Codex 계산 |
| 5 | **채점 예시가 AI 라벨에 앵커됨.** 워크북 예시 8개 중 6개가 seed 데이터셋 점수를 정확히 복제, seed 라벨은 gemini/gpt/claude-assisted. | Codex 대조 |

### 1.4 DECISION (cycle 4)

`git show c9f4791:docs/ai-collab/DECISION.md`. 핵심:

- **calibration 48 → 30문항 × 2명** (평가 담당 2명). 샘플러·확률문구·예시 수정 후.
- **2주 진단 우선 순서**: 측정+교사충실도+표현 → 작은 calibration + rubric 고정 +
  Flash-Lite 교사 1회 비교 → bounded first-40 → 판정.
- **사용자 결정 2건**: (U1) 사람 gold gate 유지 vs "교사 재현"으로 목표 변경,
  (U2) 4×90 calibration 유지 vs 재설계.

### 1.5 사용자 결정 (2026-09-10)

- **U1: 진단 결과 보고 결정.** 그때까지 사람 gold gate 유지가 기본.
- **U2: calibration 보류.** 4×90 파일(커밋 `fce9cea`)은 팀 배포 안 함. Days 3-5에
  30×2 재설계.

> 참고: cycle 4 이전에 이미 만든 Phase 2 산출물 — calibration 90행(30/출처),
> pilot 54행, first40 40행 후보 + 빈 slot CSV, 4명용 채점 워크북. 이들은
> 커밋됐으나 **채점 배포 보류** 상태.

---

## 2. Cycle 4b — Day별 진단 (2026-09-11)

공통 원칙:
- 모든 비교는 **dev-200 canonical 그룹 전부 제거한 공통 학습셋** (NICT provenance는
  `source_line`으로 복구 후 제거).
- dev-200 라벨은 평가에만 사용, 학습 금지.
- 예약 pool 미개봉.
- 학습셋 SHA-256 `23051000c3c2c4e0c38a876de61973d156188ef151faad69fca18caf20ddc1e9`,
  dev-200 SHA-256 `7dedff3225fb5161ef08ca9651acd93bbe01f6f87ac6343086905e98f8d0c7f7`.

### Day 1 — dev-200 그룹 누출 규모 측정

**스크립트**: `scripts/diagnose_dev200_group_purge.py` (커밋 `219ae06`)

**방법**: NICT 600행 전부 `source_line`으로 원본 join(600/600 발화 일치) → dev-200의
161개 canonical 그룹 식별 → 학습셋에서 그 그룹에 속한 행 전부 제거 (197행: AMI 158 /
NICT 33 / Taskmaster 6) → rule/ML/hybrid를 full 학습 vs purged 학습으로 dev-200에서
비교.

**결과 (bigram, k=5)**:

| 학습 | dev-200 MAE | dev-200 평균 rho |
|---|---:|---:|
| full 3,137 | 14.897 | 0.280 |
| dev-group-purged 2,940 | 14.966 | 0.284 |
| (rule, 학습 무관) | 14.535 | 0.372 |

overlap-100 vs clean-100 분리:

| slice | rule rho | ML rho | hybrid rho | ML MAE |
|---|---:|---:|---:|---:|
| overlap-100 (AMI 65) | 0.274 | 0.268 | 0.330 | 13.80 |
| clean-100 (Taskmaster 58) | 0.385 | 0.282 | 0.388 | 16.14 |

출처별 (purged bigram):

| 출처 | n | rule rho | ML rho | hybrid rho |
|---|---:|---:|---:|---:|
| AMI | 67 | 0.291 | 0.130 | 0.272 |
| NICT | 68 | 0.292 | 0.355 | 0.368 |
| Taskmaster | 65 | 0.345 | 0.216 | 0.330 |

검수자별:
- reviewer-avg (AMI 67 / NICT 33): rule rho 0.203 / ML 0.247 / hybrid 0.272
- reviewer-01 (Taskmaster 65 / NICT 35): rule rho 0.395 / ML 0.304 / hybrid 0.397, **Humor NA**

**Claude Day 1 해석 (일부 나중에 정정됨)**:
1. 누출은 실재(100행)하나 집계 영향은 작음 (<0.07 MAE, <0.01 rho) → ML 약세의
   원인이 아님. ✅ 유지
2. clean 슬라이스에서 ML은 rule·hybrid보다 뒤짐. ⚠️ 부분 정정 (아래 §3)
3. ML 약세가 출처별로 다름, "NICT 스타일 과적합". ❌ 정정 (아래 §3)
4. Humor는 Taskmaster 65행 + reviewer-01 100행에서 상수 → dev 절반에서 측정 불가. ✅ 유지

### Day 2 — 교사 충실도 vs 학생 용량

**스크립트**: `scripts/diagnose_teacher_fidelity.py` (커밋 `4cb9ec8`)

**질문**: ML이 dev에서 약한 게 (a) 감독 신호(약한 라벨)가 천장이라서인가, 아니면
(b) k-NN이 자기 학습 신호조차 재현 못 해서인가?

**방법**: purged 학습셋 내부에서 provenance 복구한 canonical 그룹으로 group-held-out
split (seed `teacher-fidelity-20260911`, 그룹의 ~1/5 hold). 학생(k-NN)을 train
부분에 fit → held-out 부분 예측 → **저장된 약한 라벨**과 일치도. 별도로 `draft_axes`를
같은 held-out 부분에 실행 → 저장 라벨과 일치도.

**결과 (held-out, bigram)**:

| slice | student vs stored | draft_axes vs stored | student vs draft_axes |
|---|---|---|---|
| held-out ALL (n=652) | MAE 7.64 / rho 0.402 | MAE 1.85 / rho 0.874 | MAE 7.20 / rho 0.369 |
| AMI (n=103) | MAE 7.13 / rho 0.327 | **MAE 0.00 / rho 1.000** | MAE 7.13 / rho 0.327 |
| CHiME (n=143) | rho 0.293 | **MAE 0.00 / rho 1.000** | rho 0.293 |
| HCRC (n=110) | rho 0.269 | **MAE 0.00 / rho 1.000** | rho 0.269 |
| Taskmaster (n=110) | rho 0.459 | **MAE 0.00 / rho 1.000** | rho 0.459 |
| NICT (n=115) | rho 0.539 | MAE 0.80 / rho 0.981 | rho 0.541 |

**해석**:
- **저장된 학습 라벨 = `draft_axes` 출력 그대로** (AMI/CHiME/HCRC/Taskmaster는
  rho 1.000, MAE 0.000). "교사"는 결정론적 어휘/버킷 규칙 함수이고, 그게 곧 학습 타깃.
- NICT는 567행 중 208행이 Formality/Energy에서만 다름 (평균 |Δ| F 2.57 / E 1.10),
  `codex_accept_draft_per_user` 편집분.
- **학생(k-NN)은 그 결정론적 교사조차 rho ~0.33(AMI) ~ 0.54(NICT)로만 재현.**
  TF-IDF k-NN은 어휘 함수를 rho 0.4~0.5 이상으로 복원 못 함.
- 결론: dev-200 ML 약세는 **약한 교사 × 손실 큰 학생**. "같은 라벨 더 자동화"도
  "표현 수정"도 단독으로는 hybrid(0.39)를 못 넘김.

> Codex Round 2(cycle 4b)가 이 해석의 "rho ≤ 0.30이면 supervision ceiling" 같은
> 사후 경계를 근거 없다고 지적. 스크립트 해석 문구를 "방향성만, 판정 아님"으로 수정.

### Day 3 — STT 입력 train/serve 불일치

**스크립트**: `scripts/diagnose_stt_input_skew.py` (커밋 `bba5c02`)

**발견 (코드 검증)**: `backend/main.py`의 두 STT 호출부 모두
`"enableAutomaticPunctuation": False`. 반환 transcript는 `.strip()`만 하고 바로
`_analyze_axes(transcript)`로 전달. → **프로덕션 축 입력에는 구두점이 없다.**
dev-200과 학습 코퍼스는 구두점·대문자가 있음. rule과 `draft_axes`는 `?`(Curiosity),
`!`(Energy), 대문자 강조에 의존.

**방법**: dev-200을 세 조건으로 rule/ML/hybrid 재실행 (purged 학습).

| 조건 | rule rho | ML rho | hybrid rho |
|---|---:|---:|---:|
| as-is (현재 eval) | 0.372 | 0.284 | 0.391 |
| 구두점 제거 (STT 유사) | 0.317 | 0.274 | 0.378 |
| 구두점 제거 + 소문자 | 0.322 | 0.274 | 0.380 |

- rule은 프로덕션 유사 입력에서 **rho −0.055 / MAE +0.95** 손실 (dev 70/200행이 `?`
  보유, STT가 제거).
- ML은 거의 평탄 (−0.010). hybrid는 ML이 완충.
- hybrid−rule 격차: as-is 0.019 → STT 유사 0.061 로 확대.
- 소문자는 구두점 제거 대비 거의 영향 없음 (`_tokenize()`가 이미 `lower()`).
- `!`는 dev 200행 중 1행 → Energy의 `!` 신호는 여기서 무의미.

**해석**: 현재 dev-200 eval은 순수 rule 경로를 프로덕션 대비 과대평가한다. 순수 ML을
이기게 만들지는 않지만(0.274 vs hybrid 0.378), **서브타임에서 순수 rule에 반대하는
구체적 근거**.

> Codex 후속: 실제 접근 가능한 STT 샘플로 대문자 보존/구두점 완전 부재를 확인할 것.
> 이번 검토에서 외부 STT 호출은 안 함.

### Day 4 — k/ngram 탐색

**커밋**: `255a332`. dev-200, purged 학습, k ∈ {3,5,7,9,15} × {1,2,3}-gram.

| config | ML MAE / rho | hybrid MAE / rho |
|---|---|---|
| k=5 bigram (Day 1 기준) | 14.97 / 0.284 | 14.28 / 0.391 |
| k=7 unigram | 15.15 / 0.324 | 14.52 / 0.412 |
| k=15 bigram | 15.08 / 0.350 | 14.49 / 0.420 |
| rule | 14.54 / 0.372 | — |

- **순수 ML은 어떤 설정에서도 rule(0.372)을 못 넘음** (최고 0.350).
- hybrid는 k=7~15에서 0.41~0.42로 rule 확실히 상회.
- TF-IDF k-NN 계열 내부 튜닝으로는 현재 `draft_axes` 라벨로 순수 ML을 경쟁력 있게
  만들 수 없음.

### Day 5 — Flash-Lite 대안 교사 비교

**스크립트**: `scripts/flash_lite_axis_teacher.py` (커밋 `941b2de`),
`scripts/compare_flash_lite_vs_draft_teacher.py` (커밋 `fdb7792`)

**Preflight** (사용자 승인 후 실제 `gemini-2.5-flash-lite` 호출): 고정 프로토콜 —
현재 발화만 인용 데이터로, 축별 0-33/34-66/67-100 앵커를 시스템 프롬프트에,
gold/출처/버킷/타 모델 출력 미제공, temperature 0, thinkingBudget 0, responseSchema
강제, 잘못된 출력은 거부(back-fill 안 함). 테스트 3문장 모두 유효한 5축 정수 + evidence,
latency ~0.9s. API 키는 `backend/.env`(gitignore)에서 읽고 출력 안 함.

**dev-200 전체 채점** (200 호출) → `data/fixtures/flash_lite_dev200_scores.jsonl`.

**전체 결과 (vs 사람 gold)**:

| 축 | draft_axes rho | Flash-Lite rho | Flash MAE | Flash bias |
|---|---:|---:|---:|---:|
| Formality | 0.489 | **0.699** | 18.61 | **+17.89** |
| Energy | 0.217 | **0.702** | 8.26 | −0.09 |
| Intimacy | 0.087 | **0.279** | 16.29 | +9.97 |
| Humor | 0.000 | **0.195** | 7.62 | +6.86 |
| Curiosity | 0.829 | 0.766 | 10.13 | −0.64 |
| **MEAN** | **0.324** | **0.528** | **12.18** | |

비교 기준선: rule 0.372 / 14.54, 최고 hybrid ~0.42, 최고 순수 kNN ML ~0.35.

**출처별**:

| 출처 | draft_axes 평균 rho | Flash-Lite 평균 rho |
|---|---:|---:|
| AMI (n=67) | 0.331 | **0.570** |
| NICT (n=68) | 0.465 | 0.434 |
| Taskmaster (n=65) | 0.396 | **0.670** |

**해석**:
- **Flash-Lite를 직접 분석기로 쓰면 rho 0.528 / MAE 12.18** — rule·hybrid·순수 kNN
  모두 상회.
- Energy에서 극적 개선 (0.217 → 0.702), Curiosity MAE 25.8 → 10.1.
- Formality는 +17.9점 계통 편향이 있으나 rho 0.70 → **선형 편향 보정으로 MAE만
  고칠 수 있음** (dev 기준 편향 보정 시 전체 MAE 12.18 → 9.00, rho 불변).
- 여전히 약함: Intimacy 0.28, Humor 0.20 — 그래도 기존 모든 분석기보다 나음.
- NICT 평균이 떨어지는 이유: NICT Humor rho **−0.236** — Flash-Lite가 NICT 발화에
  Humor ~10을 주는데 reviewer-01은 전부 0으로 매김. **이건 Flash-Lite 문제가 아니라
  reviewer-01의 Humor 전량 0 문제일 가능성** (§4 참조).

**중요**: 이건 교사(=서브타임 LLM 분석기) 성능. 증류 학생의 개선은 별개
(same-text 재학습 비교 필요). 학습·증류·사람 라벨 0건.

---

## 3. Claude의 Day 1-2 주장 정정 로그 (Codex가 잡음, Claude 재확인)

| # | 틀린 주장 | 실제 (검증) | 출처 |
|---|---|---|---|
| C1 | "ML이 NICT에 과적합 — NICT가 학습을 지배" | 출처 카운트: NICT 600 / CHiME 600 / AMI 599 / HCRC 500 / Taskmaster 500. NICT는 19.1%, 단일 최대도 아님 | `axis_dataset_combined_real_speech_experimental.jsonl` 집계 |
| C2 | "누출이 ML 순위(rho)를 부풀렸다" | 방향 반대. 제거 시 ML rho **+0.004**, MAE +0.069. hybrid rho도 개선. overlap/clean 차이는 **출처 구성 차이** (clean-100 = Taskmaster 58 / AMI 2) | Day 1 출력 재검토 |
| C3 | "ML이 Taskmaster에 일반화 실패" (전면적) | 축별. Taskmaster **Curiosity는 ML이 최고** (rho +0.751 vs rule +0.665, MAE 21.9 vs 31.4). Energy는 최악 (rho −0.182 vs +0.401). Intimacy MAE ML 27.2 vs rule 15.9 | 축별 재계산 |
| C4 | E3 caps ablation 필요 | `_tokenize()`가 이미 `lower()` 호출 → 대문자 제거는 ML에 무영향. dev-200 반복 `!?` 0행 | 코드 확인 |

**정정 후에도 유지되는 사실**:
- 순수 ML은 dev rank에서 hybrid보다 뒤짐.
- AMI/CHiME/HCRC/Taskmaster 학습 타깃 = `draft_axes` 출력 그대로.
- 학생이 그 결정론적 교사조차 rho ~0.4로만 재현.
- 교사에 검증된 출처별 Intimacy 과대평가 (bucket_sensitivity variantB: teacher−human
  bias AMI +15.6 / NICT +7.3 / Taskmaster +27.8).
- STT `enableAutomaticPunctuation=False` → rule이 서브타임에서 ~0.055 rho 손실.

---

## 4. gold-200 신뢰도 문제 & reviewer-01 Humor 재검수

### 관찰된 신호

- gold-200은 **문장당 1명만 채점** (독립 다중 채점 없음 → 검수자 간 일치도 미측정).
- `reviewer-avg` (gold-0001~0100, AMI 편중): Humor 24/100 nonzero.
- **`reviewer-01` (gold-0101~0200, Taskmaster+NICT): Humor 100/100 전부 0.**
- 검수자는 previous_turn / next_turn 문맥을 봤으나, 모델·신규 검수는 현재 발화만.
- gold-200 빌드 시 175개 소수점 셀이 정수로 절삭 (측정 영향 ~0.006 MAE, 미미).

### 판단

gold-200이 "틀렸다"가 아니라 **신뢰도를 측정한 적이 없다**. 하지만 reviewer-01의
Humor 전량 0은 실수(축 누락) 가능성이 높다. Flash-Lite NICT Humor rho −0.236도
이 문제의 반영일 수 있음.

### 조치 (진행 중)

- `data/fixtures/ml_transition_gold_humor_rereview_reviewer01.csv` 생성 →
  사용자에게 전달. reviewer-01 100문장, 기존 F/E/I/C는 참고용, `reviewed_Humor`만
  재채점.
- 사용자가 재채점 → Claude가 원본 CSV 갱신 → `ml_transition_gold_human_200.jsonl`
  재생성 → Day 1-5 진단 **전부 재실행** (Humor rho가 측정 가능해지므로).

### 방법론 참고

- 이 재채점도 여전히 1명 채점. dev셋 신뢰도 자체를 높이려면 다중 독립 채점 필요
  (calibration의 목적).
- calibration은 모델을 개선하지 않는다. **채점 눈금이 믿을 만한지 확인** —
  검수자별 scale bias, 축별 사람-사람 일치도(어떤 축은 사람도 못 맞춤),
  "얼마나 잘하면 충분한가"의 ceiling.

---

## 5. 현재 결론과 갈림길

### 확립된 사실

1. 현재 TF-IDF k-NN + `draft_axes` 라벨로는 순수 ML 전환의 근거를 만들 수 없다
   (어떤 k·ngram에서도 rule 0.372 미달).
2. 병목은 2단계 모두: 약한 교사(`draft_axes`, 사람과 rho ~0.32, Intimacy 과대평가)
   × 손실 큰 학생(k-NN, 교사를 rho ~0.4로만 재현).
3. **Flash-Lite를 직접 분석기로 쓰면 rho 0.528** — 기존 모든 분석기 상회. Formality
   편향은 선형 보정 가능. Intimacy/Humor는 여전히 약하나 최선.
4. 서브타임 STT 입력엔 구두점이 없어 순수 rule이 프로덕션에서 ~0.055 rho 손실.

### 경로 (전부 사람 학습 라벨 0건)

| 경로 | 교사 | 학생 | 근거 강도 | 비용 |
|---|---|---|---|---|
| **A. hybrid로 전환** | rule+kNN 평균 | — | dev rank 0.42>0.37, 서브타임 skew에서 더 유리 | 가장 낮음. 순수 ML 아님 |
| **B1. Flash-Lite 교사 → kNN 증류** | Flash-Lite | kNN | 학생이 개선분 상당 버림 (k-NN rho 0.4 재현 한계) | API + 학습 |
| **B1+. Flash-Lite 교사 → 더 나은 학생** | Flash-Lite | 로지스틱/부스팅/소형 NN | 유망, 범위 큼 | API + 모델 개발 |
| **B2. Flash-Lite = 분석기 (증류 안 함)** | Flash-Lite | 없음 | 증류 손실 0, dev rho 0.528 확인됨 | 턴당 LLM 호출 1개 추가 (현재 2개 → 3개). latency/비용 실측 필요 |
| C. 다른 모델 계열 학습 | — | 비-kNN | 미지수 | 큼 |
| D. 약한 축 타겟 사람 라벨 | — | — | 강함 | 목표1 위배 |

**공통**: 어느 경로든 예약 pool 176행 × 5축 × 2명 = 1,760점수 사람 평가 필요.

### D 경로 라벨량 (참고, 지금 확정 불가)

| 단계 | 라벨량 | 목적 |
|---|---|---|
| first-40 | E/C/I 3축 × 40행 × 2명 = 240점수 | 라벨 1개 효과 측정 |
| 효과 있으면 | +80행 = 480점수 | 기울기 확인 |
| 최대 (축당 균형) | ~450행 × 3축 × 2명 ≈ 2,700점수 | 목표1과 상충 시작 |

정확한 수는 first-40 전후 비교로 기울기를 재야 나옴.

---

## 6. 미결정 사항 (사용자 결정 필요, 순서대로)

1. **U1 — 목표/평가 기준.** 사람 gold gate 유지(기본) vs "교사 재현"으로 변경.
   진단 결과(특히 reviewer-01 재검수 후 재실행)를 보고 결정.
2. **경로 선택.** A(hybrid) / B1 / B1+ / B2 중. Flash-Lite dev rho 0.528을 봤으니
   B2가 유력하나, latency/비용 실측(CLAUDE.md §4)과 "의존성 없는 빠른 분석기" 원칙
   상충을 확인해야 함.
3. **first-40 실행 여부.** 자동 경로(B)가 gate를 넘기면 first-40 생략 가능 (계획
   변경으로 기록). 못 넘기면 bounded first-40.
4. **calibration 재개 시점 / 규모.** 4명 vs 2명. 30문항 재설계 후 언제 배포·채점.
5. **최종 평가 프로토콜.** CI 기반 pass/inconclusive의 정확한 정의, 허용폭, 필수 축,
   검수자 수, 표본 크기 — 예약 pool 개봉 전 확정.
6. **런타임 전환 승인.** frozen 후보가 `final_gate` 통과 + `gate4_reproduction` 재현
   + 배포 어댑터 검증 + rule 대비 퇴행 보고 후 명시 승인.

---

## 7. 커밋 목록 (branch `gsd/phase-ai-ml-transition-execution`, base `a72ff9f`)

| commit | 내용 |
|---|---|
| `80ca683` | 예약 pool fail-safe, best_by_spearman NA 보류, diagnose NA, partial-label ML, bucket sensitivity |
| `9391b89` | batch 검수 CSV 스키마 + `aggregate_axis_reviews.py` |
| `9f1e69b` | Phase 2 후보 세트 (calibration/pilot/first40, unscored) |
| `c4a0e4a` | calibration 48→90 (탐지확률 기반, 30/출처) |
| `0a2fff3` | calibration 채점 워크북 스크립트 |
| `fce9cea` | 검수자 4명 (slot A–D), 부분 집계 지원 |
| `c9f4791` | cycle 4 — 라벨 전략 & calibration 검토 (Claude R1 + Codex R2 + DECISION) |
| `219ae06` | Day 1 — dev-200 group-purge 비교 |
| `4cb9ec8` | Day 2 — 교사 충실도 vs 학생 용량 |
| `bba5c02` | Day 3 — STT train/serve 입력 skew |
| `2024ea7` | cycle 4b — Day 1-3 결과 검토, 주장 3건 정정 |
| `255a332` | Day 4 — k/ngram 탐색 (순수 ML kNN은 못 넘김) |
| `941b2de` | Day 5 — Flash-Lite 5축 교사 + preflight |
| `fdb7792` | Day 5 — Flash-Lite vs draft_axes vs 사람 비교 |

미푸시 (2026-09-11 기준). `ml_transition_gold_humor_rereview_reviewer01.csv`는 미커밋.

---

## 8. 생성/수정 파일

### 진단 스크립트 (신규)

- `scripts/diagnose_dev200_group_purge.py` — Day 1
- `scripts/diagnose_teacher_fidelity.py` — Day 2
- `scripts/diagnose_stt_input_skew.py` — Day 3
- `scripts/flash_lite_axis_teacher.py` — Day 5 (`--preflight` / `--score`)
- `scripts/compare_flash_lite_vs_draft_teacher.py` — Day 5
- `scripts/bucket_sensitivity_gold200.py` — cycle 4 이전 (교사 bucket 민감도)

### 데이터 산출물 (신규)

- `data/fixtures/flash_lite_dev200_scores.jsonl` — Flash-Lite dev-200 채점 (200행)
- `data/fixtures/ml_transition_reserved_final_test_pool.jsonl` — 예약 176행/156그룹
- `data/fixtures/ml_transition_reservation_audit.jsonl` — 400행 전체 기록
- `data/fixtures/ml_transition_calibration_candidates_90.jsonl` + slot CSV/manifest/워크북
- `data/fixtures/ml_transition_pilot_eh_candidates.jsonl` (54행, 미배포)
- `data/fixtures/ml_transition_train_first40_candidates.jsonl` (40행, 미배포)
- `data/fixtures/ml_transition_gold_humor_rereview_reviewer01.csv` — reviewer-01 재검수용

### ai-collab 논의 기록

- `docs/ai-collab/CONTEXT.md` / `CURRENT_TASK.md` / `CLAUDE_REVIEW.md` / `CODEX_REVIEW.md`
  / `DECISION.md` — cycle 4b 현재 상태
- `docs/ai-collab/archive/2026-09-10-execution-planning/` — cycle 3
- (cycle 4는 `git show c9f4791:docs/ai-collab/DECISION.md`)

### 문서 수정

- `docs/ml-transition-contract.md` — STATUS 블록 cycle 4/4b 반영, §12 Phase 2 산출물
- `docs/ml-transition-plan.md` — STATUS 포인터

---

## 9. 다음 단계

1. **사용자**: reviewer-01 Humor 재채점 → CSV 반환.
2. **Claude**: 원본 CSV 갱신 → `ml_transition_gold_human_200.jsonl` 재생성 →
   Day 1-5 진단 전부 재실행 → Humor 포함 갱신된 표.
3. **사용자**: 갱신된 결과로 U1 + 경로(A/B) 결정.
4. 경로 확정 후: (B2면) latency/비용 실측 → (B1+면) 학생 모델 선정 →
   same-text 재학습 비교. (A면) hybrid 설정 고정 + 배포 어댑터.
5. frozen 후보 → 예약 pool 176×2 사람 평가 → `final_gate` + `gate4_reproduction` →
   사용자 승인 → 전환.

---

후속 기록: §4의 재검수 진행 상황과 §9의 다음 단계 이후에 완료한 5축 재평가 기준·출처·검증 결과를 아래에 통합했다. 점수 파일 반영은 완료했으며, 기존 진단 지표의 재계산은 아직 수행하지 않았다.

## 10. reviewer-01 100문장: 연구 참고 5축 재평가 기준

대상은 `gold-0101`~`gold-0200`이다. 현재 발화만 평가하며, 기존 점수와 비교하는 재평가다. 독립 블라인드 검수나 검수자 간 일치도를 측정한 결과가 아니다. `reviewer_id`는 원래 검수 묶음의 식별자다.

### 축별 적용 기준 요약

| 축 | 적용한 기준 |
|---|---|
| Formality | 직접 요청·완곡한 요청·격식 있는 표현 구분 — [격식성 연구](https://aclanthology.org/Q16-1005/), [정중함 연구](https://aclanthology.org/P13-1025/) |
| Energy | 긍정·부정과 감정의 강도를 구분 — [각성도 연구](https://pdodds.w3.uvm.edu/teaching/courses/2013-01UVM-300/output/files/2013/warriner2013a.pdf) |
| Intimacy | 거래 정보·취향 공개·관계에 대한 감정 구분 — [친밀성 연구](https://aclanthology.org/2020.emnlp-main.428/) |
| Humor | 감탄과 농담 의도·익살을 구분 — [유머 평가 연구](https://aclanthology.org/2021.semeval-1.9/) |
| Curiosity | 행동 요청·안부·정보 질문·설명 탐색 구분 — [호기심 연구](https://www.cmu.edu/dietrich/sds/docs/loewenstein/PsychofCuriosity.pdf) |

### 공개 자료와 적용 범위

| ID | 공개 자료 | 확인한 내용 | 이번 평가에 적용한 판단 |
|---|---|---|---|
| F1 | [Pavlick & Tetreault (2016), An Empirical Analysis of Formality in Online Communication](https://aclanthology.org/Q16-1005/) §3.1–3.3 | 문장 격식성은 정도 차이가 있고 장르에 영향을 받는다. 원 연구는 −3~3 척도를 사용했다. | 문장 전체의 말투를 비교한다. 학습자 문법 오류나 머뭇거림을 무례함으로 해석하지 않는다. |
| F2 | [Danescu-Niculescu-Mizil et al. (2013), A computational approach to politeness with application to social factors](https://aclanthology.org/P13-1025/) §3, Table 3 | 간접 요청, could/would, 감사 등은 정중함과 관련된다. 표현의 위치와 조합도 중요하다. | 프로젝트의 대화 중심 Formality 정의에 맞춰 직접 요청·일반 요청·완곡한 요청을 구분한다. 정중함과 격식성이 완전히 같은 개념이라는 뜻은 아니다. |
| E1 | [Warriner, Kuperman & Brysbaert (2013), Norms of valence, arousal, and dominance for 13,915 English lemmas](https://pdodds.w3.uvm.edu/teaching/courses/2013-01UVM-300/output/files/2013/warriner2013a.pdf) Abstract, Method | 정서의 긍정·부정과 각성 수준은 구별되는 차원이다. 연구 대상은 개별 단어다. | Energy는 문장에 드러난 활성·강조 정도로 평가한다. 긍정 단어 개수를 더하거나 단어 평정치를 문장 점수로 환산하지 않는다. |
| I1 | [Pei & Jurgens (2020), Quantifying Intimacy in Language](https://aclanthology.org/2020.emnlp-main.428/) §2–4 | 친밀성은 자기공개, 따뜻함, 언어적 표현 등에 걸쳐 나타나며 주제만으로 설명되지 않는다. 연구는 질문을 중심으로 한다. | 업무상 정보 전달·일상 취향 공개·개인적 경험·관계에 대한 따뜻한 표현을 구분한다. 평서문으로의 적용은 이번 평가의 확장이다. |
| H1 | [Meaney et al. (2021), SemEval 2021 Task 7: HaHackathon](https://aclanthology.org/2021.semeval-1.9/) §3.2–3.4 | 유머 의도와 재미의 정도를 구분하며, 설정·반전이나 부조리한 내용 등을 단서로 사용했다. 평가자 간 유머 평정 차이도 다룬다. | 유머를 표현하는 단서를 먼저 확인한다. 감탄·친절·어휘 오류 자체는 유머 근거가 아니다. 약한 익살로도 읽히는 문장은 낮은 점수와 불확실성 근거를 함께 기록한다. |
| C1 | [Loewenstein (1994), The Psychology of Curiosity: A Review and Reinterpretation](https://www.cmu.edu/dietrich/sds/docs/loewenstein/PsychofCuriosity.pdf) 정보 격차 관점 | 호기심을 자신이 알고 있는 것과 알고 싶은 것 사이의 격차와 연결한다. | 현재 발화가 정보를 얻으려는 정도를 평가한다. 행동 요청, 의례적 안부, 사실 질문, 설명·탐색 요청을 구분한다. 문장 점수나 아래 구간을 원 논문이 제시한 것은 아니다. |

### 0~100 운영 척도

아래 수치와 문장별 평정은 **이번 데이터용 판단 기준**이다. 논문이 이 문장에 부여한 점수도, 원 척도를 선형 변환한 값도 아니다. 정수 저장과 5점 단위 구분을 사용한다. 5점 차이는 검토 가능한 상대적 판단이며 통계적으로 검증된 정밀도를 뜻하지 않는다.

| 축 | 낮은 구간 | 중간 구간 | 높은 구간 |
|---|---|---|---|
| Formality | 0–20 매우 편한 말투·슬랭; 25–35 구어적 도입과 단편 표현 | 40–50 중립적 일상 발화; 55–65 정중한 요청·감사 | 70–80 복수의 완곡·존중 표현; 85–100 매우 의례적·격식적인 발화 |
| Energy | 0–15 명시적 저활성; 20–30 강조 없는 평이한 서술·질문 | 35–45 가벼운 관심·평가·강조; 50–60 뚜렷한 감탄·강조된 감사 | 65–80 강한 흥분·긴급성; 85–100 압도적인 고각성 표현 |
| Intimacy | 0–5 비개인적 정보·업무 요청; 10–20 인사·협조·의례적 감사 | 25–40 취향·경험·개인적 감정 또는 구체적인 따뜻함; 45–60 관계에 대한 정서 표현·상당한 자기공개 | 65–80 취약성·애정·깊은 지지; 85–100 매우 깊은 정서적 친밀성 |
| Humor | 0 유머 단서 없음; 5–10 약한 익살의 텍스트 단서는 있지만 문자적 해석도 유력 | 15–35 가벼운 놀림·과장·장난; 40–60 분명한 농담 구조 | 65–80 강한 유희성; 85–100 발화 전체를 지배하는 유머 |
| Curiosity | 0 정보 탐색 없음; 5–20 행동 요청·수사 질문; 25–40 의례적 안부·불명확한 탐색 | 45–55 조건·가능성 확인; 60–70 명시적 사실·개인 취향 질문 | 75–80 비교·추가 탐색; 85–100 설명·이유·메커니즘을 적극적이고 확장적으로 탐색 |

### 문장별 판정 절차

1. 현재 문장의 발화 목적을 확인한다. 이전·다음 턴의 말투나 등장인물 정보를 가져오지 않는다.
2. 각 축을 독립적으로 평가한다. Formality가 높다고 Intimacy가 자동으로 낮아지거나, Energy가 높다고 Humor가 자동으로 높아지지 않는다.
3. 복합 발화는 정보 질문·감사·요청 등의 비중을 함께 본다. 동일 유형은 비슷한 점수를 주고 실제 표현 차이가 있을 때만 조정한다.
4. 현재 문장에 없는 음량·속도·억양·농담 의도를 추측하지 않는다. 무표정한 음성이라고 가정하지도 않는다. Energy는 텍스트에서 읽히는 정도만 평가한다.
5. 문법 오류, 반복, 전사 오류는 원문대로 보존한다. 정보가 불완전하면 근거에 불확실성을 적고 극단값을 피한다.
6. 문맥을 반드시 사용해야 점수를 정할 수 있는 경우 `문맥 필요`로 기록한다. 이번 평정은 현재 문장만으로 제한했으므로 인접 턴을 근거로 한 점수는 없다.

### 경계 사례

- `Can you book it?`: 행동 요청이 중심이므로 Curiosity 15. 질문 형태만으로 90점을 주지 않는다.
- `Who stars in the film?`: 명시적인 사실 질문이므로 Curiosity 65. 원인 설명이나 심화 탐색은 없다.
- `I am doing great. How are you?`: 친근한 안부이므로 Intimacy 30, Curiosity 35. 개인의 실제 심리 상태까지 추론하지 않는다.
- `Thank you very much ... I really enjoyed talking to you.`: 관계 자체에 대한 따뜻한 표현으로 Intimacy 55. 감사의 크기와 Energy를 같은 값으로 고정하지 않는다.
- `Can you imagine that`: 수사적 놀람은 읽히지만 현재 문장 안에 농담의 내용이 없어 Humor 0. 앞선 5점에서 수정한다.
- `it's safety but food is terrible`: 상반된 평가를 연결했지만 유머를 의도한 반전이라고 단정하기 어려워 Humor 0. 앞선 5점에서 수정한다.
- `... reading books, listening music, singing songs and having a sleep`: 활동 나열 끝에 수면을 둔 가벼운 익살 가능성을 Humor 5로 평가한다. 단순 취향 목록으로도 자연스러우므로 확신이 낮은 경계 사례다.
- `... sound divine ...`: 강한 칭찬은 있지만 장난이나 농담 구조는 없어 Humor 0. 앞선 5점에서 수정한다.

### 파일 반영

- `ml_transition_gold_humor_rereview_reviewer01.csv`: 기존 `prev_*`와 원문을 보존한다. Humor는 `reviewed_Humor`, 다른 축의 변경은 `reviewer_notes`에 `Formality 35로` 형식으로 기록한다. notes에는 모든 축의 짧은 판단 근거도 포함한다.
- `ml_transition_gold_blind_review_200.csv`: reviewer-01의 최종 5축 점수와 동일 근거를 반영한다. reviewer-avg 100행은 그대로 둔다.
- `ml_transition_gold_human_200.jsonl`: reviewer-01의 5축과 notes를 원본 검수 CSV에 맞춰 재생성한다. 해당 행의 `label_status`와 `labeler`는 `research_guided_rereview`로 구분한다. 기존 `human_reviewed_blind` 검증이 이번 평정에 새로 수행되었다는 의미를 남기지 않는다. reviewer-avg의 기존 정수 점수는 보존한다.
- `ml_transition_gold_stratified_candidates_200.jsonl`: 후보·출처 파일로 그대로 보존한다. `axes: null`은 의도된 구조다.

각 notes의 F/E/I/H/C는 위 축 순서이며, 근거 ID는 F1·F2/E1/I1/H1/C1에 대응한다. 이 문서의 기준은 이번 100문장에만 적용했다. 다른 검수자의 100행까지 같은 눈금으로 재평가한 것은 아니므로 전체 200행의 검수자 간 척도 일치가 검증되었다고 해석하지 않는다. 기존 평가 지표는 이전 라벨의 결과이며 이번 변경 후 지표를 재계산하지 않았다.

### 반영 결과와 검증

아래 변경 수는 이번 연구 참고 재평가 직전 파일과의 비교다. Humor는 앞선 임시 조정값과 비교했다.

| 축 | 변경한 점수 수 / 100 | 최솟값–최댓값 | 평균 |
|---|---|---|---|
| Formality | 90 | 25–75 | 45.50 |
| Energy | 77 | 20–55 | 35.25 |
| Intimacy | 87 | 0–55 | 12.05 |
| Humor | 4 | 0–5 | 0.05 |
| Curiosity | 64 | 0–70 | 28.40 |

총 500개를 검토하여 322개를 수정했다. Humor는 `gold-0132`만 5점이고 나머지는 0점이다. 현재 표본에 높은 점수의 근거가 없으므로 척도의 상단 구간은 사용하지 않았다. 낮은 Humor 분포 자체가 축 누락의 증거는 아니다.

- 100개 ID와 500개 점수의 0–100 정수 범위를 확인했다.
- 재검수 CSV·원본 CSV·최종 JSONL의 점수와 notes를 대조했다.
- `prev_*`, 원문, 인접 턴, 출처 식별자, 후보 파일 및 reviewer-avg 100행을 보존했다.
- 기존 `scripts/build_human_reviewed_axis_dataset.py`로 임시 파일을 생성하여 200행의 점수·notes·출처가 최종 파일과 일치함을 확인했다. 재평가 상태를 구분하는 `label_status`·`labeler`는 의도적으로 별도 유지했다.
- 모델 재학습이나 분석기 성능 평가를 실행한 결과는 아니다.

---

## 11. reviewer-01 재검수 후 진단 재실행 (2026-09-11)

reviewer-01의 100행(gold-0101~0200) 5축을 연구 참고 재평가한 뒤 gold-200을 갱신하고
(dev-200 SHA-256 `998fce0f...`, reviewer-01 행 `label_status=research_guided_rereview`),
Day 1 / 4 / 5를 재실행했다. reviewer-avg 100행은 손대지 않았다.

**결론 요지 변화**: 재평가로 rule의 우위가 줄고(0.372 → 0.344), 격차가 좁혀졌다.
Flash-Lite의 우위는 유지·강화됐다.

### Day 1 재실행 (dev-200 전체, dev-group-purged 학습)

| 분석기 | 이전 (재검수 전) | 재검수 후 |
|---|---|---|
| rule | MAE 14.54 / rho 0.372 | **MAE 12.53 / rho 0.344** |
| ML (k5 bigram) | 14.97 / 0.284 | 13.33 / 0.288 |
| hybrid (k5 bigram) | 14.28 / 0.391 | 12.16 / 0.377 |

- MAE가 전반적으로 개선 (재평가 라벨이 모델 예측과 크기 면에서 더 근접).
- clean-100: rule 0.348 / ML 0.307 / hybrid 0.382 (ML-rule 격차 0.04로 축소).
- 출처별: NICT는 이제 **ML rho 0.351 > rule 0.255**. AMI(reviewer-avg, 미변경) ML 0.130 유지.
  Taskmaster rule 0.327 / ML 0.196 / hybrid 0.311.

### Day 4 재실행 (k/ngram, dev-200 전체)

| config | ML MAE / rho | hybrid MAE / rho |
|---|---|---|
| k=7 unigram | 13.23 / 0.339 | 12.35 / 0.401 |
| k=15 bigram | 13.21 / **0.362** | 12.36 / **0.408** |
| rule | 12.53 / 0.344 | — |

- **순수 ML(k=15 bigram) rho 0.362가 rule 0.344를 근소하게 상회** (재검수 전에는
  ML 최고 0.350 < rule 0.372였음).
- hybrid는 0.40~0.41로 여전히 최고 (기존 분석기 중).

### Day 5 재실행 (Flash-Lite vs draft_axes vs 사람)

| 축 | draft_axes rho | Flash-Lite rho | Flash MAE | Flash bias |
|---|---:|---:|---:|---:|
| Formality | 0.538 | **0.711** | 14.93 | +13.52 |
| Energy | 0.310 | **0.698** | 6.93 | +0.79 |
| Intimacy | 0.124 | **0.359** | 13.13 | +7.58 |
| Humor | −0.003 | **0.201** | 7.59 | +6.83 |
| Curiosity | 0.820 | 0.742 | 12.38 | +7.21 |
| **MEAN** | **0.358** | **0.542** | **11.00** | |

출처별 Flash-Lite 평균 rho: AMI **0.570** / NICT **0.440** / Taskmaster **0.728**.

### 재검수 후 순위 (dev-200, 근사)

| 분석기 | rho | MAE |
|---|---:|---:|
| draft_axes (교사) | 0.358 | 14.60 |
| rule | 0.344 | 12.53 |
| 순수 ML (k=15 bigram) | 0.362 | 13.21 |
| hybrid (k=15 bigram) | 0.408 | 12.36 |
| **Flash-Lite 직접** | **0.542** | **11.00** |

**해석**: 갱신된 dev-200에서 Flash-Lite 직접 분석기가 여전히 결정적으로 앞선다
(다음 후보인 hybrid보다 rho +0.13). 순수 ML도 rule을 근소하게 넘지만 hybrid에는 못
미친다. reviewer-01 재평가는 rule을 절대적으로 낮췄고, ML 전환(경로 B) 근거를
약화시키지 않았다.

**주의**:
- reviewer-01 재평가는 blind 아님 (진단 결과를 본 뒤). `label_status`로 구분.
  최종 예약 pool 평가는 fresh blind 검수자로.
- reviewer-01 Humor는 재확인 결과 거의 전량 0 (gold-0132만 5). 축 누락이 아니라
  해당 표본(과제대화·학습자 인터뷰)에 유머가 희소한 것. dev Humor rho는 여전히
  reviewer-01 절반에서 상수에 가까움.
- Flash-Lite NICT Humor rho는 낮음(−0.24 수준) — Flash-Lite가 중립 학습자 발화에
  Humor를 과다 부여하는 실제 약점.

---

## 12. B0-B4 실험: 로지스틱 대안 학생 모델 (2026-09-11~12, cycle 4c로 정정됨)

> **이 절은 cycle 4c(코덱스 검토 + 재검증)를 반영한 정정본이다. 처음 보고했던
> 숫자·해석 중 상당수가 틀렸거나 과장이었다. 아래는 정정 후 버전만 남긴다.**

### 실험 설계

dev-200(dev-그룹 제거 학습셋, NA-aware, 출처별)에서 5개 팔(B0-B4)을 비교했다:

- **B0 — 규칙 기반.** `RuleBasedAxisAnalyzer`. 학습 데이터 없음.
- **B1 — 기존 약한 라벨로 학습한 최근접 이웃 회귀.** `TfidfKnnAxisRegressor`
  (k=15, bigram — 15개 설정 sweep 중 dev 최댓값, **선택편향 있음**). 학습 라벨(AMI/
  CHiME6/HCRC/Taskmaster)은 `draft_axes()`의 결정론적 출력 그대로(rho 1.000 재현
  확인됨); NICT는 567행 중 208행만 사람이 Formality/Energy를 수정.
- **B2 — hybrid.** B0과 B1의 축별 평균.
- **B3 — 의존성 없는 능선회귀(ridge) 선형 모델.** `ai/linear_axis_model.py`,
  B1과 같은 TF-IDF 파이프라인이나 **어휘 4,000개로 제한**(B1은 17,913개 — 완전히
  같은 특징이 아님), 미니배치 SGD로 학습 (numpy 없음).
  - B3a: B1과 같은 약한 라벨로 학습.
  - B3b: B4가 매긴 라벨로 학습.
- **B4 — LLM을 직접 채점기로 호출.** `gemini-2.5-flash-lite`, 고정 프롬프트
  (축별 0-33/34-66/67-100 앵커, 현재 발화만 인용, temperature 0, 스키마 강제,
  무효 출력 거부). dev-200 200개 + 학습 purged 2,940개를 각각 한 번씩 채점.

### 코덱스 재검토에서 확인된 정정 사항

1. **ridge 정규화 버그(확인·수정됨)**: L2 축소가 배치에 등장한 feature에만
   적용되고 있었다(표준 ridge 아님). `ai/linear_axis_model.py` 수정 — 이제 매
   스텝 전체 가중치에 적용. 수정 후 ridge(draft) rho 0.439→0.428, ridge(flash)
   0.480→0.462. 순위는 안 바뀜, 수치만 소폭 하락.

2. **B4가 응답 생성과 병렬 불가하다는 주장(확인·철회)**: 틀렸다.
   `_call_gemini_chat()`은 `character_name` 문자열과 `level`만 받고, 계산된
   축·character dict는 넘기지 않는다 (`backend/main.py:694`). 코드상 직렬이어야
   할 데이터 의존성이 없다 — 지금까지 아무도 병렬로 안 짰을 뿐. "완전 병렬 불가"는
   철회. 다만 비동기 구현은 아직 없고 실측도 안 됨. 턴당 API 호출 1회 추가라는
   비용 자체는 유효.

3. **B3b가 Flash-Lite의 Formality 편향을 그대로 이어받음(확인, 미해결)**:
   B3b Formality MAE **15.4~15.6** — hybrid(B2)의 9.6보다 훨씬 나쁨. Flash-Lite가
   dev에서 Formality를 +14~+18 과대평가하는데, ridge가 그 라벨로 학습해서 같은
   오프셋을 새 문장에도 그대로 재현. **구현 버그가 아니라 편향된 라벨로 학습한
   회귀 모델의 당연한 결과.** 이번 사이클에서 고치지 않음 — dev-200 자체로 편향을
   보정하면 새로운 dev 유출이 되므로, 별도 데이터로 보정하는 계획이 필요.

4. **B1→B3a가 "모델만 바꾼" 비교가 아님(확인)**: 어휘 크기가 다르다(4,000 vs
   17,913). B3a↔B3b(같은 ridge 구현, 라벨만 다름)는 깨끗한 비교지만, B1↔B3a는
   추정기와 어휘 필터링이 동시에 바뀐 비교다. "이 선형 파이프라인이 이 kNN
   파이프라인보다 dev에서 낫다"까지만 말할 수 있다.

5. **B1(및 B3/hybrid가 재사용한 k=15/bigram) 수치가 dev에서 15개 설정 중
   최댓값(확인)**: k5/unigram 0.297, k5/bigram 0.288, k15/bigram(인용값) 0.362.
   선택편향의 정확한 크기는 이 sweep만으로 추정 불가 (nested held-out 선택이나
   독립 평가 필요).

6. **"두 독립적인 dev 상태에서 순위가 재현됐다"는 주장(확인, 철회)**: 재검수 전
   (커밋 `255a332`): kNN 최댓값 0.350 < rule 0.372. 재검수 후: kNN 0.362 > rule
   0.344. **같은 dev를 같은 텍스트로, 라벨만 100행 비-blind 수정한 뒤 두 번 본
   것이지 독립 재현이 아니다.**

7. **탐색적 부트스트랩 (코덱스, 인메모리, 리포지토리에 스크립트로 남기지 않음)**:
   출처별 그룹 층화(161그룹: AMI 39 / NICT 61 / Taskmaster 61), 1,000회 재표본,
   seed 20260912, ridge 수정 전 예측 기준:

   | 짝지은 평균 rho 차이 | 관측값 | 탐색적 95% 구간 |
   |---|---:|---:|
   | B3b(수정 전) − B2 | +0.072 | [+0.001, +0.149] |
   | B4 − B3b(수정 전) | +0.062 | [+0.012, +0.115] |

   B3b의 hybrid 대비 개선은 **95% 구간 하한이 0에 매우 가까움** — 명확히 0보다
   크다고 보기 어려움. 반복 분석·설정 선택·비-blind 재검수·rubric 불확실성을
   반영 못한 구간이다. ridge 수정 후 예측으로 재계산 필요(방향은 유지될 것으로
   보이나 크기 미확인).

8. **B3b 배포 경로 없음(확인)**: `ai/analyzers.py::get_axis_analyzer()`는
   rule/ml(kNN)/hybrid만 지원. ridge 직렬화·로딩 어댑터가 아직 없다. "그대로
   배포 가능"은 구현 상태를 과장한 것 — 어댑터는 아직 안 만든 작업이다.

9. **검수자/출처 교란(확인)**: B3b의 hybrid 대비 개선폭이 reviewer-avg 행
   (AMI+NICT, 원래 blind 검수)에서 +0.093, reviewer-01 행(NICT+Taskmaster,
   비-blind 재검수)에서 +0.231로 다르다. 개선이 재검수분에만 몰린 건 아니지만,
   검수자 구분이 출처와 얽혀 있어 "검수자 효과"만 따로 분리할 수 없다.

10. **축별 숨은 퇴행**: Energy rho는 rule(0.505) > hybrid(0.426) > B3b(0.389) —
    Energy는 여전히 규칙이 최고. AMI MAE도 rule(11.76)이 모든 ML 계열보다 낮다
    (B3b 12.64로 최악). B4도 전축 지배는 아님 — Humor·Intimacy 풀링 rho는 B3b가
    B4보다 낫고, Curiosity는 B3a가 B4보다 낫다. **"B3b/B4가 이긴다"는 단일
    문장은 성립하지 않는다 — 축·출처별 표를 같이 봐야 한다.**

### 정정된 헤드라인 표 (dev-200, ridge 수정 후, 평균 Spearman rho / MAE)

| 팔 | rho | MAE | 비고 |
|---|---:|---:|---|
| B0 규칙 | 0.344 | 12.53 | Energy(0.505)·AMI MAE(11.76) 최고 |
| B1 kNN·기존 약한 라벨 (k15/bigram, sweep 최댓값) | 0.362 | 13.21 | 선택편향 있음, 미선택 설정은 0.29~0.30 |
| B2 hybrid | 0.408 | 12.36 | |
| B3a ridge·같은 약한 라벨 (어휘 다름) | 0.428 | 12.67 | B1과 어휘 크기 다름 |
| B3b ridge·Flash-Lite 라벨 | 0.462 | 11.94 | hybrid 대비 개선 95% 구간 하한이 0 근접(수정 전 기준); **Formality MAE 15.4~15.6로 hybrid(9.6)보다 확실히 나쁨** |
| B4 Flash-Lite 직접 호출 | 0.542 | 11.00 | 전축 지배 아님; 턴당 API 비용; 병렬화는 막혀있지 않으나 미구현·미실측 |

### 이번 사이클 결론

**아직 어느 팔도 프로덕션 결정을 내릴 수 있는 상태가 아니다.** B3b는 발전
가능성 있는 후보이지만 (1) Formality 편향 미해결 (2) hybrid 대비 개선의 통계적
확실성 낮음 (3) 배포 어댑터 없음 (4) 축·출처별로 이기지 못하는 부분이 있음.
다음 단계는 이 문제들을 해결하거나 명시적으로 남겨둔 채 보고서에 정확히
기록하는 것.

**참고 문헌·데이터 출처**: `docs/ai-labeling-guide.md`(5축 정의), `docs/ml-transition-contract.md`
(평가 규약), NICT JLE 4.1(CC BY-SA 3.0), AMI Meeting Corpus(CC BY 4.0),
Taskmaster-1(CC BY 4.0), Google `gemini-2.5-flash-lite`(Google AI Studio API),
`docs/ai-collab/archive/2026-09-11-cycle4b-diagnosis/` 및 `docs/ai-collab/DECISION.md`
(cycle 4c, 코덱스 Round 2 원문).
