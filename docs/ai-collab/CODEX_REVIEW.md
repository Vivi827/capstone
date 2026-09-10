# CODEX_REVIEW — cycle 4b / Round 2

2026-09-10. 판정: **Day 1 수치는 재현되지만, “NICT 과적합이 주 병목이며 teacher보다 coverage/representation 문제”라는 해석은 지지되지 않는다.** 출처별 성능 차이는 사실이다. 그러나 학습 출처에 관한 전제가 틀렸고, 라벨 편향과 표현력 손실이 동시에 관측된다. E1 분할을 수정하고, E2를 축소한 뒤, 작은 표현 실험과 대체 teacher→student 비교로 진행하는 것이 우선이다. 대규모 사람 학습 라벨은 여전히 정당화되지 않았다.

## 검토 범위와 재현

- 현재 `CONTEXT.md`, `CLAUDE_REVIEW.md`, `CURRENT_TASK.md`, 평가 계약 및 관련 코드/데이터를 읽었다. 현재 `DECISION.md`는 “아직 작성 안 됨”이므로 cycle 4 결정은 `git show c9f4791:docs/ai-collab/DECISION.md`로 읽었다. 실행계획 archive는 이전 결정이므로 cycle 4 대용으로 취급하지 않았다. U1 보류/U2 calibration 보류는 현재 task의 지시를 적용했다.
- `python -B scripts/diagnose_dev200_group_purge.py`를 재실행했다. 추가 검증은 `python -B -`의 메모리 내 계산으로만 수행했다. 최종 예약 pool, reservation audit, gold-600 및 예약 항목을 포함할 수 있는 후보 파일은 열지 않았다. 최종 pool 규모는 공개된 계약/결정 문서의 수치이며 이번에 독립 재검증한 수치가 아니다.
- 학습 SHA-256: `23051000c3c2c4e0c38a876de61973d156188ef151faad69fca18caf20ddc1e9`; dev-200 SHA-256: `7dedff3225fb5161ef08ca9651acd93bbe01f6f87ac6343086905e98f8d0c7f7`. NICT 원본 join은 600/600 발화 일치. 이 학습 hash는 **원본 3,137행**의 hash이며, 2,940행 purged artifact 자체의 hash는 아니다.
- Day 1 bigram ML 14.897/0.280 → 14.966/0.284, hybrid 14.262/0.386 → 14.283/0.391 및 출처·검수자별 표가 모두 출력 정밀도에서 일치했다. dev는 200행/161그룹, 그중 학습과 겹치는 100행/69그룹, 제거된 학습은 197행이다.

## 1. 진단의 약한 주장과 누출

### P1 — “NICT가 학습을 지배한다”는 전제가 틀렸다

`axis_dataset_combined_real_speech_experimental.jsonl`을 직접 집계했다.

| 출처 | 원본 | dev 그룹 제거 후 |
|---|---:|---:|
| NICT | 600 | 567 |
| CHiME6 | 600 | 600 |
| AMI | 599 | 441 |
| HCRC | 500 | 500 |
| Taskmaster | 500 | 494 |
| AI-assisted/generated seed 합계 | 338 | 338 |
| 합계 | 3,137 | 2,940 |

2,199 draft 행은 CHiME6+AMI+HCRC+Taskmaster이다. NICT는 원본의 19.1%, purge 후 19.3%로, 가장 큰 단일 출처도 아니다. NICT 외 corpus도 learner-like하다는 별도 증거 없이 이를 NICT 데이터로 세면 안 된다. NICT 행의 `label_status=human_reviewed` 역시 독립 사람 gold를 의미하지 않는다는 기존 provenance 주의는 유지한다.

NICT 성능이 상대적으로 좋다는 것만으로 과적합은 입증되지 않는다. 해당 영역 train/held-out 격차, 이웃의 출처/유사도, 출처별 label 편향, 학습 소스 비율을 통제한 비교가 없다. 현재 결론은 **“이 모델의 dev 성능이 출처·축별로 다르다”**까지다.

### P1 — E1의 제안된 split은 실제로 NICT 그룹 누출을 재도입한다

Day 1은 NICT 원본에서 그룹을 복구해 제거하지만 `_as_examples()`는 원래 행의 `source_group`을 그대로 옮긴다. purge 후 NICT **567행 전부 이 필드가 비어 있다**. `ai/evaluate_axis_analyzers.py::split_by_source_group()`는 빈 그룹을 발화 텍스트 hash로 대체한다.

