# Codex Round 2 — ML 전환 로드맵 방법론 검토

2026-09-07. 판정: **방향은 타당하지만 현재 9단계 순서로 라벨링 예산을 확정하면 안 된다.** 평가 대상·provenance·라벨 정밀도·검수 입력 조건을 먼저 고정하고, 작은 라벨링 pilot과 ablation 결과로 확장 여부를 결정해야 한다. 현재 증거는 ML 기본값 전환을 지지하지 않는다.

검증 범위: `CONTEXT.md`, `CURRENT_TASK.md`, `CLAUDE_REVIEW.md`, 이전 사이클 `DECISION.md`, `docs/ml-transition-plan.md`, 관련 구현과 실제 JSONL/CSV를 읽었다. Python 표준 라이브러리로 메모리 내 행 수·분포·교집합을 집계했다(`python -B`, 파일 출력 없음). 모델 재학습·성능 재평가·신규 classifier 실험은 하지 않았으며 Round 3 대상으로 남긴다. 아래 성능 수치는 기존 보고값이고, 데이터 집계는 이번에 직접 확인한 값이다. 코드와 데이터는 수정하지 않았다.

## 1. [최우선] #8을 앞으로: 남은 400개는 곧바로 쓸 수 있는 blind test 400개가 아니다

실험 학습셋 3,137행의 비어 있지 않은 `source_group`과, gold-600에서 gold-200의 발화를 제외한 400행을 대조했다.

| 소스 | 남은 행 | 기존 학습 그룹과 일치 | 불일치 확인 / 미확인 |
|---|---:|---:|---:|
| AMI | 133 | 128 | 5행 불일치 확인 |
| Taskmaster | 135 | 19 | 116행 불일치 확인 |
| NICT | 132 | 판정 불가 | 132행 미확인 |

NICT 학습 600행 모두 `source_group`이 없다. 따라서 단순 set 차집합으로 얻는 253행을 clean이라고 부르면 안 된다. **현재 확인 가능한 것은 121행, 108그룹(AMI 2 / Taskmaster 106)**뿐이다. 이 중 이미 분석한 gold-200의 그룹까지 제외하면 AMI 1행 + Taskmaster 105행만 남는다. 후자는 향후 모델 선택 과정까지 분리하려는 더 엄격한 조건이다.

gold-200도 72행 overlap(AMI 65 + Taskmaster 7), 60행 known nonoverlap(AMI 2 + Taskmaster 58), 68행 NICT unknown이다. Claude의 #8은 unknown 68행을 빠뜨렸다. 또한 `docs/ml-transition-plan.md`의 candidate train/gold 간 그룹 분리는 **기존 3,137행과의 분리**를 보장하지 않는다.

권고: #8의 그룹 예약을 모델·라벨 확장 전에 실시한다. NICT provenance를 원본 `source_line`과 추출 자료로 복구할 수 있는지 확인하거나, 검증 불가 행을 최종 시험에서 제외한다. AMI 등 부족한 소스는 새 그룹을 확보하거나 학습에서 해당 그룹 전체를 제외한 새 baseline을 정의해야 한다. 예약 목록은 향후 train-120, 마이닝, 인접 발화까지 적용한다. gold-200은 반복 진단에 사용했으므로 dev로 취급한다. 남은 후보도 dev와 같은 그룹인지 별도 기록한다.

## 2. [최우선] 빠진 선행 단계: 라벨 정밀도와 평가 입력 계약

`ml_transition_gold_blind_review_200.csv`에는 소수점 점수 175셀이 있고 평가 JSONL에는 비정수 값이 0개다. `scripts/build_human_reviewed_axis_dataset.py:29`는 `int(float(value))`, `ai/ml_baseline.py::_validate_axes()`도 `int()`를 적용한다. 따라서 “0.5 단위 평균 gold로 평가”라는 설명과 실제 평가가 다르다. 변환기만 고쳐도 loader에서 다시 잘린다.

gold CSV 200행 모두 previous/next context가 적어도 하나 존재하지만, regressor와 rule 평가 입력은 `example.utterance`뿐이다. **검수자가 실제로 맥락을 사용했는지는 CSV만으로 확인할 수 없다.** 다만 next turn을 볼 수 있는 검수와 현재 발화만 보는 실시간 추론의 정보 차이는 명시적으로 통제해야 한다. 특히 Intimacy/Humor 오류를 전부 라벨 부족으로 돌리기 전에 판별할 문제다.

