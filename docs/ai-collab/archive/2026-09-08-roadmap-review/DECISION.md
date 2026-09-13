# Decision — Round 3 (Claude Code, after Codex Round 2)

작성 시각: 2026-09-07. Codex의 7개 지적을 전부 실제 코드/데이터로 재검증했다.
**전부 정확했다.** 그중 하나(Intimacy)는 내 원래 진단을 명백히 뒤집는다.

## 검증 결과

| Codex 주장 | 검증 결과 |
|---|---|
| Intimacy 대명사 정규식이 gold-200 200개 중 거의 전부가 아니라 **102개(51%)에만** 매칭 | **정확** — 내 "거의 모든 문장에 걸린다"는 서술은 틀렸다 |
| real-speech 학습 데이터의 Intimacy는 **17개 고유값, 범위 22~59** | **정확** (2,799개 real-speech 행 기준) |
| `scripts/build_human_reviewed_axis_dataset.py`뿐 아니라 `ai/ml_baseline.py::_validate_axes()`도 `int()`로 절삭 — 변환기만 고쳐도 loader에서 다시 잘림 | **정확**, 코드 확인됨 |
| `TOKEN_PATTERN = r"[a-z']+\|[!?]+"`가 이미 `!`/`?` 시퀀스를 별도 토큰으로 잡음 — "느낌표 신호가 아예 없다"는 표현은 부정확, 다만 대문자 비율/반복 문자 길이 feature는 확실히 없음 | **정확** |
| `_pearson()`은 한쪽이 상수면 0.0을 반환 — Humor처럼 한쪽이 전부 0인 subgroup의 Spearman은 "낮다"가 아니라 사실상 "정의 불가"에 가까움 | **정확**, 확인됨 (0.0 반환) |
| 남은 gold candidate 400개 중 "학습셋과 안 겹침이 확인된" 건 121개뿐(AMI 5 + Taskmaster 116), NICT 132개는 여전히 판정 불가, AMI는 133개 중 128개가 이미 겹침 | **정확히 일치** (121 = 5+116) |
| "leakage가 원인이 아님을 확인했다"는 표현이 인과적으로 과도함 — nonoverlap 60개(AMI 2/Taskmaster 58, 소스 편중)에서 ML이 낮았다는 건 "그 부분집합에서도 우위가 없었다"는 관찰이지, leakage 영향 자체를 분리 측정한 게 아님 | **정확** — 표현을 정정해야 함 |

## AGREED

- 현재 데이터로 `PALLY_AXIS_ANALYZER=ml` 전환 근거 없음. 방향은 유지.
- 같은 draft rubric으로 발화 수만 늘리는 접근은 비효율적 — Energy/Humor는 rubric이
  50/40 이상을 못 내는 게 아니라(학습셋에 각각 126개/37개 존재), **그 점수를 받은
  발화 자체가 real-speech 표본에서 희소한 것**이 문제.
- gold-200은 반복 진단에 이미 썼으므로 "dev/diagnosis set"으로 재정의하고, 진짜
  최종 acceptance test는 아직 손대지 않은 그룹으로 새로 구성해야 한다.
- 라벨 정밀도(0.5단위 평균)와 모델 출력 정수 정책은 지금 이중으로 잘리고 있어
  분리해서 정책을 정해야 한다.
- partial-label 학습 지원은 필요하다 (구현 자체는 사람 라벨 없이 가능, 유용성
  검증에만 실제 검수 라벨 필요).

## DISAGREED / 정정 (내 로드맵 제안 중 틀리거나 과장된 부분)

- **"Intimacy rubric이 대명사 때문에 거의 상수"라는 진단은 틀렸다.** 실제로는
  200개 중 102개(51%)에만 매칭되는 이분법적 신호이고, 학습 데이터에도 17개 고유값이
  존재한다. 내가 본 "37~49대에 뭉침"은 gold-200 진단 스크립트가 `sample_bucket` 없이
  기본값(personal_statement)으로만 돌린 인공물이었지, rubric 자체의 결함이 아니다.
  → **#6(Intimacy를 사람 라벨로 전면 교체)의 근거는 재검토 필요.** rubric이 좁은
  분포/타당성 문제는 있을 수 있어도 "무정보"는 과장.