이대로 2,940행을 분할해 재현한 결과: train 2,700 / holdout 240, 실제 canonical group 교집합 **14개**, holdout 중 같은 학습 그룹을 가진 **14행 모두 NICT**였다. 새 seed만으로는 해결되지 않는다.

E1/E4에서 먼저 원본 join으로 복구한 source-qualified canonical group을 **각 행/예제에 붙이고**, 분할 후 실제 그룹 교집합 0을 assert해야 한다. IDF도 E1 train 부분에서만 fit한다. source_group 없는 seed는 실제 provenance 한계를 명시하고 최소한 정규화 동일 텍스트를 묶는다. 이번 purged train에는 공백 정리+casefold 중복 0개, 같은 정규화 기준 train/dev 동일 텍스트도 0개였다. 이는 near-duplicate나 잘못된 세션 경계까지 배제한 결과는 아니다.

### P2 — “leak flattering”은 MAE에만 미세하게 해당하며, clean/overlap 비교는 인과 비교가 아니다

ML의 MAE는 purge 후 약 0.069 악화되지만 rho는 약 0.004 좋아진다. hybrid rho도 좋아진다. 누출이 rank까지 부풀렸다고 쓰면 방향이 틀린다. 작은 집계 변화는 **이 제거 개입의 점추정 효과가 작다**는 뜻이며 축별 상쇄나 불확실성은 아직 평가하지 않았다.

overlap-100은 AMI 65 / NICT 28 / Taskmaster 7, clean-100은 AMI 2 / NICT 40 / Taskmaster 58이다. 후자는 출처 구성이 완전히 다르므로 그 성능 차이를 leakage 효과로 해석할 수 없다. purge 이후에는 두 slice 모두 현재 학습과 그룹이 분리돼 있다. “genuinely held-out”은 clean 쪽에만 붙이지 말고, “원래부터 겹치지 않았던 dev slice”라고 쓴다. 두 slice 모두 반복 분석된 dev이며 acceptance test가 아니다. CI 없이 “clearly behind”는 점추정 순위 이상의 의미를 갖지 않는다.

### P2 — 실제 confound와 축별 결과는 단일 coverage 가설에 반한다

| dev 출처 | 행/그룹 | 공백 분리 단어 중앙값 | 5단어 이하 | Humor > 0 | Intimacy SD |
|---|---:|---:|---:|---:|---:|
| AMI | 67/39 | 8 | 17 | 22 | 4.58 |
| NICT | 68/61 | 9.5 | 12 | 2 | 21.42 |
| Taskmaster | 65/61 | 9 | 7 | 0 | 8.33 |

AMI가 더 짧고 독립 그룹도 적다는 가설은 일부 뒷받침된다. 그러나 길이 중앙값만으로 큰 성능 차이를 설명하지는 못한다. 길이/질문형/label 분산에 따른 잔차와 이웃 유사도를 함께 봐야 한다. 특히 NICT Humor는 68행 중 비영점 2행, SD 0.84이므로 정의된 rho라도 안정적인 유머 일반화 증거는 아니다.

Taskmaster Humor=0은 **저장된 사람 target의 사실**이다. 실제 영역에서 유머가 항상 없다는 증거는 아니다. reviewer-01의 NICT 35행까지 Humor가 모두 0이므로 출처와 scorer 기준을 분리해야 한다. NICT에는 두 reviewer 집단이 모두 있어 그 안의 비교가 보조 진단은 되지만, 같은 발화를 이중 채점한 실험이 아니므로 reviewer 인과효과를 추정하지 못한다.

축별로 보면 더 구체적인 문제다:

- AMI Intimacy MAE: ML **16.716**, rule **7.627**. Taskmaster는 ML **27.169**, rule **15.862**.
- Taskmaster Energy rho: ML **−0.182**, rule **0.401**. 반면 Curiosity는 ML **0.751**, rule **0.665**, MAE도 ML **21.923** 대 rule **31.354**로 ML이 낫다. “Taskmaster에 일반화하지 못한다”는 전면적 표현은 이 축의 성과를 숨긴다.
- Taskmaster 평균 rho는 Humor를 뺀 4축, AMI/NICT는 5축이다. 출처 간 평균 비교에는 공통 4축 보조값과 각 축 값을 함께 제시해야 한다.

