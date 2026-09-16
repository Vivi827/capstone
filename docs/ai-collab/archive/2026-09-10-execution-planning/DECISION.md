# Decision — Round 3 (실행 계획 확정)

작성: 2026-09-10. Codex Round 2의 검증 가능한 주장 5개를 직접 재현했다 — **전부 정확히 일치**.

## 검증 결과 (Codex 주장 vs 재현)

| Codex 주장 | 재현 결과 |
|---|---|
| NICT 학습 600행이 `nict_jle_learner_utterances.jsonl[source_line-1]`와 발화 일치 | **600/600 정확 일치**, 학습 그룹 470개 복구 |
| gold-600 − dev-200 = 400행, 학습 그룹만 제외 시 202행(AMI 5 / NICT 81 / Taskmaster 116) | **정확히 일치** |
| 학습 + dev 그룹 모두 제외 시 176행 / 156그룹 (AMI 1 / NICT 70 / Taskmaster 105) | **정확히 일치** |
| train reservoir의 laughter 후보 23개, 전부 AMI, train-120 그룹 제외 시 14개(13그룹) | **정확히 일치** |
| generic `classify_bucket(row)` vs NICT 저장 bucket = 132/600 불일치 / NICT 전용 `classify_bucket(text)` = 0/600 | **정확히 일치** |

## AGREED

- 방향(축별 처방, ML 전환 근거 아직 없음, gold-200은 dev)은 유지.
- **격리가 최우선.** 다른 어떤 실험(코드 작업 포함)보다 먼저 NICT provenance를 복구하고
  최종/재현 그룹을 예약한다. 미루면 그 사이 실험이 156그룹 중 일부를 봐버린다.
- train-only calibration 타당(train/gold reservoir canonical group 교집합 = 0).
- 행 복제로 원점수 보존은 맞지만, exporter만으로는 부족 — importer/aggregation
  round-trip과 reviewer별 blind export까지 한 계약으로 묶어야 한다.
- 공유 feature + 축별 유효 label top-k 접근 채택 (축별 별도 TF-IDF 모델은 후속 ablation).
- bucket sensitivity는 "가정 하 변화 방향 측정"이지 "역사적 teacher 복원"이 아니다.
- NA 축을 제외한 평균은 gate #2/#3의 의미를 조용히 바꾼다 — 필수 축 rho가 미정의면
  5축 gate 통과로 판정하지 않는다.

## DISAGREED / 정정 (내 Round 1 실행 계획 중)

- **"NICT 132개는 unknown으로 별도 보고만"은 틀렸다.** `source_line` join으로 470 그룹
  복구가 가능하고 실제로 600/600 일치한다. → A1은 이 복구를 반드시 포함. 다만 원본
  snapshot 의존이므로 file hash + 범위 + 발화 일치 3중 검사, 실패 행만 unknown 유지.
- **"clean 후보 121개"는 과소 계산이었다.** provenance 복구 후 학습 그룹만 제외하면
  202행, 학습+dev 그룹까지 제외하면 176행/156그룹. 단, 176행이 "충분한 최종 test"라는
  근거는 없다. AMI는 엄격 후보가 1그룹뿐 → 현재 풀로 AMI 일반화 입증 불가.
- **"B2 event-hint 20개"는 불가능하다.** train reservoir laughter 후보는 23개(전부
  AMI), train-120 그룹 제외 시 14개. B1 Humor 후보 6개와 같은 풀을 두고 경쟁한다.
  → event arm을 먼저 내부 예약하고 B1+B2 quota를 공동 계산, 부족 시 실제 개수로 축소
  (정책 사전 고정). event yield는 AMI 소스 효과와 교락 → AMI 비-event 대조 필수.
- **"C1 = exporter에 slot/set 추가"로는 끝까지 못 쓴다.** `build_human_reviewed_axis_dataset.py`가
  `all`/`energy-curiosity`만 지원, 중복 `review_id` 오류, `review_set` gold/train만.
  B2(Energy/Humor), B3(E/C/Intimacy)를 지원하지 않는다. importer + aggregation까지 범위.
- **"C2에서 None 반환"은 배포 계약과 충돌한다.** `AxisResult`는 5축 정수 필수,
  `MLAxisAnalyzer.analyze()`는 validation 실패 시 5축 전부 rule fallback, 평가기 hybrid
  산술은 None을 못 더한다. → 연구용 partial-prediction API를 분리하고, 배포 adapter는
  fit 시 모든 축 coverage를 요구한다. fallback 섞인 점수를 순수 ML로 보고 안 함.