권고: 사람 평균 점수 보존 정책과 모델 출력 정수 정책을 분리한다. Round 3에서 원 CSV 정밀도를 보존한 지표 민감도를 확인하고, 이후 구현 단계에서 변환·loader 모두 같은 계약을 적용한다. 검수 입력은 현재 발화만인지, 추론 시 이용 가능한 이전 맥락까지인지 먼저 고정한다. 미래 발화나 audio를 보여줄 경우 현재 text-only 모델과의 평가 목적 차이를 기록한다. 라벨링 확대 전에 이 조건을 calibration에 적용해야 한다.

## 3. [높음] “leakage가 원인이 아님을 확인”은 인과적으로 과도하다

기존 nonoverlap 60행의 ML 0.16 < rule 0.32는 **그 부분집합에서도 ML 우위가 관찰되지 않았다**는 증거다. 전체 집합의 leakage 영향을 제거하거나 원인을 판별한 실험은 아니다. 이 60행은 AMI 2 / Taskmaster 58로 소스가 편중돼 있고, overlap 집합과 난이도·reviewer 구성이 다르다. NICT는 여전히 unknown이다. 상관계수 0.16을 0.32의 “절반 성능”으로 해석하는 것도 부적절하다.

같은 평가 발화를 고정하고 겹치는 학습 그룹을 제거한 전후 비교가 leakage 민감도를 더 직접적으로 보여준다. 제거 전후 학습량·소스 구성 변화도 함께 보고해야 한다. 지금 가능한 결론은 “전환 근거 부족이라는 판단은 유지되지만, leakage 영향의 크기와 원인은 미확정”이다.

## 4. [높음] #1 calibration은 필요하나 두 reviewer ID만으로 프로토콜을 복원할 수 없다

실제 구성은 reviewer-avg=AMI 67 + NICT 33, reviewer-01=Taskmaster 65 + NICT 35이다. **소스가 완전히 분리된 것은 아니다.** NICT는 양쪽에 존재하지만 동일 발화의 교차 채점이 아니므로 reviewer 효과를 분리하지 못한다. reviewer-01의 Humor 비영점은 0/100, reviewer-avg는 24/100으로 확인했다. 이것만으로 어느 쪽이 잘못 채점했는지 정할 수 없다. reviewer-avg가 정답이고 reviewer-01의 100행만 재검수해야 한다는 결론도 이르다.

권고 pilot: dev/train 용도로만 쓰는 48발화(AMI/NICT/Taskmaster 각 16), 모든 발화를 동일한 **실제 사람 2명**이 독립적으로 5축 채점한다. 96 발화-검수 건, 480 축 점수다. 드문 Humor 후보와 일반 대조군을 함께 넣되 자연 분포 성능 추정에는 쓰지 않는다. 개인 점수·검수 입력·평균화 규칙을 보존하고 큰 불일치는 제3자가 조정한다. 평균화 프로토콜 자체를 재현하려면 기존 참여 인원과 원점수가 추가로 필요하다.

축별 signed difference, absolute difference, 점수 분포와 소스별 차이를 보고한다. 상관만 높아도 scale bias는 남을 수 있다. 48개는 실행 가능한 pilot 제안이지 충분한 통계 검정력을 증명한 표본 수가 아니다. 이 결과로 rubric을 고정한 뒤 필요한 범위만 재검수한다.

## 5. [높음] #2/#4/#6의 투입 근거와 규모를 pilot으로 바꿔야 한다

### #2 train-120

“이미 뽑았으니 먼저”는 성능 개선 근거가 아니다. 직접 확인한 선택 이유는 Energy disagreement 40, Curiosity disagreement 40, 각 extreme 15, random control 10이다. 소스는 NICT 54 / AMI 30 / Taskmaster 36이다. 이 표본은 모델 간 불일치 표본이지 실제 고에너지 정답 표본이라는 보장이 없고, 자연 분포 성능 평가용도 아니다.

