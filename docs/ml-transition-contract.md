# ML Transition — Evaluation & Annotation Contract

작성: 2026-09-10. 이 문서는 ML 전환 판정에 쓰이는 **데이터 역할, 라벨 정밀도, 검수 절차,
평가 규약**을 고정한다. `docs/ml-transition-plan.md`(전략)와 충돌하면 이 문서가 우선.

근거: `docs/ai-collab/archive/2026-09-07-gold200-diagnosis/DECISION.md`,
`docs/ai-collab/archive/2026-09-08-roadmap-review/DECISION.md`,
`docs/ai-collab/DECISION.md` (실행 계획, 2026-09-10, Codex Round 2 검토 완료).

> **STATUS 2026-09-10** — Phase 0 산출물 검증 완료 · 재실행 안전성 보완 완료 /
> Phase 1 진행 중.
> - 예약 스크립트 fail-safe 완료: provenance 복구 <100% 또는 `--expect-*-sha256`
>   불일치 시 **파일 쓰기 전에 중단**. 정상 입력에서 기존 176행 / 156그룹 분할
>   byte-identical 재생성 확인.
> - `evaluate_axis_analyzers.py`: 필수 축 NA면 `best_by_spearman` 판정 보류
>   (verdict withheld). MAE · 공통 유효 축 보조 비교는 유지.
> - partial-label ML 지원 완료: `_validate_partial_axes`, `label_source`,
>   `TfidfKnnAxisRegressor.predict_partial()`, `fit(require_full_axes=True)` 배포 어댑터.
> - bucket 민감도: `scripts/bucket_sensitivity_gold200.py` 추가. §11 참조.
> - **미고정(최종 평가 전 필수)**: §9 CI level / bootstrap 반복 수 / seed,
>   고정 hybrid 버전. §7 검수량은 실제 후보 수 확정 후 재계산 (아래 provisional).

---

## 1. 데이터 역할

| 세트 | 파일 | 역할 | 학습 사용 |
|---|---|---|---|
| gold-200 human | `ml_transition_gold_human_200.jsonl` | **dev / diagnosis set** (반복 진단에 이미 사용됨) | 절대 금지 |
| 3,137행 실험셋 | `axis_dataset_combined_real_speech_experimental.jsonl` | 모델 반복용 (AI-draft 라벨, HCRC 포함) | 실험용만 |
| 예약 최종 pool | `ml_transition_reserved_final_test_pool.jsonl` | **frozen acceptance test** — `final_gate` 106행 + `gate4_reproduction` 70행 | 절대 금지, 모델 확정 전까지 결과 안 봄 |
| 예약 audit | `ml_transition_reservation_audit.jsonl` | gold-600 − dev-200 = **400행 전체 기록** (reserved_clean 176 + 제외 224), 각 행에 포함/제외 태그 | — |

- gold-200은 더 이상 "frozen acceptance test"가 아니다. 최종 판정은 예약 pool로만.
- 전환 대상 **학습 구성**(HCRC 제외 여부 등)을 실험용 3,137행과 별도로 고정한다.
  실험셋 성능을 전환 학습셋 성능으로 이식하지 않는다.

## 2. 예약 최종 test pool (2026-09-10 확정)

`scripts/reserve_ml_transition_final_pool.py` 실행 결과:

- NICT provenance: 학습 600행 전부 `source_line` → 원본 발화 일치(600/600), 그룹 470개 복구
- gold-600 − dev-200 = 400행 → `reserved_clean` 176행 / 156그룹
  (학습 그룹 + dev-200 그룹 모두 미겹침, seed 20260910)
- 분할: `final_gate` 106행 (NICT 42 / Taskmaster 63 / **AMI 1 = 참고용**),
  `gate4_reproduction` 70행 (NICT 28 / Taskmaster 42)
- 예약은 **그룹 전체 + 인접 발화**에 적용. 이후 calibration / pilot / 마이닝 / 검수는
  이 156그룹을 건드리지 않는다.
