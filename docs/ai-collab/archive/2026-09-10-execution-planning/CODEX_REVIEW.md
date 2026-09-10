# Codex Round 2 — 실행 계획의 방법론·실행 가능성 검토

2026-09-10. **방향은 유지하되 A1, B/C1, C2, C4의 계약을 보완한 뒤 실행해야 한다.** 가장 큰 새 발견은 NICT provenance를 실제로 복구할 수 있다는 점이다. 현재 파일 기준 최종 후보는 기존 학습 그룹만 제외하면 202행, 이미 분석한 dev 그룹까지 제외하면 176행이다. 이는 최종 시험의 충분성이나 대표성을 보장하는 숫자가 아니다.

검증 범위: CONTEXT, CURRENT_TASK의 Round 2 지시, 현재 CLAUDE_REVIEW, 2026-09-08-roadmap-review의 DECISION/CODEX_REVIEW, 관련 Python 구현과 실제 JSONL/CSV를 읽었다. `python -B -`로 메모리 내 집계와 기존 순수 함수의 재적용만 수행했다. 모델 재학습, 신규 라벨 생성, 최종 후보의 예측/점수 검토는 하지 않았다. 이 리뷰 이외의 파일 및 git 상태를 변경하는 명령은 실행하지 않았다. 기존 성능 표는 이번에 재평가한 수치가 아니다.

## 1. [최우선] A1: NICT 132개는 더 이상 전부 unknown으로 둘 필요가 없다

`sample_nict_jle_label_candidates.py`는 원본 JSONL을 순회하며 1-based `source_line`을 저장한다. 실험 학습셋의 NICT 600행 각각을 `nict_jle_learner_utterances.jsonl`의 `source_line - 1` 위치와 대조한 결과 **600/600 발화가 정확히 일치**했다. 해당 원본 행에는 `source_group`, `source_record_id`, `source_file`이 있으며 학습 그룹 470개를 복구할 수 있다. 후보의 line과 학습의 line을 직접 비교하는 대신, **학습행 → 원본행 → 그룹**으로 연결해야 한다. 후보 NICT 행에는 이미 그룹이 있다.

아래는 gold-600에서 dev-200의 발화를 뺀 400행을 대상으로 양쪽 모두 `source:source_group` 형태로 비교한 결과다.

| 소스 | 남은 행 | 기존 학습 그룹 중복 | 학습 그룹 미중복 행 / 그룹 | 학습 및 dev 그룹 모두 미중복 행 / 그룹 |
|---|---:|---:|---:|---:|
| AMI | 133 | 128 | 5 / 2 | 1 / 1 |
| NICT | 132 | 51 | 81 / 70 | 70 / 59 |
| Taskmaster | 135 | 19 | 116 / 106 | 105 / 96 |
| 합계 | 400 | 198 | 202 / 178 | 176 / 156 |

**수정 요구:** A1의 `group_key`를 raw `source_group` 문자열 집합과 비교한다고 문자 그대로 구현하면 접두사 차이 때문에 중복을 놓친다. 양쪽에 동일한 canonical key를 사용하고, 누락 provenance에는 발화 fallback을 clean 증거로 쓰지 않는다. NICT line join에는 파일 hash, 범위 검사, utterance 일치 검사를 붙여 실패 시 unknown으로 남긴다. 현재 600/600 성공은 현재 원본 snapshot에 대한 결과이며 원본 재추출 후에도 자동 성립한다고 가정하면 안 된다.

202행도 전부 새 최종 test는 아니다. **26행은 dev-200과 그룹이 겹친다.** 이미 반복 분석한 dev와 독립적인 acceptance/재현 검증이 목적이면 176행/156그룹을 출발점으로 삼는다. 실제 미노출 이력까지 증명한 것은 아니므로 manifest에 `train_overlap`, `dev_overlap`, `provenance_verified`, `exposure_status`를 구분한다. 제외된 198행도 이유와 함께 감사용 manifest에 남긴다.

예약은 행 목록뿐 아니라 **그룹 전체**에 적용해야 한다. 학습/마이닝/검수의 모든 입구와 인접 발화도 검사한다. 이 156그룹을 최종 gate와 gate #4 재현용으로 어떻게 나눌지 지금 예약해야 한다. AMI는 엄격한 후보가 단 1그룹이므로 현재 풀만으로 두 시험 모두에서 AMI 일반화를 입증할 수 없다. 새 AMI 그룹 확보 또는 평가 범위의 명시적 제한이 필요하다.