- **"predict에서 label 없는 이웃 제거"의 순서가 틀렸다.** 현재 코드는 전체 similarity
  정렬 → top-k 자름. 그 다음 필터하면 더 먼 유효 label을 버린다. → 전체 순위에서 그
  축의 유효 label을 먼저 필터한 뒤 k개 선택, 축별 분모 계산.
- **"classify_bucket() 하나로 재구성"은 두 가지 재현 오차를 숨긴다.** (1) NICT 전용
  classifier가 별도 존재하고 generic과 132/600 다르다. (2) `draft_axes(저장 bucket)` vs
  저장 draft axes가 NICT 221행 다르다(Formality/Energy). → CONTEXT와 진단 스크립트의
  "현재 함수가 역사적 학습 라벨을 재현한다"는 서술은 성립하지 않는다. C3는 sampler
  오차 + teacher 오차를 둘 다 명시.
- **점수 정밀도 정책(이전 EVIDENCE #5)이 C 범위에서 빠졌다.** `int(float())`(importer),
  `_validate_axes()` `int()`(ML loader), `load_model_examples()` `int()`(선정기) 3곳이
  각각 절삭한다. → Phase 0 계약에 포함.
- **D3(3 CSV 동시 전달)이 "calibration 후 first40 채점"과 충돌한다.** 후보 + 빈 CSV
  준비는 병행 OK, 실제 B2/B3 채점은 calibration 불일치 검토 + rubric/input version
  고정 후 시작.

## EVIDENCE NEEDED (실행 중 확인)

1. NICT `source_line` join의 file hash / 범위 / 발화 일치 3중 검사 통과율 (600/600은
   현재 snapshot 기준).
2. B1+B2 공동 quota 계산 시 각 arm의 실제 가용 후보 수 (event 14, model-disagreement,
   residual random) 및 소스별 분포.
3. C2 구현 후: top-k 밖 유효 label 회수 테스트, 중복 correction 추가 전후 IDF 불변,
   미검수 축 누락 유지, 축별 coverage + adapter 동작.
4. C3: NICT 221행 draft_axes 불일치의 역사적 원인(버전 변경 등) — 이번엔 확정 안 함,
   두 variant 결과만 보고.
5. 실제 검수자 2명 확보 가능 여부 (repo만으로 확인 불가 — 사용자 확인 필요). 1인 +
   부분 중복으로 축소 시 "2인 교차 채점 증거"라고 부르지 않고 한계 재명세.
6. 최종 test 176행 / 156그룹을 최종 gate용 / gate#4 재현용으로 어떻게 분할할지 (seed
   고정). AMI 1그룹 → 별도 AMI 그룹 확보 or 평가 범위 명시적 제한.

## ACTION (Phase 순서 — Codex 권장안 채택)

### Phase 0 — 계약 고정 (다른 작업 시작 전, 이것만 먼저)

**P0-1. NICT provenance 복구 + 최종 test pool 예약** (읽기 전용 스크립트)
- `scripts/reserve_ml_transition_final_pool.py` (신규)
- NICT 학습행 → `source_line` join (hash/range/text 3중 검사) → 470 그룹 복구
- gold-600 − dev-200 = 400행, 각 행에 `train_overlap` / `dev_overlap` /
  `provenance_verified` / `exposure_status`
- 산출: `data/fixtures/ml_transition_reserved_final_test_pool.jsonl` (176행/156그룹,
  train+dev 그룹 제외) + `data/fixtures/ml_transition_reservation_audit.jsonl` (제외된
  224행 + 이유)
- 156그룹을 `final_gate` / `gate4_reproduction` 두 세트로 분할 (seed 고정), 각 행에 태그
- 예약은 **그룹 전체 + 인접 발화**에 적용 — 이후 B/마이닝/검수는 이 그룹을 건드리지 않음

