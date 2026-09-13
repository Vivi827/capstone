# Claude Code Review — Round 1 (ML Transition Roadmap Proposal)

작성 시각: 2026-09-07. 이전 사이클(gold-200 진단, `archive/2026-09-07-gold200-diagnosis/`)의
`DECISION.md`에 있는 AGREED/DISAGREED/EVIDENCE NEEDED/ACTION을 근거로 다음 단계
로드맵을 제안한다. 아직 아무 코드도 수정하지 않았다.

## 목표

`docs/ml-transition-plan.md`의 ML Acceptance Gate(4개 기준)를 실제로 통과시키기 위해
무엇을, 어떤 순서로 해야 하는지 결정한다.

## 현재 상태 요약 (이전 사이클에서 확정된 사실)

gold-holdout 평가(3,137개로 학습 -> gold-200 human label로 평가):

| Axis | rule Spearman | ML Spearman | hybrid Spearman |
|---|---:|---:|---:|
| Formality | 0.16 | **0.46** | 0.39 |
| Curiosity | 0.77 | 0.68 | **0.76** |
| Intimacy | 0.39 | 0.27 | **0.45** |
| Energy | **0.45** | 0.03 | 0.29 |
| Humor | 0.09 | -0.04 | 0.05 |

overlap/nonoverlap 분리 재평가에서 leakage가 원인이 아님을 확인함 (nonoverlap 60개에서도
ML Spearman 0.16으로 rule 0.32의 절반) — 즉 ML이 못하는 건 진짜로 못하는 것이지 학습셋과
겹쳐서 착시가 낀 게 아니다.

## 제안 로드맵

| # | 항목 | 사람 라벨링 필요? | 이유 |
|---|---|---|---|
| 1 | Reviewer calibration: 같은 30-50개 발화를 reviewer-avg/reviewer-01 두 프로토콜이 독립 채점, agreement 계산 | 필요 (적음) | gold-200의 reviewer-avg(AMI+NICT)/reviewer-01(Taskmaster+NICT) source 구성이 완전히 분리돼 있고, reviewer-01은 Humor를 100개 전부 0으로 매겼다. 이게 "진짜 유머 없음"인지 "채점자 스타일"인지 구분 안 되면 Humor 관련 어떤 결론도 못 믿는다 |
| 2 | train-120 (Energy/Curiosity) 검수 완료 | 필요 (이미 CSV 배포됨) | 이미 뽑아놓은 것부터 처리 |
| 3 | `ai/ml_baseline.py`에 partial-label 학습 지원 (축별 독립 regressor) | 불필요 | train-120이 2축만 있어서, 지금 구조로는 나머지 3축을 뭔가로 채워야 해 라벨 위조가 됨. 축별로 독립 학습해야 함 |
| 4 | Energy/Humor 표본 마이닝: AMI/CHiME-6의 `annotation_events`(laughter 등)를 후보 탐색 힌트로만 사용하고 사람이 최종 채점 | 필요 (마이닝된 후보만) | 학습셋에 real-speech 기준 Energy>=50은 126개 중 15개, Humor>=40은 37개 중 5개뿐 — teacher rubric도 ML도 배울 positive 예시 자체가 없다 |
| 5 | Energy ML feature에 텍스트 강도 신호 추가 (`!` 개수, 대문자 비율, 반복 문자) | 불필요 | 지금 TF-IDF word n-gram만으로는 "That's great." vs "THAT'S GREAT!!"를 구분 못 함 |
| 6 | Intimacy는 draft rubric 대신 사람 라벨로 교체 | 필요 | `draft_axes()`의 Intimacy 가산 조건(대명사 정규식)이 사실상 상수를 만든다 — 이 rubric으로 더 만들어봤자 무의미, 사람 라벨이 필요 |
| 7 | gold-200 bucket-sensitivity 재검증 (`classify_bucket()` 신규 작성, 이전 사이클 Codex 지적사항) | 불필요 | Curiosity 0.83이 `sample_bucket` 폴백 때문에 과장된 값일 가능성 — 확정 전 마지막 점검 |
| 8 | 남은 gold candidate 400개 중 현재 학습셋과 source_group이 완전히 안 겹치는 것만 골라 최종 blind test 예약 | 나중에 필요 | 지금 gold-200은 72개가 학습셋과 겹쳐서 엄밀한 gate 판정용으로는 약함 |
| 9 | 재평가 -> gate 4개 기준 확인 -> 다른 held-out으로 재현 확인 | 불필요 (재평가만) | 이후에 사용자 승인 받고 `PALLY_AXIS_ANALYZER=ml` 전환 |

**바로 코드/실험만으로 착수 가능한 것: 3, 5, 7.**
**사람 라벨링이 필요한 것: 1, 2, 4, 6.**

## Risks / Uncertainties

- 4번(Energy/Humor 표본 마이닝)은 "얼마나 마이닝해야 충분한가"에 대한 기준이 없다.
  최소 표본 크기를 먼저 정해야 실행 가능하다.
- 5번(텍스트 강도 피처)이 실제로 Energy Spearman을 얼마나 올릴지 사전에 알 수 없다 —
  작은 ablation 실험으로 먼저 검증해야 한다.
- 1번(reviewer calibration)에서 두 프로토콜이 실제로 다른 결과를 낸다는 게 확인되면,
  기존 gold-200의 절반(reviewer-01이 채점한 100개)을 재검수해야 할 수도 있다 — 이건
  일정/리소스에 큰 영향을 준다.
- 이 로드맵은 "무엇을 해야 하는가"에 대한 것이지 "어떤 순서가 최적인가"에 대한
  근거는 약하다 (예: 1번을 3번보다 먼저 할 이유가 "확신을 위해서"이지 "막혀서"는 아님).

## Next Experiment / 확인 필요

- 이 로드맵 순서 자체가 타당한지, 빠진 단계가 없는지 비판적으로 검토해달라.
- 특히 4번(표본 마이닝)과 6번(Intimacy 사람 라벨 교체)이 실제로 얼마만큼의 사람
  라벨링 리소스를 요구하는지 규모를 가늠해줄 수 있는지 봐달라.