- 제외: `train_contaminated` 71 / `dev_analyzed` 26 / `train_and_dev` 127
- 각 행 태그: `train_overlap`, `dev_overlap`, `provenance_verified`, `exposure_status`,
  `reservation_role`, `reference_only`, `reservation_seed`, `nict_raw_sha256`, `training_sha256`
- **재실행 안전장치**: `reserve_ml_transition_final_pool.py`는 NICT provenance가
  600/600 미만이면 중단(`--allow-unverified-provenance`로만 우회). baseline 고정용
  `--expect-nict-raw-sha256` / `--expect-training-sha256` 불일치 시에도 **쓰기 전 중단**.
  정상 입력에서 기존 pool·분할은 byte-identical 재생성.

### AMI 범위 제한 (사용자 결정 2026-09-10)

- 최종 gate는 **NICT + Taskmaster 중심**으로 판정.
- AMI 1그룹(`reference_only=true`)은 참고 결과로만 보고, AMI 전체로 일반화하지 않는다.
- 후속 작업: 학습·dev와 안 겹치는 AMI 그룹 확보. 사람 라벨링·gate 통과 기준은 생략 안 함.
- NICT provenance 복구는 현재 원본 snapshot(`nict_jle_learner_utterances.jsonl`,
  sha256 로그는 pool 파일에 기록) 기준. 원본 재추출 시 재검증 필요.

## 3. 라벨 정밀도

- **사람 원점수 · 사람 평균 · 학습/평가 target**: 소수점 보존 (0.5 단위 평균 등).
- **모델 최종 출력**: 정수 (별도 정책). `AxisResult` 계약은 유지.
- 현재 3곳에서 암묵적 절삭 발생 — 수정 대상:
  - `scripts/build_human_reviewed_axis_dataset.py` `int(float(value))`
  - `ai/ml_baseline.py::_validate_axes()` `int()`
  - `scripts/select_ml_transition_annotation_sets.py::load_model_examples()` `int()`
- `ai/ml_baseline.py::_validate_partial_axes()` (신규, `allow_partial=True` 경로)는
  cast 전에 유한 수 + 0~100 범위를 검사한다. 배포 경로 `_validate_axes()`는 그대로.
- **현재 `ml_transition_gold_human_200.jsonl`은 이미 절삭된 정수로 빌드됨**
  (reviewer-avg 0.5 단위가 build 시점에 소실). 정밀도 트랙 진입 시 원본 CSV에서
  소수점 보존해 재빌드한 별도 파일로 "정밀도 전/후"를 비교한다. 기존 파일의
  보고 지표를 재빌드 값으로 바꿔 부르지 않는다.

## 4. 검수 입력 (reviewer가 보는 것)

- **현재 발화만.** 모델 추론 입력(`example.utterance`)과 일치시킨다.
- 이전 맥락(previous_turn) / 다음 턴(next_turn) / annotation event / audio를 보여주는
  검수는 **별도 과제**로 표기하고, 그 결과를 text-only 모델 평가와 같은 선상에서
  비교하지 않는다.
- `selection_reason` 등 선정 메타는 CSV에서 제외 (blind).

## 5. 검수 CSV / ID 스키마

- `dataset_partition`: `train` / `dev` / `test` — 데이터 역할
- `annotation_batch`: `calibration` / `pilot` / `first40` — 검수 배치
- `item_id`: 배치 내 안정적 ID. 원본 candidate ID와의 매핑을 숨긴 manifest에 보존.
  40행 subset을 재번호화해 기존 train-120 ID에 잘못 연결하지 않는다.
- 원점수 식별키: `(annotation_batch, item_id, reviewer_slot)` + 실제 `reviewer_id`.
  slot A/B는 **서로 다른 사람**임을 확인.
- **reviewer별 별도 blind export.** 같은 CSV의 인접 복제 행에서 상대 점수가 보이면
  독립 채점이 아니다. 항목 순서도 무작위화하고 seed를 보존.
- 무결성 검사: 누락 / 중복 / 범위 / 축 schema / 발화·context 일치.
- 구현: `scripts/export_axis_review_csv.py --annotation-batch <b> --reviewers 2 --seed <n>`
  → slot별 blind CSV(`<stem>.slotA.csv` / `.slotB.csv`) + 비공개 manifest
  (`<stem>.manifest.json`, item_id↔candidate 매핑·slot별 순서·seed 보존).
  legacy `--review-set` 경로는 gold-200 / train-120 재현용으로 유지(출력 byte-identical).