calibration 후 40행을 선택 이유·소스를 섞어 먼저 검수하고, 도움이 되는 오류 유형과 라벨 분포가 확보되는지 보고 나머지를 진행한다. 전체 120행 2축은 240개 1차 축 점수, 그중 30행 중복 검수는 60개 추가 축 점수다. 비용 단위는 사람 수와 축 수를 함께 기록한다. 금전/시간은 pilot에서 실제 분당 채점량을 측정하기 전 확정할 수 없다.

### #4 Energy/Humor 마이닝

보고된 라벨 집계는 재현됐다: Energy>=50은 전체 126행 중 real-speech 15행, Humor>=40은 37행 중 real-speech 5행이다. 그러나 이는 **draft 점수의 빈도**이며 사람이 판단한 positive 빈도가 아니다. “positive 예시 자체가 없다”는 문구는 수치와도 모순된다. 낮은 draft 점수를 받은 발화에도 사람이 인정할 positive가 있을 수 있다.

우선 train 그룹 내 60발화 pilot을 제안한다: event 힌트 20, 텍스트/모델 불일치 후보 20, 무작위 대조 20. 두 사람이 Energy/Humor를 독립 채점하면 120 발화-검수 건, 240 축 점수다. laughter는 재미의 정답이 아니며, 긴장/맞장구일 수 있다. 선택 경로별 실제 yield, 불일치, 소스 편향을 확인한 뒤 확대한다. annotation event가 없어도 잡히는 positive를 보려면 대조군이 필수다. 배포 평가에는 enrichment 비율을 그대로 가져가지 않는다.

### #6 Intimacy

현재 `draft_axes()` 대명사 정규식은 `\b(i|i'm|my|me|we|our)\b`이며 gold 200행 중 102행에 매칭된다. real-speech 학습 Intimacy는 17개 고유값, 범위 22~59다. **현재 코드에서 대명사 조건이 상수를 만든다는 주장은 성립하지 않는다.** rubric의 타당성과 좁은 분포 문제는 여전히 의심할 수 있지만, 전체 라벨 교체 필요량을 이 원인으로 단정할 수 없다.

먼저 calibration 48행의 Intimacy 결과를 활용하고, 필요하면 train-120의 첫 40행에 Intimacy를 추가한다(1차 40개 + 중복 검수분의 축 점수). human-only, draft-only, human+draft 가중 혼합을 비교하는 학습곡선으로 확대 여부를 정한다. 기존 2,799 real-speech 행 전체를 교체하는 약속은 아직 근거가 없다. gold/dev를 학습에 재사용하지 않는다.

## 6. [중간] #3/#5/#7의 기술적 근거를 정정하고 작은 ablation을 먼저

- **#3 partial labels:** 필요성은 맞다. 현재 loader는 5축 키를 모두 요구한다. 그러나 축별 별도 TF-IDF 모델만이 해법은 아니다. 공유 feature 공간에서 축별 유효 label 이웃을 찾는 방법도 가능하다. 같은 발화의 human correction을 기존 draft 행에 덧붙여 두 이웃으로 중복 집계하지 않도록 축별 provenance·대체 규칙을 설계해야 한다. 누락 축은 누락으로 유지한다. 구현은 사람 라벨 없이 준비 가능하지만 유용성 검증에는 실제 검수 label이 필요하다.
- **#5 feature:** `TOKEN_PATTERN = re.compile(r"[a-z']+|[!?]+")`이므로 `That's great.`와 `THAT'S GREAT!!`는 `!!` 토큰 유무로 이미 구분된다. 대소문자는 lowercasing으로 사라지는 것이 맞다. 반복 문자도 토큰 형태에는 남지만 일반화된 반복 길이 feature는 없다. 따라서 현재 token 기준선 대비 새 feature의 증분 효과를 검증해야 한다. 코퍼스/STT가 대문자·구두점을 얼마나 보존하는지 먼저 확인하고, 소스 표기 관습을 Energy로 학습하는지 점검한다.
- **#7 bucket:** 우선순위를 라벨 확대 앞으로 옮기는 데 동의한다. 그러나 새 classifier로 추정한 bucket은 원래 bucket의 복원이 아니다. 기존 추출·샘플링 규칙과 provenance를 먼저 확인하고, 재구성이 불가능하면 여러 합리적 bucket 가정에 대한 sensitivity로만 보고한다. 결과가 좋게 나오는 classifier를 gold-200에서 선택하면 추가적인 dev tuning이다. Curiosity rho 0.83이 과장됐는지, 반대로 낮아졌는지는 아직 미확정이다.

