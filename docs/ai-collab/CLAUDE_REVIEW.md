# Claude Code Review — Round 1 (실행 계획 초안)

작성: 2026-09-10. 근거: `archive/2026-09-08-roadmap-review/DECISION.md`. 실제 스크립트
(`ai/ml_baseline.py`, `scripts/select_ml_transition_annotation_sets.py`,
`scripts/sample_ml_transition_candidates.py`, `scripts/export_axis_review_csv.py`,
`scripts/sample_real_speech_label_candidates.py`)를 읽고 작성. 코드는 아직 수정 안 함.

## 배경 사실 (읽어서 확인한 것)

- `focus_bucket`(sample_ml_transition_candidates.py)은 Energy/Curiosity 이분 휴리스틱.
  `sample_bucket`(sample_real_speech_label_candidates.py `BUCKET_ORDER` 6종)과 다르다.
  **`classify_bucket()`이 결정론적 함수로 존재** (line 165) — gold 후보 행에 재적용 가능.
  다만 `move_label`(HCRC 전용) 분기는 AMI/NICT/Taskmaster 후보엔 안 걸림.
- gold/train 후보는 `group_key = source:{source_group|source_record_id|source_file|utterance}`
  기준으로 서로 disjoint하지만 **기존 3,137행 학습셋과는 분리 보장 없음** (manifest도
  overlapping_source_groups=0은 gold vs train 간만).
- NICT 학습 600행은 `source_group` 없음 → group 대조 불가.
- `export_axis_review_csv.py`: `review_set` choices가 `gold`/`train`만. CSV는 blind
  (utterance + prev/next turn + 빈 reviewed_* + reviewer_id + status + notes).
  `review_id = f"{review_set}-{index:04d}"`.
- `ml_baseline.py`: `AxisTrainingExample.label`은 5축 전부 요구(`_validate_axes`),
  `predict()`는 모든 이웃이 5축 다 있다고 가정.
- `TfidfKnnAxisRegressor`는 축별 독립 모델이 아님 — 하나의 feature 공간 + k-NN
  가중평균. 축별 이웃 필터만 넣으면 partial-label 지원 가능(별도 모델 불필요).

## 실행 계획

### A. 즉시 (코드 불필요 / 읽기 전용) — 격리 + manifest

**A1. 최종 test pool 격리 목록**
- 입력: `ml_transition_gold_candidates_600.jsonl` − `ml_transition_gold_stratified_candidates_200.jsonl`의 발화 = 400행
- 각 행의 `group_key`를 3,137행(`axis_dataset_combined_real_speech_experimental.jsonl`)의 non-empty `source_group` 집합과 대조
- 산출: `data/fixtures/ml_transition_reserved_final_test_pool.jsonl`
  - `overlap_status`: `clean`(AMI/Taskmaster 중 그룹 미겹침, 예상 ~121) / `unknown`(NICT 132, 그룹키 없음)
  - `overlap_status=dirty`는 제외
- NICT provenance: 각 NICT 행의 `source_line`/`source_record_id`가 학습 600행의 `source_line`과 매칭 가능한지 이 스크립트에서 조사·보고 (복구되면 unknown → clean/dirty 재분류)
- 읽기 전용 집계 스크립트로 작성, 결과만 파일로

**A2. `docs/ml-transition-plan.md` 갱신** (문서만)
- gold-200 → "dev/diagnosis set" 재정의
- "leakage가 원인 아님" → "leakage 영향 크기 미확정, 다만 nonoverlap 60행에서도 ML 우위 관찰 안 됨"
- 즉시 쓸 수 있는 clean 후보는 400개가 아니라 121개(+ NICT 132 unknown)
- 평가 계약 추가: 고정 comparator(현재 rule / 기존 hybrid / 후보 ML+연결 hybrid, rule 대비 퇴행도 보고), source-group 단위 paired bootstrap CI, `_pearson()` 상수입력 NA 표기, gate #4는 별도 예약 그룹에서만

### B. 사람 라벨링 CSV 3종 (내가 후보 추출 + CSV 생성, 검수는 팀)

공통:
- 후보는 전부 **train candidate reservoir(1200)** 에서만 뽑는다. gold reservoir(600)는
  A1 격리 대상이라 손대지 않는다. (train_active_ec 120 + A1 목록 제외)
- 2인 독립 채점 포맷: **행 복제** 방식 — 같은 `review_id`에 `reviewer_slot` A/B 2행,
  개인 점수를 그대로 보존. 평균은 나중에 별도 스크립트로.
- `selection_reason` 등 선정 메타는 CSV에서 제외 (blind 유지).
- `export_axis_review_csv.py`에 `review_set` = `calibration` / `pilot` 추가 +
  `reviewer_slot` 컬럼 + 행 복제 옵션 필요 (코드 수정 = C 작업에 포함).

**B1. Reviewer calibration — 48 발화 (96행)**
- train reservoir에서 AMI 16 / NICT 16 / Taskmaster 16, `group_key` 중복 없음
- Humor 희소 후보 6개 + 나머지 42개는 자연스럽게 (자연 분포 성능 추정용 아님, 명시)
- 5축 전부 채점
- 산출: `ml_transition_calibration_candidates_48.jsonl`, `ml_transition_calibration_review_48.csv`