## 2. [높음] B1/B2: event-hint 20개는 여유 있는 quota가 아니며 소스와 완전히 교락된다

직접 집계한 `annotation_events` 내 대소문자 무시 `laugh` 포함 결과:

| 모집단 | 행 수 | laughter 후보 | 후보 그룹 수 | 소스 |
|---|---:|---:|---:|---|
| train reservoir 전체 | 1,200 | 23 | 22 | 전부 AMI |
| train-120 발화 제외 | 1,080 | 20 | 19 | 전부 AMI |
| train-120 그룹 전체 제외 | 887 | 14 | 13 | 전부 AMI |

따라서 B1에서 남은 laughter 후보를 하나라도 소비하면 B2의 20개가 모자랄 수 있다. B1의 Humor 후보 6개를 어떤 규칙으로 뽑을지도 없다. B2에 그룹당 1개 제한을 적용하면 현재 발화 제외만으로도 20그룹을 채울 수 없다. **부족분을 중복 행이나 gold 후보로 메우면 안 된다.** event arm부터 내부적으로 예약하고 calibration과 공동으로 quota를 계산하거나, 부족 시 실제 개수로 줄이는 정책을 사전에 정한다. train-120과의 그룹 재사용은 dev/train 내부에서는 반드시 금지할 필요는 없지만 독립 pilot처럼 해석하지 말고 기록한다.

event arm의 yield가 높아도 event 선택 효과인지 AMI 소스 효과인지 분리되지 않는다. AMI 내 비-event 대조와 소스별 결과를 함께 보고한다. random control의 모집단은 이미 Energy/Curiosity 층화·품질 필터를 거친 reservoir이며 자연 배포 분포가 아니다. 앞선 두 arm을 뽑고 남은 행에서 random을 고르면 “잔여 모집단 대조”임을 명시한다.

B1/B2/B3 간 중복 처리, source/group quota, seed, 동점 처리, 후보 부족 처리까지 명세가 필요하다. B2의 disagreement는 Energy/Humor를 어떤 방식으로 합치는지(max, 축별 quota 등)도 고정해야 한다. B3는 공통의 “train-120 제외” 규칙의 명시적 예외로 적는다. 선택 이유 5종은 실제로 40/40/15/15/10개다. 파일의 첫 40개를 그대로 쓰지 말고, 40개에 대한 이유×소스 배분을 별도로 고정한다.

train과 gold reservoir의 canonical group 교집합은 실제로 0이다. 세 소스가 양쪽에 모두 있으므로 calibration을 위해 gold reservoir를 열 필요는 없다. **train-only calibration 자체는 타당하다.**

## 3. [높음] B/C1: 행 복제는 원점수 보존에 유용하지만 importer와 독립 채점 절차가 빠졌다

`export_axis_review_csv.py::review_fields()`와 `build_human_reviewed_axis_dataset.py::REVIEW_AXES`는 `all`, `energy-curiosity`만 지원한다. B2의 Energy/Humor, B3의 Energy/Curiosity/Intimacy는 지원하지 않는다. importer의 `load_review_csv()`는 같은 `review_id`가 두 번 나오면 오류를 내고, `review_set`도 gold/train만 허용한다. 후보의 `review_partition=train`을 `calibration` 또는 `pilot`과 직접 비교하면 partition 검사도 실패한다. exporter에 slot과 set만 추가하는 C1 범위로는 끝까지 사용할 수 없다.

**최소 계약:**

- `dataset_partition=train/dev/test`와 `annotation_batch=calibration/pilot/first40`를 분리한다. sampling metadata는 검수자에게 숨긴 manifest에 보존한다.
- batch 내 안정적인 `item_id`와 원본 candidate ID를 매핑한다. 40행 subset을 재번호화하여 기존 train-120의 ID에 잘못 연결하지 않는다.
- 원점수 식별키는 `(batch_id, item_id, reviewer_slot)`이며 실제 `reviewer_id`도 필수다. A/B가 서로 다른 사람인지 확인하고, 누락·중복·범위·축 schema·발화/context 무결성을 검사한다.
- A/B에게는 별도 blind view/export를 제공한다. 같은 CSV의 인접 복제 행에서 상대 점수가 보이면 독립 채점이 아니다. 선택 순서도 무작위화하고 seed를 보존한다.
- 원점수는 덮어쓰지 않는다. aggregation/adjudication은 별도 산출물로 만들고 검수자 수, rubric version, 수정 이력을 남긴다. 평균만으로 불일치를 없애지 않는다.

