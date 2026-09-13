# Current Task — 실행 계획 (Execution Planning)

> 이전 두 사이클은 아카이브됨:
> - `archive/2026-09-07-gold200-diagnosis/` — gold-200 teacher-label 진단
> - `archive/2026-09-08-roadmap-review/` — ML 전환 9단계 로드맵의 Codex 방법론 검토
>
> **이번 사이클의 근거 문서**: `archive/2026-09-08-roadmap-review/DECISION.md`
> (ACTION 6개 + EVIDENCE NEEDED 6개 + AGREED/DISAGREED). 그 전략 결정을 바꾸는 게
> 아니라, **구체적 실행 단계로 옮기는 것**이 이번 목표.

## 목표(Goal)

`archive/2026-09-08-roadmap-review/DECISION.md`의 ACTION/EVIDENCE NEEDED를 실행 가능한
단계로 구체화한다:
- 사람 라벨링이 필요한 CSV 파일 3종의 정확한 사양(소스, 선정 방법, 축, 2인 채점 포맷)
- 내가 병행할 코드 작업 3종(partial-label 학습 지원, bucket-sensitivity 분석, `_pearson` NA 처리)의 정확한 구현 범위
- clean-candidate 격리(최우선)의 실행 방법

## 진행 방식 (3단계, 무한 루프 금지)

1. **Claude Code (실행 계획 초안, done)** -> `CLAUDE_REVIEW.md`
2. **Codex (실행 가능성/누락 검토)** -> `CODEX_REVIEW.md`
3. **Claude Code (합의/불일치 정리 + 최종 실행 계획)** -> `DECISION.md`

1·2단계는 코드를 수정하지 않는다. 읽기 전용 집계만 허용.

## Round 2 지시 (Codex용)

`CONTEXT.md`, `CLAUDE_REVIEW.md`, `archive/2026-09-08-roadmap-review/DECISION.md`,
`archive/2026-09-08-roadmap-review/CODEX_REVIEW.md`를 읽고, `CLAUDE_REVIEW.md`의
실행 계획에서:

- CSV 사양의 결함 (소스 선택이 최종 test pool을 오염시키는지, blind 처리 누락, 2인 채점 포맷이 개인 점수를 실제로 보존하는지)
- 코드 작업 범위가 이전 DECISION.md의 결정과 어긋나는 부분
- 실행 순서의 문제 (격리 전에 후보를 뽑아 오염시키는 등)
- partial-label 구현 접근(축별 독립 vs 공유 feature+축별 이웃 필터)의 트레이드오프
- bucket-sensitivity 재구성이 "원래 bucket 복원"으로 과대 표현되는지
- 빠진 검증/계약 (평가 comparator 고정, source-group bootstrap, gate #4 그룹 예약)

을 찾아 `CODEX_REVIEW.md`에 작성한다. 실제 repo 데이터로 검증 가능한 주장은 검증한다.
아직 코드는 수정하지 않는다.