teacher도 직접 비교했다. `bucket_sensitivity_gold200.py`의 variantB(NICT 전용 classifier, 나머지 generic)를 사용하면 Intimacy의 teacher−human 평균 bias가 **AMI +15.597, NICT +7.265, Taskmaster +27.815**이다. 현재 ML의 큰 Intimacy 오차와 양립하는 출처별 supervision 편향이다. 이것만으로 teacher를 원인으로 확정할 수는 없지만, teacher error를 후순위로 내릴 근거는 더욱 없다. 같은 variant의 Energy rho는 AMI 0.187, NICT 0.450, Taskmaster 0.154로, teacher와 student 양쪽 문제가 가능하다. 이 variant는 역사적 teacher의 확정 복원이 아니다.

## 2. E1–E5 수정안과 판별력

### E1 — 유지하되 “핵심 이분 판별기”에서 용량/전이 진단으로 낮출 것

수정된 canonical-group holdout에서 출처×축별 student-vs-stored와 current-teacher-vs-stored를 측정한다. NICT를 제외할 이유는 없다. 다만 NICT/다른 draft/seed를 섞은 한 평균으로 해석하지 않는다. 학습 부분에서 계산한 축별 상수 median baseline, target 분산, bias, NA 이유를 같이 보고해 좁은 label 범위에서 MAE≤5를 쉽게 얻는 경우를 구별한다.

실제 purge 데이터에서 current `draft_axes(row)`는 AMI 441, CHiME6 600, HCRC 500, Taskmaster 494행의 저장 5축을 **전부 정확히 재현**한다. 따라서 그 영역 teacher-vs-stored의 높은 충실도는 생성함수의 자기 재현이다. NICT는 567행 중 208행이 F/E에서만 달라지고 평균 절대차는 F 2.568 / E 1.101이다. seed 338행은 전부 적어도 한 축이 달라, 이들에 같은 teacher provenance를 붙이면 안 된다.

판별 가능한 것: 높은 student 충실도는 해당 held-out weak-label 분포를 현재 모델이 근사할 수 있다는 증거다. 낮은 충실도는 근사 실패의 증거다. **어느 쪽도 human 성능의 단일 원인을 확정하지 않는다.** 낮은 충실도에는 데이터 밀도·split 난이도·혼합 teacher·k·특징 손실이 모두 관여한다. teacher의 완벽한 자기 재현과 student를 비교해 표현력만 원인이라고 결론내리지 않는다.

특히 “rho≤0.30이면 supervision ceiling”은 근거 없는 사후 경계다. 이미 variantB teacher의 dev 평균 rho는 AMI 0.265 / NICT 0.414 / Taskmaster 0.406(마지막은 4축)으로 출처별 상황이 다르다. student가 teacher를 잘 모사해도 표본 증가에 따른 분산 감소나 오류 상쇄로 human 성능이 좋아질 수 있다. “동일 라벨을 더 자동화해도 도움 없음”은 E1만으로 나오지 않는다.

### E2 — 비NICT arm은 생략, NICT F/E의 작은 통제 실험으로 제한

저장 bucket으로 재계산하는 비NICT 실데이터 label swap은 위 검증상 **완전 no-op**이다. NICT에서는 208행 F/E의 오프셋 교체만 검사한다. seed까지 교체하면 별도 생성자의 labels를 current heuristic으로 바꾸는 다른 실험이므로 seed는 고정한다.

동일 텍스트·순서·membership·feature/IDF·k·나머지 축을 고정하면, dev 예측 변화가 **그 label 변경에서 유래했다**는 것은 분리할 수 있다. 그러나 새 label이 더 정확하다는 것은 별개의 주장이다. “correct bucket”도 current sampler인지 역사적 저장값인지 명시해야 한다. 양쪽 차이가 있으면 sampler와 rubric 변화가 섞인다. 짧은 NICT 진단은 가능하지만 이를 “better teacher”의 검증으로 부르거나 Flash-Lite 비교를 며칠 늦출 이유는 없다.

### E3 — 작은 k/ngram sweep 유지; 제안된 caps/repeated-punctuation ablation은 제외