빠진 저비용 비교는 human-only / draft-only / 혼합 비중, 기존 unigram/bigram, k, 소스별 성능이다. 수십 개 human label을 수천 개 draft에 단순 추가하면 label 품질 개선이 예측에 반영되지 않을 수 있다. 하나씩 고정된 dev에서 비교하고 실험 수와 선택 기준을 기록한다. 이번 Round 2에서 구현·실행한 실험은 아니다.

## 7. [높음] #9는 “재평가만, 사람 불필요”가 아니다

미검수 최종 test와 다른 held-out 그룹의 재현 검증에는 **새로운 5축 사람 label 예산**이 필요하다. 예를 들어 test 200발화를 두 사람이 채점하면 400 발화-검수 건 / 2,000 축 점수다. 이것은 비용 예시이지 200개면 gate의 작은 차이를 안정적으로 판정할 수 있다는 보장이 아니다. 현재 clean reservoir는 소스가 편중돼 그 숫자조차 그대로 확보할 수 없다.

평가 계획에 다음이 빠져 있다.

1. 고정 comparator: 현재 rule, 기존 hybrid, 후보 ML에 연결된 hybrid를 구별한다. ML을 바꾸면 hybrid도 바뀌므로 기존 기준선을 함께 유지한다. rule이 현재 런타임 기본이므로 rule 대비 퇴행도 보고한다. 승인된 gate를 몰래 바꾸지는 않는다.
2. 소스별·축별 MAE/rho, paired **source-group 단위** bootstrap 불확실성, 독립 그룹 수를 보고한다. 0.20 MAE / 0.03 rho 차이는 점추정만으로 강한 결론을 내리기 어렵다. CI 기반 판정 정책은 결과를 보기 전에 정한다.
3. `ai/evaluate_axis_analyzers.py::_pearson()`는 상수 입력에서 0을 반환한다. Humor가 전부 0인 subgroup의 rho는 실제로 정의되지 않는다. 유효 축 수와 NA를 표시하고 고정된 평균 집계 정책을 정해야 한다.
4. gate #4는 동일 test 재실행으로 충족되지 않는다. 별도 예약 그룹에서 모델과 분석 계획을 고정해 확인한다. 최종 test를 보고 튜닝했다면 그 test는 이후 dev다.
5. gold의 source/Energy×Curiosity 층화 결과는 자연 사용 분포 성능과 다르다. 목표 분포 평가와 rare-case 진단을 분리한다. HCRC 제외 등 실제 전환 대상 학습셋 구성도 고정해야 실험용 3,137행 성능을 잘못 이식하지 않는다.

## 권장 순서와 Round 3의 최소 결정

1. 평가 계약과 manifest: gold-200은 dev, 점수 정밀도, reviewer 입력 맥락, NICT unknown 처리, 최종/재현 그룹 예약을 먼저 결정한다. 예약은 지금, 최종 채점은 rubric 고정 후 한다.
2. 48행 reviewer calibration과 기존 bucket/feature 검토를 진행한다. partial-label 설계는 병행 가능하다.
3. train-120 일부와 Energy/Humor pilot을 검수하고 Intimacy는 같은 발화에 추가해 중복 비용을 줄인다. 실제 label yield와 agreement로 전체 검수 여부를 결정한다.
4. 축별 label provenance를 지키는 학습 후, 작은 사전 정의 ablation과 학습곡선으로 확장 여부를 결정한다.
5. 모델·comparator·평가 코드를 고정하고 독립적인 5축 test 및 재현 평가를 실시한다. gate 충족과 사용자 명시 승인 후에만 전환한다.

Round 3에서는 먼저 이번 집계(특히 121 known-clean / 132 unknown)를 확인하고, CSV 정밀도에 따른 지표 민감도와 동일 평가행의 학습 그룹 제거 민감도를 가능한 읽기 전용 방식으로 확인하면 된다. 새 코드가 필요한 실험은 후속 구현 과제로 명시한다. 이번에 제시한 48/40/60행은 예산 상한을 정하기 위한 pilot 규모이며, “이 정도면 gate를 통과한다”는 예측이 아니다.