**P0-2. 평가·검수 계약 문서** — `docs/ml-transition-contract.md` (신규) + `docs/ml-transition-plan.md` 갱신
- 점수 정밀도: human raw/mean + train/eval target = 소수점 보존, model 출력 = 정수(별도)
- 검수 input: 현재 발화만 (model input 일치). prev-context / next / event / audio = 별도 과제로 표기
- ID 스키마: `dataset_partition`(train/dev/test) + `annotation_batch`(calibration/pilot/first40)
  분리, 안정 `item_id` + 원본 candidate ID 매핑, PK `(batch_id, item_id, reviewer_slot)` + 실제 `reviewer_id`
- 집계: raw 불변, aggregation/adjudication 별도 산출물 (검수자 수, rubric version, 수정 이력)
- NA 정책: 필수 축 rho 미정의 → 5축 gate 통과 판정 안 함. human-constant(정보 부족) vs
  model-constant(퇴화) 구분. MAE는 rho NA로 제외 안 함. bootstrap 재표본 상수화 빈도도 보고
- comparator: 현재 rule / 고정 기존 hybrid / 후보 ML+연결 hybrid. training file hash + rule
  version + k/ngram 명시. rule 대비 퇴행 보고. 승인된 gate 몰래 변경 금지
- bootstrap: 모든 모델 동일 source-group 재표본. CI level / reps / seed 결과 전 고정.
  불확실 시 보류 정책
- gate #4: 별도 예약 그룹(gate4_reproduction)에서만. 최종 test 보고 튜닝 시 그건 이후 dev
- gold-200 → "dev/diagnosis set" 공식 재정의. leakage 결론 → "영향 크기 미확정, nonoverlap
  60행(AMI 2/Taskmaster 58, 편중)에서도 ML 우위 관찰 안 됨"
- 전환 학습 구성(HCRC 제외 등)을 실험용 3,137행과 별도로 고정

### Phase 1 — 코드 작업 (사람 라벨 불필요, P0 후 병행)

**P1-1 = roadmap item 3. partial-label 학습 지원** — `ai/ml_baseline.py` + 연구용 API 분리
- `_validate_partial_axes(raw, min_axes=1)` — cast 전 유한 수 + 범위 검사, 소수점 보존 옵션
- `AxisTrainingExample.label` 부분 dict 허용 + `label_source: dict[str, str]`
  (`draft`/`accepted_draft`/`human`/`human_correction`)
- `fit()`: 같은 발화 정규화 중복은 feature 문서로 **한 번만** 카운트 (IDF 불변), 축별
  label/provenance는 provenance ID로 연결
- 새 `predict_partial(utterance) -> dict[str, float | None]`: 전체 순위 → 축별 유효 label
  필터 → top-k → 축별 가중평균. 유효 label 0개면 None. "유효 label 없음" ≠ "similarity
  전부 0" 구분
- 배포 경로(`MLAxisAnalyzer`)는 fit 시 모든 축 coverage 요구하는 adapter — 미충족 시 명시적 에러
- A/B 같은 우선순위 human label은 aggregation 산출물에서 먼저 조정 (임의 행 순서 금지)
- 유닛테스트: top-k 밖 회수, dedup 전후 IDF 불변, 미검수 축 누락 유지, None vs zero-sim

**P1-2 = roadmap item 7. bucket sensitivity** — `scripts/bucket_sensitivity_gold200.py` (신규)
- variant A: generic `classify_bucket(row)` / variant B: NICT행엔 NICT 전용 `classify_bucket(text)`,
  나머지는 generic (소스별 가정, 결과 보기 전 고정)
- 두 variant + 기본(personal_statement) 세 경우로 `draft_axes` 재계산 → gold-200 human과
  축별 Spearman/MAE/bias/sd_ratio 비교표
- sampler 재현 오차(NICT generic 132/600) + teacher 재현 오차(NICT draft_axes 221행) 둘 다 보고
- in-memory 2-variant 비교 함수/CLI (`diagnose_gold_vs_ai_draft.py`는 입력 경로 고정이라 확장)
- 결과 명명: "명시한 가정 하 현재 dev에서의 변화 방향" — Curiosity 0.83 과장/축소 "확정" 아님

**P1-3 = EVIDENCE NEEDED #6. `_pearson()` NA 처리** — `ai/evaluate_axis_analyzers.py` + `scripts/diagnose_gold_vs_ai_draft.py` **둘 다**
- 상수 입력 → `float('nan')` 반환
- 리포트: `valid_axes=N/5`, NA 축 이름, 공통 유효 축 보조 평균, 표본/그룹 수
- 평균/best-model 선택/gate/diagnostic 경로 전부 NA-aware로 점검
- MAE는 NA로 제외 안 함