`ai/ml_baseline.py::_tokenize()`가 이미 `text.lower()`를 호출하므로 대문자 제거는 현재 ML에 아무 변화를 주지 않는다. dev-200의 반복 `!?`는 **0행**이고 `!` 포함 발화도 1행뿐이다. 학습 쪽 반복 punctuation 정규화가 이웃을 바꿀 가능성은 있으나, 이 dev로 caps와 묶어 핵심 병목 실험을 할 가치는 낮다. 새로운 caps/길이 feature를 추가하는 실험은 별개이며 “현재 feature 제거”라고 부르면 안 된다.

`backend/main.py:383,1115`의 두 STT 설정 모두 `enableAutomaticPunctuation=False`이고 반환 transcript에는 `.strip()`만 한다. 이는 중요한 입력 불일치 근거다. 다만 실제 대문자 보존이나 punctuation의 완전 부재까지 코드만으로 확정하지 않는다. 필요한 후속은 접근 가능한 실제 STT 샘플의 확인과 고정된 입력 정규화 민감도 분석이다. rule도 같은 입력으로 비교하되 이는 정규화 stress test이고 원래 comparator 결과와 별도로 보고한다. 현재 task에서 외부 STT 호출은 하지 않았다.

k={3,5,9}×unigram/bigram은 저비용 dev 선택으로 유지한다. 그러나 TF-IDF family 내부 탐색이지 표현력 가설 전체의 검증은 아니다. 낮은 개선으로 “representation은 문제 아님”이라고 결론낼 수 없다. 현재 tokenizer는 숫자·일반 구두점·대문자를 버리고 bag-of-features를 만들며, teacher는 길이·쉼표·repair 등을 쓴다. 이웃의 출처 구성, top-k 유사도, OOV/zero-similarity, label 분산을 먼저 기록하면 후속 표현 변경의 근거가 된다.

Day 1은 k=5 uni/bi를 이미 실행했으므로 중복 재실행을 줄인다. 여러 arm 중 최고값의 nominal CI는 선택 편향을 제거하지 않는다. 이 결과는 dev 선택이며 final 성능 주장에 쓰지 않는다.

### E4 — 지금 15-run 규모로 시작하지 말고 teacher 비교 뒤로 이동

학습량 변화는 IDF·이웃·출처량·label 다양성을 동시에 바꾼다. 기존 표현대로 비인과적 size curve임을 유지한다. “NICT accepted 고정 + 다른 weak 데이터 증가”는 NICT 증가 효과를 테스트하지 않으며 전체 source 비율도 바뀐다. 실제 그룹 기준 source-stratified nested subset을 만들고 각 seed/비율별 행·그룹 수를 기록한다. 동일 100% 집합은 5번 계산할 필요가 없다.

일관된 이득은 **해당 데이터 범위에서의** scale-up 후보 근거다. flat/negative는 teacher 불량·표현 한계·적은 독립 그룹·출처 mix의 어느 것도 배제하지 못한다. source-matched coverage 가설은 고정된 teacher 아래 해당 source 데이터의 추가/제거를 통제한 별도 arm이 더 직접적이다. E1과 개선된 teacher/student 비교에서 다음 의사결정을 바꿀 때만 작은 curve를 실행한다.

### E5 — 숫자 감사만 유지, text-only ceiling 판단은 제외

상수성은 “행이 축 안에서 constant”가 아니라 출처/검수자별 **target 열의** 분산·고유값·비영점 수로 정의한다. 유사 텍스트는 사전 고정한 규칙과 reviewer/source 교차표로 보고한다. 다르게 채점됐다는 사실은 scorer noise일 수도 있어 정보 부족의 증명이 아니다. 사람 기준의 near-duplicate 감사도 노동이므로 숨겨진 추가 labeling으로 확장하지 않는다.

계약 §4는 사람과 모델 모두 현재 발화만 보도록 한다. context reader가 줄 것 같은 가상의 점수를 새 정답으로 가정할 필요가 없다. 부족한 맥락의 예시는 가설 목록까지만, controlled study 없는 ceiling 주장은 계속 금지한다. reserved 항목이나 그 맥락을 이 감사에 사용하지 않는다.

## 3. 가장 짧은 신뢰 가능한 경로와 사람 평가량