C1에는 exporter뿐 아니라 importer/aggregation의 round-trip 검증까지 포함해야 한다. 검수자가 보는 input 계약도 먼저 정해야 한다. 현재 gold CSV 200행 모두 previous/next 중 하나 이상의 context가 있지만 평가 모델은 utterance만 본다. 기본 제안은 이번 calibration/pilot도 현재 발화만 보여 주는 것이다. 이전 맥락을 포함하려면 모델 입력과 일치시키고, 미래 next turn이나 event/audio를 보여 준 평가는 별도 과제로 표시한다. 숨긴 selection_reason만으로 이 정보 차이는 해결되지 않는다.

## 4. [높음] 이전 DECISION의 정밀도 결정과 calibration 이후 채점 순서가 빠졌다

이전 EVIDENCE NEEDED #5의 점수 정밀도 정책이 현재 C 범위에서 누락됐다. 원 gold CSV의 **175개 비정수 점수 셀**을 다시 확인했다. importer의 `int(float(value))`, ML loader의 `_validate_axes()`의 `int()`, 후보 선정기의 `load_model_examples()`의 `int()`가 각각 정밀도를 잃게 한다.

사람 원점수/평균과 학습·평가 target은 소수점을 보존하고, 모델의 최종 정수 출력은 별도 정책으로 다루는 편이 타당하다. 기존 지표를 바꿔 부르지 말고 동일 dev에서 정밀도 전후 민감도를 구분한다. partial validator도 cast 전에 유한 수와 범위를 검사해야 한다. 이 결정과 importer 변경 없이 평균화 스크립트만 추가해서는 이전 결정을 이행하지 못한다.

D3의 세 CSV 동시 전달과 D5의 마지막 rubric 고정은 이전의 **“calibration 끝난 뒤 first40 검수”**와 충돌할 수 있다. 후보와 빈 CSV를 미리 준비하는 것은 괜찮지만, 실제 B2/B3 채점은 calibration 불일치 검토와 rubric/input version 고정 뒤 시작해야 한다. calibration 도중 rubric이 바뀌면 pilot 결과를 버전별로 구분한다.

48×5×2 + 60×2×2 + 40×3×2 = **960개 축 점수, 296 발화-검수 건**이다. 이는 148개의 서로 다른 발화를 쓴다는 조건부 계산이고 조정/재채점 비용은 별도다. 실제 두 검수자 확보는 repo만으로 확인할 수 없다. 1인+부분 중복으로 축소한다면 기존 2인 교차 채점 계획과 같은 증거라고 부를 수 없으며 중복 범위와 한계를 다시 명세해야 한다.

## 5. [높음] C2: 공유 feature는 타당하지만 단순 이웃 필터/None으로 끝나지 않는다

축별 별도 TF-IDF 모델은 필수가 아니다. **공유 feature + 축별 유효 label의 top-k**를 우선 구현하는 데 동의한다. 다만 현재 `predict()`는 전체 similarity를 정렬한 뒤 먼저 top-k를 자른다. 그 뒤 label 없는 이웃을 제거하면 더 먼 위치에 유효 label이 있어도 버린다. 반드시 전체 순위에서 해당 축의 유효 label을 필터한 뒤 k개를 선택하고 축별 분모를 계산해야 한다.

human/draft 중복을 predict 시점에만 제거해도 `fit()`에서 두 문서가 document frequency/IDF에 이미 반영된다. 같은 발화 correction은 feature 문서 단계에서 한 번만 세고, 축별 label/provenance는 별도로 연결한다. 동일 문자열이라도 서로 다른 context/출처의 발화일 수 있으므로 correction 대상은 provenance ID로 먼저 식별하고, 정규화 텍스트 중복은 충돌 기록과 명시적 정책을 사용한다. 사람 A/B의 같은 우선순위 label은 먼저 집계/조정해야 하며 임의 행 순서로 하나를 고르면 안 된다.

누락된 사람 축은 그대로 누락이다. 기존에 실제로 존재하는 draft label을 별도 provenance로 사용하는 혼합 실험과, human row의 빈 축을 draft로 채우는 행위를 구분한다. accepted-draft를 독립 blind human correction과 같은 신뢰도로 자동 취급하지 않는다.