- import: `scripts/build_human_reviewed_axis_dataset.py --manifest <manifest> --input slotA.csv --input slotB.csv`
  → PK `(annotation_batch, item_id, reviewer_slot)` 검증, item×slot **원점수 1행씩**
  (`label_status=human_reviewed_blind_raw`, `label_source` 축별 `human`).

## 6. 집계 / 조정

- 원점수는 **덮어쓰지 않는다.** raw JSONL은 불변.
- aggregation / adjudication은 별도 산출물 (`scripts/aggregate_axis_reviews.py`):
  raw → item별 평균(소수점 보존) + `slot_spread` + `--disagreement-threshold` 초과
  항목 목록 + `<output>.report.json`(축별 slot간 평균/최대 차이).
  `--adjudication <json>`(`{item_id: {axis: value, note}}`)은 평균 위에 얹고
  `label_source`를 `human_adjudicated`로 표시, `raw_scores`에 원점수 보존.
- 평균만으로 불일치를 없애지 않는다. threshold 초과 항목은 제3자 조정 대상.
- A/B의 같은 우선순위 human label은 집계·조정을 먼저 하고, 임의 행 순서로 하나를
  고르지 않는다.

## 7. 검수자 (2026-09-10 확정)

- **검수자 4명 확보** (팀원 4인). calibration은 slot A/B/C/D 4행 (inter-rater 신호가
  많을수록 기준 차이 탐지에 유리). pilot / first40은 slot A/B 2행 유지
  (규모가 작고 축이 특화됨; 필요 시 확대).
- calibration 표본 수는 **탐지 확률**에서 계산 (2026-09-10 Codex round): 한 발화에서
  5축 중 하나라도 두 검수자 점수차 >20점인 "큰 불일치"가 한 출처에서 ≥10% 빈도로
  발생할 때, 그 출처에서 최소 1건 이상 볼 확률 ≥95%. `0.9^n ≤ 0.05 → n ≥ 29`,
  출처당 30으로 반올림. **출처별 보장이지 세 출처 동시 보장은 아님**(동시 보장은
  Bonferroni로 출처당 ~39 필요, 이번 범위 밖).
- 규모 (2026-09-10, 검수자 4명 확정):
  | batch | items | axes | slots | 축 점수 |
  |---|---:|---:|---:|---:|
  | calibration | 90 (AMI 30 / NICT 30 / Taskmaster 30) | 5 | 4 | 1,800 |
  | pilot (E/H) | 54 | 2 | 2 | 216 |
  | first40 (E/C/I) | 40 | 3 | 2 | 240 |
  | **합계** | | | | **2,256** |
  발화-검수 건 = 90×4 + 54×2 + 40×2 = **548**. 조정/재채점 비용 별도.
  pilot 54 = event 13(실제 라흐터 가용치, 라운드업 안 함) + AMI 비-라흐터 대조 9
  (calibration이 AMI 39 non-laugh 그룹 중 30 사용 후 잔여) + model-disagreement 16
  (Energy 8 / Humor 8) + residual random 16.
- calibration은 **무작위 표본**이다. 희소 사례(Humor 등)를 의도적으로 넣지 않는다
  (넣으면 위 탐지 확률 해석이 깨진다). 적용 범위 = 후보 pool, 자연 사용 분포 아님.
- 실제 B2(pilot)/B3(first40) 채점은 **calibration 불일치 검토 + rubric/input version
  고정 후** 시작한다. 후보 + 빈 slot CSV는 생성 완료 (아래 §12).

## 8. NA (상수 입력 상관계수) 정책

- `_pearson()`이 상수 입력에서 반환하던 `0.0`을 `float('nan')`으로 바꾼다
  (`ai/evaluate_axis_analyzers.py` **및** `scripts/diagnose_gold_vs_ai_draft.py` 둘 다).
