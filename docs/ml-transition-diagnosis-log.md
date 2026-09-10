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