`None` 반환은 현재 배포 계약과 충돌한다. `AxisResult`는 5개 정수 필수이며 `MLAxisAnalyzer.analyze()`는 validation 실패 시 **5축 전체를 rule로 fallback**한다. 평가기의 hybrid 산술도 `None`을 더할 수 없다. 연구용 partial prediction API로 분리하거나, 배포 fit 시 모든 축의 coverage를 요구하는 adapter 정책이 필요하다. fallback이 섞인 점수를 순수 ML 성능으로 보고하지 않는다. “유효 label 없음”과 “similarity가 전부 0”도 구별한다. 현재 후자는 0.001 가중치로 임의 동점 이웃을 평균하므로 재현 가능한 tie/zero-similarity 정책이 필요하다.

필수 검증은 top-k 밖 유효 label 회수, 중복 correction 추가 전후 IDF 불변, 미검수 축 누락, 원점수 정밀도, 축별 coverage와 adapter 동작이다. 공유 IDF는 모든 학습 발화를 활용하지만 source/draft 분포 영향이 남고, 축별 IDF는 label subset마다 거리 공간까지 달라진다. 후자는 별도 ablation이며 구현 선행조건은 아니다.

## 6. [높음] C3: 현재 classifier 하나로 역사적 teacher를 복원했다는 결론은 낼 수 없다

“bucket sensitivity analysis”라는 명칭과 classifier 사전 고정은 적절하다. 그러나 실제로 **NICT 전용 `scripts/sample_nict_jle_label_candidates.py::classify_bucket(text)`가 별도로 존재**한다. 이 함수는 NICT candidate-600의 저장 bucket과 600/600 일치한다. Claude가 제안한 generic `sample_real_speech_label_candidates.py::classify_bucket(row)`는 NICT 저장 bucket과 **132/600 불일치**한다.

현재 `draft_axes(row)`를 저장된 bucket 그대로 적용하여 저장 draft axes와 비교한 결과도 다르다.

| draft 파일 | generic classifier vs 저장 bucket 불일치 | 현재 draft_axes vs 저장 axes 불일치 행 |
|---|---:|---:|
| NICT 600 | 132 | 221 |
| AMI 600 | 0 | 0 |
| CHiME-6 600 | 2 | 0 |
| HCRC 500 | 1 | 0 |
| Taskmaster 500 | 1 | 0 |

NICT 221행은 Formality/Energy가 달랐고, NICT human-600의 axes는 저장 draft-600과 600/600 같았다. 따라서 현재 함수가 역사적 학습 라벨을 전부 재현한다는 CONTEXT/진단 스크립트의 설명은 성립하지 않는다. 이 차이의 역사적 원인(버전 변경 등)은 이번에 확정하지 않았다.

C3 1단계에 sampler와 teacher의 **두 가지 재현 오차**를 포함한다. generic classifier만 적용한 결과는 하나의 가정 하에서의 민감도다. NICT 전용 규칙을 포함한 소스별 가정도 결과를 보기 전에 고정할 수 있지만, 좋은 성능을 보고 선택하면 안 된다. C3 마지막의 **“Curiosity 0.83 과장/축소 방향 확정”은 “명시한 가정과 현재 dev에서 변화 방향 측정”으로 낮춘다.** 원래 gold bucket도 없고 역사적 teacher와의 불일치도 있어 실제 원인이나 일반화 방향은 확정할 수 없다. 현재 diagnose 스크립트는 입력 경로가 고정돼 있으므로 두 variant를 메모리에서 명시적으로 비교하는 함수/CLI 범위도 필요하다.

## 7. [높음] C4/A2: NA 제외 평균을 곧바로 gate에 쓰면 비교 대상이 달라진다

상수 입력의 rho를 NA로 표시하는 것은 맞다. 하지만 모델별로 NA 축을 제외한 평균은 서로 다른 축 집합의 평균일 수 있다. 예를 들어 ML이 어려운 Humor를 상수로 출력하면 4축 평균이 올라가고 hybrid는 5축 평균으로 불리하게 비교될 수 있다. 이는 gate #2/#3의 의미를 조용히 바꾸는 결과다.

진단 리포트에서는 유효 축, 공통 유효 축의 보조 평균, 표본/그룹 수를 표시하되, **필수 축의 rho가 미정의면 기존 5축 gate를 통과했다고 판정하지 않는다.** human target이 상수인 경우는 시험 정보 부족, model prediction만 상수인 경우는 모델 퇴화로 이유를 구분한다. MAE는 rho NA라는 이유로 제외하지 않는다. bootstrap 재표본에서 상수가 되는 경우도 NA 빈도와 CI 가능 여부를 보고한다.