- **"leakage가 ML 부진의 원인이 아님을 확인했다"는 인과적 결론은 과도했다.** nonoverlap
  60개에서도 ML이 낮았다는 건 사실이지만, 이 60개 자체가 AMI 2/Taskmaster 58로 극단적으로
  편중돼 있어 "일반적으로 leakage와 무관하다"고 일반화할 근거는 약하다. 앞으로는 "leakage
  영향의 크기는 미확정, 다만 이 부분집합에서도 ML 우위는 관찰 안 됨"으로 표현을 낮춘다.
- **#8(남은 400개를 최종 gate용으로 예약)의 우선순위가 너무 낮았다.** 실제로 즉시 쓸 수
  있는 clean 후보가 400개가 아니라 121개(그것도 NICT 132개 판정 보류 상태)뿐이라는 걸
  몰랐다. 이건 다른 모든 라벨링 작업보다 먼저 그룹을 예약해둬야 한다 — 나중에 하면 그
  사이 다른 실험에서 이 121개 중 일부를 이미 봐버렸을 위험이 있다.
- Energy/Humor 표본 부족을 "positive 예시가 없다"고 쓴 건 부정확 — draft rubric 점수
  기준 희소성이지, 사람이 봤을 때 진짜 positive가 없다는 뜻이 아니다.

## EVIDENCE NEEDED (Codex가 구체적 규모까지 제안함 — pilot 우선)

1. **그룹 예약 (최우선, 지금 바로 가능, 코드 불필요)**: 121개 known-clean(AMI 5 +
   Taskmaster 116) + NICT 132개 unknown을 다른 어떤 실험에도 쓰지 않도록 지금 즉시
   따로 표시/격리. NICT provenance(`source_line`) 복구 가능한지도 확인.
2. **Reviewer calibration pilot (48발화)**: AMI/NICT/Taskmaster 각 16개, 실제 사람
   2명이 5축 전부 독립 채점 (96 발화-검수 건, 480 축 점수). 개인 점수를 반드시 보존
   (지금처럼 평균만 남기지 않는다).
3. **Energy/Humor pilot (60발화)**: annotation_events 힌트 20 + 모델 불일치 후보 20 +
   무작위 대조 20, 두 명이 독립 채점 (120 발화-검수 건, 240 축 점수). laughter 태그는
   힌트일 뿐 정답 아님 — 대조군 필수.
4. **train-120은 전체가 아니라 40개 먼저**: calibration 끝난 뒤 소스/이유를 섞어
   40개만 먼저 검수하고, 실제 label yield와 오류 유형이 나오는지 보고 나머지 진행
   여부 결정. Intimacy는 같은 발화에 추가해서 중복 검수 비용 절감.
5. **점수 정밀도 정책 확정**: 사람 평균은 0.5단위로 보존할지, 모델 계약은 정수로
   할지 분리해서 결정 — 지금처럼 암묵적으로 이중 절삭되는 상태로 두지 않는다.
6. **평가 코드 보강**: `_pearson()`이 상수 입력에서 0을 반환하는 걸 그대로 "성능
   나쁨"으로 오독하지 않도록, 유효 축 수/NA 표시를 평가 리포트에 추가.

## ACTION (순서, Codex 권장안 채택)

1. **지금 바로**: 121개 known-clean + NICT 132개 unknown을 다른 실험에서 격리 —
   새 코드 불필요, 목록만 만들어서 문서화.
2. `docs/ml-transition-plan.md`에 이번 두 사이클(진단 + 로드맵 검토) 결과 반영:
   gold-200 역할 재정의, leakage 결론 표현 수정, 남은 clean 후보가 121+132(unknown)뿐이라는
   사실.
3. **다음 우선순위는 사람 라벨링 pilot 설계**: reviewer calibration 48개 + Energy/Humor
   pilot 60개 CSV를 준비 — 이건 제가 스크립트로 만들 수 있음(사람 검수 자체는 아니지만
   후보 추출/CSV 생성은 코드 작업).
4. partial-label 학습 지원(`ai/ml_baseline.py`)은 병행 가능 — pilot 결과를 기다릴
   필요 없이 구조만 먼저 구현.
5. `!`/`?` 토큰 신호는 이미 있으므로, Energy feature 추가는 "느낌표 추가"가 아니라
   "대문자 비율·반복 문자 길이"로 범위를 좁혀서 작은 ablation부터.
6. Intimacy 사람 라벨 교체는 **보류** — calibration 48개 결과와 train-120 첫 40개
   결과를 먼저 보고 판단 (rubric이 "무정보"라는 전제가 틀렸으므로 시급성이 낮아짐).