**자동 라벨로만 학습한 ML도 현재 gate를 실제로 통과하면 전환 후보가 될 수 있다.** 학습 label이 사람이어야 한다는 gate는 없다. single LLM teacher도 허용 가능한 학습 원천이지만, “강한 모델”이라는 이름이나 AI 간 합의가 사람 평가를 대체하지는 못한다.

권장 순서:

1. 위 provenance split 오류를 먼저 막고 common purged baseline/고정 rule/기존 hybrid의 정확한 모델 명세를 기록한다. E1과 남은 작은 k/ngram 비교, 출처×축 bias/이웃 진단을 한 묶음으로 끝낸다. E2는 필요하면 NICT F/E만, E4는 후순위다.
2. 현재 결정에 맞춰 30×2 calibration 후보/안내의 수정과 rubric 예시의 사람 확인을 준비한다. 채점은 보류 지시를 지키며, 실제 평가 담당자 A/B의 기준을 맞춘 뒤 rubric을 고정한다. 10/source는 약한 screen이며 95% source별 보장이 아니다.
3. cycle 4의 frozen Flash-Lite protocol을 dev에서 한 번 비교한다. gold 점수/출처/bucket/기존 모델 출력을 prompt에 주지 않는다. 직접 teacher 성능과 반복 안정성을 본 다음, 유망하면 **train-only 동일 텍스트**를 자동 재라벨링해 기존 label student와 대체 teacher student를 같은 representation으로 비교한다. dev에서 생성한 teacher labels는 학습에 넣지 않는다. 실제로 필요한 것은 “teacher가 좋아졌다”에서 끝나는 보고가 아니라 “그 teacher를 학습한 배포 후보가 좋아졌다”는 증거다.
4. 자동 teacher/student가 유망하면 대량 사람 training labels와 first40을 필수 경유지로 두지 않는 경로를 제안한다. cycle 4의 Days 6–9 first40 실행 순서를 바꾸는 것은 계획 변경으로 기록한다. 자동 경로가 막힌 경우에만 bounded human-vs-automated same-text 실험이 필요한지 판단한다.
5. dev 기준으로 준비된 **한 후보**의 training 구성(HCRC 포함 여부 포함), 입력/rubric, k/ngram, 코드/hash, comparator, 통계 판정 규칙을 freeze한다. 이후 예약된 final/reproduction을 독립 인간이 blind 채점하고 모델·분석을 고정한 채 각각 평가한다. 불확실하거나 NA면 보류하며 결과를 보고 튜닝했다면 해당 test는 dev로 강등한다.

### “얼마나 작은 human eval로 gate를 지지할 수 있는가?”

cycle 4 AGREED #5의 현행 최소 절차는 **176항목×2명×5축=1,760개 점수**다. 공개 계약상 final 106행(AMI 참고 1행 포함) + reproduction 70행, 총 156그룹이다. 실제 주 평가 영역은 NICT+Taskmaster이고 AMI 한 항목을 평균에 넣어 전반적 coverage 증거로 쓰면 안 된다. 30×2 calibration은 별도 300점, rubric 예시 검증/불일치 조정 비용도 별도다. 4×90은 배포하지 않는다.

**176×2는 현재 정해진 평가 절차이지 통계적으로 충분하다고 증명된 표본 수가 아니다.** 두 rating은 독립 test item 두 개가 아니며, 156그룹도 두 평가 세트로 나뉜다. 0.20 MAE와 축별 0.03 rho 허용폭을 이 규모가 판별할 수 있다는 근거는 아직 없다. 30개 calibration이나 40개 pilot로 해당 gate를 대체할 근거도 없다.

최소 필요량은 candidate와 comparator의 paired 오차 분산, 실제 효과의 margin 대비 거리, 그룹 의존성, Humor 같은 희소 target, 두 세트 각각의 검정력에 달렸다. final을 보지 않고 dev의 paired group 분포로 가정별 power/precision 시뮬레이션을 먼저 한다. 단일 평균의 단순 근사에서도 95% 반폭은 약 `1.96 × SD(paired group difference) / sqrt(G)`이며 SD와 G 없이는 숫자를 정할 수 없다. 이 식은 Spearman이나 불균등 cluster용 최종 산식이 아니다.