- 리포트: `valid_axes=N/5`, NA 축 이름, 공통 유효 축 보조 평균, 표본/그룹 수.
- **필수 축의 rho가 미정의면 5축 gate 통과로 판정하지 않는다.**
- NA-제외 평균은 모델마다 다른 축 집합의 평균일 수 있다 — gate #2/#3 의미를 조용히
  바꾸므로, 공통 유효 축 평균을 함께 보고하고 단독 판정 근거로 쓰지 않는다.
- human target 상수(시험 정보 부족) vs model prediction 상수(모델 퇴화)를 구분해 보고.
- MAE는 rho NA를 이유로 제외하지 않는다.
- bootstrap 재표본에서 상수가 되는 빈도와 CI 가능 여부도 보고.
- 평균 / best-model 선택 / gate / diagnostic 경로 전부 NA-aware로 점검 (report 출력만 아님).

## 9. 최종 평가 규약

- **고정 comparator 3종**: 현재 런타임 `rule` / 고정된 기존 `hybrid` / 후보 ML +
  그 ML에 연결된 hybrid. ML을 바꾸면 hybrid도 바뀌므로 기존 기준선을 함께 유지한다.
- rule이 현재 기본이므로 **rule 대비 퇴행도 보고**한다.
- 명시 항목: training 파일 hash, rule 버전, k / word-ngram, HCRC 포함 여부.
- 지표: 소스별 · 축별 MAE / rho, **source-group 단위 paired bootstrap** 불확실성,
  독립 그룹 수.
- **최종 평가 실행 전 반드시 아래를 이 문서에 값으로 못박는다 (현재 미정 = 평가 착수 불가):**
  - CI level (예: 95%)
  - bootstrap 반복 수 (예: 10,000)
  - bootstrap seed (고정 정수 1개)
  - 비교 대상 hybrid의 정확한 버전 — rule 버전 + k + word-ngram + training 파일 hash로 식별.
    후보 ML이 바뀌면 그 ML에 연결된 hybrid도 바뀌므로, "고정 hybrid"는 별도 스냅샷으로
    보존하고 hash를 여기 기록한다.
- 위 값을 고정하기 전에는 `final_gate` 결과를 산출·열람하지 않는다.
- 0.20 MAE / 0.03 rho 차이는 점추정만으로 강한 결론 금지 — CI 기반 판정.
- gold의 source × (Energy×Curiosity) 층화 결과 ≠ 자연 사용 분포 성능. 목표 분포 평가와
  rare-case 진단을 분리.

## 10. ML Acceptance Gate (갱신)

`final_gate` 그룹에서 아래 4개 전부 만족 + `gate4_reproduction` 그룹에서 재현:

1. ML 평균 MAE가 hybrid보다 0.20 초과로 나쁘지 않음 (CI 고려)
2. ML 평균 Spearman ≥ hybrid 평균 Spearman (필수 축 rho 미정의 시 통과 아님)
3. 어떤 축도 hybrid보다 0.03 초과로 나쁘지 않음
4. `gate4_reproduction` 그룹에서 모델·분석 계획을 **고정한 채** 재현 (동일 test 재실행
   아님). 최종 test를 보고 튜닝했다면 그 test는 이후 dev로 강등.

통과 + **사용자 명시 승인** 후에만 `PALLY_AXIS_ANALYZER=ml`. `hybrid`는 한 릴리스 동안
되돌릴 수 있는 config fallback으로 유지.

## 11. 순서 (DECISION 정렬)

**모든 dev 실험은 `final_gate` 결과를 열기 전에 끝낸다.** `final_gate` /
`gate4_reproduction`는 §9 파라미터 고정 + 모델·분석 계획 확정 이후 **1회** 연다.
그 전에 열면 그 pool은 dev로 강등된다 (§10.4).

dev(=gold-200 + calibration/pilot/first40)에서 먼저 할 것:

- **bucket 민감도 (완료 — `scripts/bucket_sensitivity_gold200.py`)**:
  - generic vs NICT `classify_bucket`는 NICT 학습행 132/600에서 불일치 →
    "generic classifier 선택"은 중립 복구가 아니라 모델링 선택.
  - `draft_axes()`는 저장된 NICT 라벨을 221/600 행에서 재현 못함 (Formality/Energy
    오프셋) → "동일 teacher" 주장은 근사.
  - default-bucket 가정은 축별 bias뿐 아니라 **rank도** 바꾼다 (Intimacy rho
    0.09 → 0.29). `diagnose_gold_vs_ai_draft.py` 결과는 이 가정을 명시해 읽는다.
- 대문자 비율 · 반복 문자 길이 feature ablation — baseline 고정, 한 번에 하나씩.
  코퍼스/STT의 대문자·구두점 보존 여부 먼저 확인.
- human-only / draft-only / 혼합 비중 학습곡선.
- Intimacy 전면 교체 — calibration 48 + first40 Intimacy 결과 후 판단 (계속 보류).

gate 이후 / 별도 트랙:

- 새 AMI 그룹 확보 (학습·dev 미겹침).

## 12. Phase 2 산출물 (2026-09-10, 후보 + 빈 CSV만 / 채점 전)

| batch | candidate 파일 | manifest | slot CSV | 상태 |
|---|---|---|---|---|
| calibration 90 | `ml_transition_calibration_candidates_90.jsonl` | `ml_transition_calibration_review.manifest.json` | `..._calibration_review.slot{A,B,C,D}.csv` + `calibration_scoring_slot{A,B,C,D}.xlsx` | 채점 가능 (dev, calibration 먼저) |
| pilot 54 | `ml_transition_pilot_eh_candidates.jsonl` | `ml_transition_pilot_review.manifest.json` | `..._pilot_review.slot{A,B}.csv` | **채점 보류** — calibration 검토 + rubric 고정 후 |
| first40 40 | `ml_transition_train_first40_candidates.jsonl` | `ml_transition_first40_review.manifest.json` | `..._first40_review.slot{A,B}.csv` | **채점 보류** — 동일 |
| first40 remainder 80 | `ml_transition_train_active_remainder_candidates.jsonl` | — | 미생성 | 사용/채점 보류 |

- 생성: `scripts/build_calibration_pilot_sets.py` (할당 순서 = 라흐터 예약 → calibration
  30/출처 → AMI 비-라흐터 대조 → disagree → residual), `scripts/build_train_first40_set.py` (B3).
  공통 seed 20260910. plan JSON에 arm별 quota·source 배분 기록.
- calibration: 적격 그룹 무작위 + 그룹 내 발화 무작위, 출처별 서로 다른 30그룹.
  라흐터 그룹 제외(pilot event arm용).
- pilot arm: event 13 / ami_nonlaugh_control 9 / disagree(E8·H8) 16 / residual 16.
  event yield는 실제 라흐터 가용치(train-120·reserved 제외 후 13그룹, 라운드업 안 함).
  대조군 9 = AMI non-laugh 39 − calibration 30. AMI 신규 그룹 확보 시 대조군 확대.
- reservoir는 gold reservoir와 canonical group 교집합 0 → reserved pool 유출 불가 (스크립트가 assert).
- 채점 시작 전제: calibration 2인 불일치 검토 → rubric/input version 고정 → §7 검수량 재확인.
- 검수자 배포용: `scripts/export_calibration_workbook.py` → `calibration_scoring_slot{A,B,C,D}.xlsx`
  (시트: 안내 / 채점 기준표 / 채점 예시 / 채점 시트, 0~100 정수 검증). 검수자 1명당 파일 1개,
  같은 90발화·순서만 다름. slot별 문항 순서는 manifest `slot_order` 사용.
  채점 완료본은 slot CSV로 옮겨 `--manifest` importer에 넣는다. importer는 제출된 slot만
  완결성 검사하므로 4명이 다 끝나기 전에 부분 집계 가능.
  (openpyxl 필요 — dev 전용 도구 의존성, 런타임 아님)
- calibration 채점 후 확인: 출처별 큰 불일치 비율 / 축별 평균 부호차 / 축별 평균 절대차 /
  불일치 원인. rubric 수정 시 기존 90개는 "기준 개선용 데이터"로 남기고 효과는 새 표본에서 재검증.