**P1-4 = roadmap item 1(코드부분) + C1. exporter/importer/aggregation 확장**
- `export_axis_review_csv.py`: `annotation_batch` + `dataset_partition` + `item_id` +
  `reviewer_slot`, axes에 `energy-humor` / `energy-curiosity-intimacy` 추가, **reviewer별
  별도 blind export** (인접 복제 행 노출 금지), 순서 무작위화 + seed 보존
- `build_human_reviewed_axis_dataset.py`: 새 axes/batch 지원, `(batch, item, slot)` PK,
  중복 review_id 허용(slot 다르면), partition 검사 완화
- 신규 `scripts/aggregate_axis_reviews.py`: raw 불변, slot별 → 평균/adjudication 산출물
  (reviewer 수, rubric version, 큰 불일치는 제3자 조정 플래그)
- round-trip 유닛테스트 (export → 채점 시뮬 → import → aggregate)

### Phase 2 — 사람 라벨링 CSV (P0 계약 고정 후, 후보/빈 CSV 준비는 P1과 병행)

**P2-1. B1 calibration 48** — `scripts/build_calibration_pilot_sets.py` (신규, B1+B2 공동)
- train reservoir에서 AMI/NICT/Taskmaster 각 16, `canonical group` 중복 없음, 예약 그룹 제외
- B2 event arm과 quota 공동 계산 (희소 후보 충돌 방지)
- 5축, reviewer_slot A/B 2행, `annotation_batch=calibration`, `dataset_partition=dev`
- "자연 분포 성능 추정용 아님" 명시

**P2-2. B2 Energy/Humor pilot** — 같은 스크립트
- event-hint: 실제 가용치(train-120 그룹 제외 후 14, AMI-only)만큼만 + **AMI 비-event 대조**
- model-disagreement: rule vs ML의 Energy/Humor 절대차 상위 (합치는 방식 = 축별 quota, 사전 고정)
- residual random: 앞 두 arm 제외 후 잔여 모집단 ("잔여 대조"로 명시)
- Energy + Humor 2축, reviewer_slot A/B, `annotation_batch=pilot`
- 소스별 결과 보고 (event 효과 vs AMI 효과 분리)

**P2-3. B3 train first-40** — `scripts/build_train_first40_set.py` (신규)
- `ml_transition_train_active_ec_candidates_120.jsonl`에서 이유(40/40/15/15/10)×소스 배분
  별도 고정, 첫 40개 그대로 쓰지 않음
- 재번호화 시 원본 candidate ID 매핑 보존
- E/C/Intimacy 3축, `annotation_batch=first40`
- **채점은 calibration 불일치 검토 + rubric 고정 후 시작**
- 나머지 train-80: 빈 CSV 준비 가능, 채점/사용 보류

### Phase 3 — 검수 결과 후

- label yield / inter-rater agreement를 소스·선택 경로별로 검토 → 전체 검수 확장 결정
- rubric 고정 → 학습곡선 (human-only / draft-only / 혼합 비중), 기존 unigram/bigram, k, 소스별
- ACTION #5: 대문자 비율 / 반복 문자 길이 feature ablation — baseline 고정, 한 번에 하나만.
  코퍼스/STT가 대문자·구두점 보존하는지 먼저 확인
- 최종 gate 채점 (`final_gate` 그룹) + `gate4_reproduction` 재현 → 4개 기준 통과 →
  **사용자 명시 승인** → `PALLY_AXIS_ANALYZER=ml`
- Intimacy 전면 교체는 계속 보류 (calibration 48 + first40 Intimacy 결과 후 판단)

## 사용자 확인 완료 (2026-09-10)

1. **검수자 2명 확보 가능** → calibration/pilot CSV는 `reviewer_slot` A/B 2행,
   inter-rater agreement + scale bias 측정.
2. **AMI 최종 test는 이번 범위 밖으로 명시** → 최종 gate는 NICT + Taskmaster 중심.
   AMI 1그룹은 참고 결과로만 보고, AMI 전체로 일반화하지 않음. 후속 작업으로 학습·dev와
   안 겹치는 AMI 그룹 확보. 사람 라벨링·gate 통과 기준은 생략하지 않음.
3. 실행 순서: Phase 0 → Phase 1 코드 병행.