최종 분석 전에 MAE delta의 upper bound를 +0.20과 비교할지, 평균 rho delta의 lower bound를 0과 비교할지, 각 축 lower bound를 −0.03과 비교할지 등 “CI 고려”의 정확한 뜻과 두 세트의 적용 방법을 못박아야 한다. 평균/축별 joint gate의 interval 해석, source별 재표본 방식, constant bootstrap 표본의 처리/빈도도 고정한다. NA 표본을 버려 낙관적인 CI만 남기거나 5축 gate를 4축으로 바꾸지 않는다. 10,000회 bootstrap은 데이터 정보량을 늘리지 않는다.

따라서 현재 계약을 유지하면서 더 작은 확정 숫자를 약속할 수 없다. 176×2부터도 실패/불확실 가능성을 인정해야 한다. 1인+일부 이중 채점, 순차 평가, 표본 축소를 원하면 별도의 사전 계획·정밀도 근거와 사용자 승인이 필요하다. test 결과를 본 뒤 유리할 때만 멈추거나 추가 표본으로 통과할 때까지 연장하면 안 된다. dev Humor 분포는 경고 신호지만 예약 pool의 Humor 분포는 확인하지 않았으며 미리 단정하지 않는다.

## 4. 빠진 중요한 배포 검증

Day 1의 bigram/experimental 결과를 `PALLY_AXIS_ANALYZER=ml`만으로 배포할 수 있는 것처럼 취급하면 안 된다. `ai/analyzers.py::MLAxisAnalyzer` 기본 생성자는 `TfidfKnnAxisRegressor()` 즉 **k=5/unigram**을 쓰고, 데이터는 `PALLY_AXIS_DATASET` 또는 `data/axis_dataset_week2.jsonl`을 로드한다. 연구 후보의 k/ngram/purged training 구성과 자동으로 같아지지 않는다.

최종 gate 전에 배포 adapter가 바로 그 frozen artifact를 사용하는지 검증해야 한다. adapter는 예외 시 rule로 fallback하므로 fallback이 섞인 출력을 순수 ML 성공으로 세지 않는다. 최종 비교 hybrid도 “fixed old hybrid”라는 이름만으로 부족하며 rule 코드, ML k/ngram, 실제 training hash를 모두 식별해야 한다. Day 1의 연결 hybrid는 학습이 바뀔 때 같이 변하므로 그것만으로 고정 comparator가 준비된 것은 아니다.

## 5. 남은 사용자 결정 — 필요한 순서

1. **진단 후 U1 확정:** human-perceived tone gate 유지가 현재 기본이다. teacher 재현 목표로 바꾸는 경우에만 명시적 목표/판정 변경 승인이 필요하다. E1 결과가 어떤 방향이든 변경이 강제되지 않는다.
2. **진단 결과에 따른 사람 작업/실행 순서:** 자동 teacher→student 경로로 first40을 건너뛸지, bounded first40을 진행할지, calibration 실제 배포·채점을 언제 재개할지 확정한다. U2의 4×90 보류와 30×2 재설계는 이미 정해졌으므로 다시 선택시키지 않는다. 자동 teacher 외부 호출은 기존 승인·예산 범위 내에서 진행하고 범위를 넘는 경우만 별도 비용 결정을 받는다.
3. **최종 평가 계획의 미정/변경 사항:** 현행 176×2와 NICT+Taskmaster 범위를 기본으로 모델 준비 후 채점 실행을 확정한다. CI-based pass/inconclusive 의미를 concrete protocol로 작성하고, 허용폭·필수 축·검수자 수·표본 크기·AMI 범위·재현 요건을 바꾸려면 평가 전 명시 승인을 받는다. seed/hash 지정과 split 오류 수정 자체는 새로운 사용자 선택 사항이 아니다. AMI 일반화 제외도 이미 승인된 사항이다.
4. **gate와 reproduction 통과 후 runtime 전환 명시 승인:** 실제 배포 후보와 연구 후보 일치, rule 대비 퇴행 보고, hybrid fallback/rollback 준비를 제시한 뒤 `PALLY_AXIS_ANALYZER=ml` 전환을 승인받는다. 통계적으로 불확실하면 통과로 간주하지 않는다.

이번 검토는 외부 호출·라벨 작성·모델/설정 변경 없이 수행했고, 수정 대상은 이 파일 하나다. 실행 시 이미 수정돼 있던 다른 ai-collab 문서는 그대로 두었다. commit/push/reset/checkout/pull은 하지 않았다.
