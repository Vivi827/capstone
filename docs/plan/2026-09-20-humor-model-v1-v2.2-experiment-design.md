# Humor/3축 실험 설계 — 상태 및 이력 (실제 설계서는 PR #82에 있음)

개정: 2026-09-22 · 상태: **이 파일은 더 이상 설계서 본문을 담지 않는다.** 실제 진행할 설계서는 아래 "현재 확정본" 참고.

---

## 현재 확정본

**PR #82** (`puter8/capstone`, 아직 main 미병합, 작성자 Vivi827)의 다음 문서가 진행할 실험 설계서다.

```
docs/AI_TACTIC/Pally_Communicative_Purpose_Aware_Experiment_Design_2026-09-22.md
```

로컬 working tree엔 없다(다른 PR 소유 문서). 읽으려면:

```bash
git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'
git show origin/pr/82:docs/AI_TACTIC/Pally_Communicative_Purpose_Aware_Experiment_Design_2026-09-22.md
```

**핵심 구조:**

```
조건 A (Direct)         사용자 턴 → Formality/Humor/Curiosity 직접 예측 → 응답
조건 B (Purpose-aware)  사용자 턴 → 대화 목적(10종) 예측 → 목적을 입력받은 3축 예측 → 응답
```

- **주 결과**: 최종 응답의 블라인드 A/B 쌍대 승률(연구팀 3인 + LLM judge 3개, 정답 명세 기반) — 3축 점수 정확도가 아니라 **응답 품질**이 주 지표다.
- **과정/진단 지표**: 대화 목적 macro-F1, 축별 MAE·Spearman, 목적 오분류→축 오류→응답 오류 전파.
- **필수 조작 점검(5.2절)**: B의 예측된 목적이 3축 평가기 입력에 실제로 연결돼야 함 — 동시 출력 금지.
- **13절에 현재 코드 기준 구현 격차**가 명시돼 있다 — 실험 시작 전 반드시 확인:
  - `PALLY_AXIS_ANALYZER` 기본값이 `rule` (실험용 고정 모델·checkpoint 명시 필요)
  - 3축이 계산은 되지만 Gemini 응답 생성 함수에 전달되지 않음
  - 대화 목적 분류기와 B 경로 자체가 아직 없음
  - 이전 대화 최대 10턴이 Gemini에 전달됨 (실험에서는 `history=[]` 강제 필요)
  - 프롬프트에 1문장/1–2문장 지시가 혼재
  - 운영 EMA·관계 상태가 개입 가능 (실험에서는 비활성화 필요)
  - → 운영 `/api/chat`을 직접 고치지 말고 별도 experiment runner로 격리할 것을 권장함 (13절)
- 인용: Stolcke et al. 2000(대화행위), Pei/Sun/Xu 2019·Sun/Zemel/Xu 2022(슬랭), Röttger et al. 2022(주관 라벨링), Ribeiro et al. 2020(CheckList), Liu et al. 2023(G-Eval)·Zheng et al. 2023(judge 편향)·Sellam et al. 2020(BLEURT).

**미확인 사항 (PR82 문서 자체엔 없음, 팀 확인 필요):**
- 기존 `humor_v2.2_scoring_slot{A-D}.xlsx` 워크북(v2.2 스키마: primary_function/language_form/축 점수/case_type 등)이 이 설계의 자료 수집에 그대로 쓰일 수 있는지 — PR82의 7.1절 슬라이스 구성(clear 40%/ambiguous_informal 35%/surface_shortcut 25%)은 이전 "Boundary-aware" 문서의 6개 층 쿼터와 다르다. 워크북 문항이 이 3-슬라이스 목표에 맞는지 재확인 필요.
- PR #82가 언제 main에 머지되는지 — 머지 전까지는 위 `git show` 명령으로 계속 확인.

---

## 이력 (혼동 방지용, 최신이 위)

| 시점 | 설계 | 상태 |
| --- | --- | --- |
| 2026-09-22 (PR #82 최신 커밋) | **Direct vs Purpose-aware hierarchical** — 대화 목적을 중간 표현으로 써서 응답 품질(블라인드 A/B)이 개선되는지 | **확정, 진행** |
| 2026-09-22 (이 파일의 이전 버전) | v2.2 Base(clear만 학습) vs v2.2 Boundary-aware(clear+boundary 학습) — Humor MAE 기준 | 폐기 — PR82 정식 문서로 대체됨 |
| 2026-09-22 초 | End-to-end(3축만) vs Oracle-function(발화기능 먼저 판정) | 폐기 — Boundary-aware로 대체됐다가, 결과적으로 PR82의 Purpose-aware(구조상 거의 동일한 아이디어를 더 엄밀하게 formalize한 버전)로 다시 수렴함 |
| 2026-09-21 | v1.0(naive, context_insufficient 무시) vs v2.2(rubric 준수) 가중치 비교 | 폐기 — "규칙 준수 여부는 비교 대상이 아니다"는 지적으로 폐기 |

**참고:** PR #79는 이번 연구와 무관 (결제/쿼터 기능 PR).

---

*이 파일은 더 이상 유지보수되는 설계서가 아니라 이력·포인터 문서다. 다음 세션은 이 파일 대신 위 "현재 확정본"의 `git show` 명령으로 PR82 문서를 직접 읽을 것.*