**B2. Energy/Humor pilot — 60 발화 (120행)**
- train reservoir에서: 20 event-hint(`annotation_events`에 laughter/laugh 류) + 20 model-disagreement(rule vs ML의 Energy 또는 Humor 절대차 상위) + 20 random control
- Energy + Humor 2축만
- `selection_reason` 숨김
- 산출: `ml_transition_energy_humor_pilot_candidates_60.jsonl`, `..._review_60.csv`

**B3. train-120 첫 40개 + Intimacy**
- 기존 `ml_transition_train_active_ec_candidates_120.jsonl`에서 `selection_reason` 5종 + 소스 섞어 40개
- 축: Energy + Curiosity + Intimacy (Intimacy를 같은 발화에 얹어 중복 검수 비용 절감)
- 산출: `ml_transition_train_first40_review.csv`
- 나머지 80개는 이 40개의 label yield/agreement 확인 후 결정

### C. 병행 코드 작업 (사람 라벨 불필요)

**C1 = roadmap item 1 (reviewer calibration)**: B1의 후보 추출/CSV 스크립트 + `export_axis_review_csv.py` 확장(calibration/pilot review_set, reviewer_slot, 행 복제).

**C2 = roadmap item 3 (partial-label 학습 지원)**: `ai/ml_baseline.py`
- `_validate_axes` 옆에 `_validate_partial_axes(raw, allow_missing=True)` — 최소 1축, 있는 축만 0~100 검증
- `AxisTrainingExample`에 `label_source: dict[str, str]` 추가 (축별 provenance: `draft`/`human`/`human_correction`)
- `TfidfKnnAxisRegressor.predict`: 축마다 그 축을 가진 이웃만 골라 가중평균. 해당 축 보유 이웃이 k개 미만이면 있는 만큼, 0개면 그 축은 `None`
- 같은 발화의 human correction이 기존 draft 행과 **둘 다** 이웃으로 잡히면 축별로 human 우선(중복 집계 방지) — `_dedupe_by_utterance_per_axis` 헬퍼
- 누락 축은 누락으로 유지 (AI-draft로 안 채움 — 라벨 위조 금지 원칙)
- 유닛테스트: partial label fit/predict, human 우선, 이웃 부족 시 None
- **구현만. pilot 결과 안 기다림. 유용성 검증(학습곡선)은 후속.**

**C3 = roadmap item 7 (bucket-sensitivity)**: 신규 스크립트 `scripts/bucket_sensitivity_gold200.py`
- 1단계: `draft_label_nict_jle_candidates.py` / `build_*` 체인 추적해서 3,137행 draft 라벨 생성 시 `sample_bucket`이 실제로 어떻게 들어갔는지 확인 (읽기 전용)
- 2단계: `classify_bucket()`을 `ml_transition_gold_stratified_candidates_200.jsonl` 200행에 적용해 `sample_bucket` 재계산
- 3단계: `diagnose_gold_vs_ai_draft.py`를 (a) 기본 bucket, (b) 재구성 bucket으로 각각 실행 → 축별 Spearman/MAE/bias/sd_ratio 비교표
- 결과 명명: **"bucket sensitivity analysis"** (원래 bucket 복원 아님, Codex 지적). "좋게 나오는 bucket 고르기" 안 함 — 결정론적 `classify_bucket` 하나만.
- Curiosity 0.83이 과장/축소 어느 쪽인지 확정

**C4 = EVIDENCE NEEDED #6**: `ai/evaluate_axis_analyzers.py`
- `_pearson()` 상수입력 시 `0.0` 대신 `float('nan')` 반환 + 리포트에 `valid_axes=N/5`, NA 축 표시
- 평균 집계는 NA 축 제외하고 계산, 제외한 축 명시

### D. 실행 순서

1. **A1 + A2 먼저** — 격리를 미루면 그 사이 B/C 실험이 121개 중 일부를 봐버릴 위험 (Codex 지적)
2. C2(partial-label) + C3(bucket sensitivity) + C4(_pearson NA) 병행 — 사람 라벨 불필요
3. C1 + B1/B2/B3 CSV 생성 → 팀 전달
4. 검수 진행 중: ablation 사전 설계, 평가 comparator/코드 고정
5. 검수 결과(label yield, agreement) → 전체 검수 확장 + rubric 고정 + 학습곡선

## 확인 필요 / 내가 불확실한 것

1. **2인 채점 리소스**: calibration 48 + pilot 60 + train 40 = 148 발화, 2인 독립이면
   ~296 발화-검수 건. 팀에 실제 검수자 2명 확보 가능한가? 안 되면 1명 + 일부 중복으로 축소?
2. **후보 소스 제한**: B는 train reservoir만 쓰는 게 맞나? calibration은 gold/train
   양쪽 소스를 봐야 reviewer 효과가 더 잘 보일 수도 있는데, gold reservoir를 건드리면
   최종 test pool이 줄어든다. train만으로 충분한가?
3. **partial-label 접근**: 축별 이웃 필터(공유 feature 공간 유지)로 충분한가, 아니면
   Codex가 언급한 "축별 별도 처리"가 필요한가? 나는 전자를 제안.
4. **NICT provenance**: `source_line` 매칭이 실패하면 NICT 132개를 최종 test에서
   빼야 하나, 아니면 unknown 상태로 별도 보고만 하고 유지하나?
5. **train-120 재사용**: 첫 40개를 뽑을 때 나머지 80개와의 관계 — 80개는 완전 보류인가,
   아니면 40개 결과 나오기 전에 CSV는 미리 만들어둬도 되나?