`ai/evaluate_axis_analyzers.py`뿐 아니라 `scripts/diagnose_gold_vs_ai_draft.py`에도 별도의 `_pearson()`이 0.0을 반환한다. C3에서 그 함수를 재사용하면 같은 오독이 남는다. report 출력 외에도 평균, best-model 선택, gate 및 diagnostic 경로를 함께 점검해야 한다.

A2에 comparator/paired group bootstrap/gate #4를 문장으로 넣는 것은 좋은 출발이지만 실행 명세는 아직 부족하다. 학습 파일 hash, rule 버전, k/ngram, 고정 기존 hybrid와 후보 연결 hybrid, 승인된 gate의 비교 상대를 지정한다. bootstrap은 모든 모델에 같은 그룹 재표본을 쓰며 source별·축별 차이와 유효 반복 수를 보고한다. CI 수준/반복 수/seed와 불확실할 때 보류하는 정책도 결과 전에 고정한다. 최종 평가 분포, 최종·재현 그룹 수, 새 5축 사람 라벨 예산을 별도 산정한다. 실험용 HCRC 포함 3,137행과 실제 전환 대상 학습 구성이 같다고 가정하지 않는다.

## Round 3에서 확정할 실행 순서

1. 원본 hash와 text 일치 검사로 NICT provenance를 복구하고, train/dev 노출을 구분한 그룹 manifest 및 최종/재현 그룹 예약을 먼저 확정한다. 176행을 충분한 test라고 약속하지 않는다.
2. 점수 정밀도, 검수 input, ID/slot/partition, 집계·NA·평가 계약을 고정한다. B1/B2 후보 quota는 동시에 계산해 희소 event 후보 충돌을 막는다.
3. exporter/importer 및 partial-label 지원, bucket/teacher 재현성, NA 처리를 구현·검증한다. 후보 준비는 병행 가능하나 실제 B2/B3 채점은 calibration 뒤에 시작한다.
4. label yield/agreement를 소스·선택 경로별로 검토한 후 확장 여부를 결정한다. 나머지 train-80은 빈 CSV 준비는 가능하지만 채점/사용은 보류한다. Intimacy 전면 교체는 계속 보류한다.
5. 이전 ACTION #5의 대문자 비율·반복 길이 feature ablation과 human-only/draft-only/혼합 학습곡선을 후속 항목으로 명시한다. 구현/선정/평가가 동시에 바뀌지 않도록 baseline을 고정한다. 별도 최종·재현 시험과 사용자 승인 전 기본 analyzer 전환 근거는 없다.

## 집계 재현 기준

JSONL은 UTF-8-sig로 읽고, NICT 복구는 `raw_rows[source_line - 1]`와 학습 utterance의 정확 일치를 먼저 검증했다. group 비교는 양쪽 모두 `source + ':' + source_group`으로 수행했다. remaining은 gold-600에서 dev-200의 정확한 utterance 집합을 제외했다. strict 후보는 복구된 전체 학습 그룹과 dev 그룹을 모두 제외했다. event count는 `annotation_events`를 직렬화한 문자열의 case-insensitive `laugh` 포함 기준이며, 실제 태그는 laugh였다. 모델 점수나 사람이 채점하지 않은 label은 선정·복구에 사용하지 않았다.

핵심 입력 SHA-256:

- `axis_dataset_combined_real_speech_experimental.jsonl`: `23051000c3c2c4e0c38a876de61973d156188ef151faad69fca18caf20ddc1e9`
- `nict_jle_learner_utterances.jsonl`: `feb9ba1e4f955db77517a07c3007a9860bfb2b8f0f49d286ab7fdef262c24313`
- `ml_transition_gold_candidates_600.jsonl`: `7d5b7c4538b23d7e6e5bf14de78d2e77c57ca2abd61ecb114ab32d0fbd2022a4`
- `ml_transition_gold_stratified_candidates_200.jsonl`: `f295a4792d44864f5812eaef15d0b78f9d9d82d9a41f9466818cbd5338ce8cb4`
- `ml_transition_train_candidates_1200.jsonl`: `057a98c315f230a601e997f55cbcae1a0c175743b16467fcca540b0c491dde70`
