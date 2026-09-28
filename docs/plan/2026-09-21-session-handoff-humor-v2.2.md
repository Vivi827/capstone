# 세션 핸드오프 — Humor v2.2 실험 (논문용)

작성일: 2026-09-21 · 목적: 새 세션에서 이어서 작업하기 위한 컨텍스트 정리

---

## 0. 지금 상황 한 줄 요약

논문 작성(9/30 마감)을 위해, Pally 5축 중 **Formality/Humor/Curiosity 3축**을 rubric v2.2 기준으로 다시 정의하고, **"발화기능(대화 목적)을 먼저 판정하면 애매한 표현 판정이 좋아지는가"**를 비교하는 실험을 준비 중이다. Energy/Intimacy는 이번 논문 범위 밖(`null`).

---

## 1. 반드시 먼저 읽어야 할 문서 (우선순위 순)

1. **`CLAUDE.md`** (repo root) — 팀 규칙 전체. 특히 §6(Top 5: 외부 API 실호출, 검증 없는 완료보고 금지, 에러 안 삼키기, `git add .` 금지, 비즈니스 로직 추측 금지)와 §1(팀 역할 — 최윤서=PM, 은혜=BE·AI)은 매 세션 적용됨.

2. **`docs/AI_TACTIC/Pally_RUBRIC_v2.2_md`** — **가장 중요.** 최윤서가 작성한 공식 확정 rubric. **아직 main에 병합 안 됨 (PR #82)**, working tree엔 없음. 읽으려면:
   ```bash
   git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'
   git show origin/pr/82:docs/AI_TACTIC/Pally_RUBRIC_v2.2_md
   ```
   핵심 내용: 발화기능 10개 분류, Formality/Humor/Curiosity 구성요소 가중치, Curiosity의 발화기능별 점수 clamp, `case_type`(clear/boundary/context_insufficient) + `score_status`, 학습 가중치 규칙(13절), **End-to-end vs Oracle-function 비교(15절 — 지금 하려는 실험의 근거)**.

3. **`docs/plan/2026-09-20-humor-model-v1-v2.2-experiment-design.md`** — 이번 세션에서 작성한 실험설계서. **주의: 5절("비교할 두 모델")이 최신 결정을 반영 못 한 상태다.** 마지막 대화에서 "v1.0(naive weighting) vs v2.2(rubric weighting)" 비교를 버리고, **"End-to-end(3축만) vs Oracle-function(발화기능+3축)"** 비교로 전환하기로 했음 (§5 아래 "최신 결정" 참고). 이 파일의 5절은 다음 세션에서 업데이트 필요.

4. **`docs/AI_TACTIC/Pally_RUBRIC_v2.1_md`** (PR #76, main 미병합, `git show origin/pr/76:...`) — v2.2 이전 버전. 왜 v2.2로 바뀌었는지(직전 턴 필요 문제, Intimacy/Energy 처리 등) 이해하는 데 참고용. 지금은 v2.2가 우선.

5. **`docs/AI_TACTIC/TASKS_0917.md`** (같은 PR #76) — 데이터 수집 가이드. Energy/Intimacy가 왜 `null`인지, Intimacy가 왜 애초에 ML 학습 불필요한지 근거.

6. **`docs/energy-voice-data-qa-2026-09-17.md`** (main에 있음, 커밋됨) — Energy/음성 데이터 관련 Q&A 전체 기록. Energy를 이번 논문에서 제외한 배경.

7. **`docs/ml-transition-diagnosis-log.md`** (main에 있음) — 더 큰 배경: 이 axis 모델 자체가 왜 ML 전환을 시도하고 있는지, NICT 라벨이 실제로는 사람이 검증 안 한 AI 초안이었다는 발견 등. 논문의 "왜 사람 라벨이 필요한가" 서론 근거로 쓸 수 있음.

---

## 2. 이번 세션에서 새로 만든 파일 (아직 커밋 안 됨, `git status`로 확인)

| 파일 | 내용 |
|---|---|
| `scripts/export_humor_v2_2_workbook.py` | v2.2 스키마 채점 워크북 생성 스크립트 (재실행 가능) |
| `data/fixtures/humor_v2.2_candidates_check.xlsx` | 후보 문장 57개 목록(점수 없음, 검토용) — remainder50 원문 50개 + 새로 찾은 유머 경계사례 7개 |
| `data/fixtures/humor_v2.2_scoring_slot{A,B,C,D}.xlsx` | **실제 채점용 워크북 4개.** 안내/발화기능·문법기준/채점기준표/채점 예시/채점 시트 5개 탭. `primary_function` 컬럼 포함 — 이게 있어서 End-to-end vs Oracle-function 비교에 추가 데이터 수집 없이 바로 쓸 수 있음. |
| `data/fixtures/remainder50_scoring_slotB.xlsx` | 구버전(pre-v2.2) 채점 결과. **점수는 폐기 대상, 문장 텍스트만 재사용됨.** |
| `docs/plan/2026-09-20-humor-model-v1-v2.2-experiment-design.md` | 실험설계서 — **2026-09-22 전면 교체됨.** 아래 3번 참고 |

**다음 세션에서 제일 먼저 확인할 것**: `humor_v2.2_scoring_slot{A-D}.xlsx` 채점이 실제로 얼마나 진행됐는지(최윤서/민주 등에게 확인).

---

## 3. 현재 확정된 실험 설계 (2026-09-22 재갱신 — PR #82 정식 문서가 최종)

**주 비교가 세 번째로 바뀌었고, 이번엔 GitHub PR #82에 실제로 올라온 정식 문서를 최종으로 확정했다.** 이 문서는 로컬 `docs/plan/`이 아니라 다른 사람(Vivi827) 소유 PR에 있으므로, `docs/plan/2026-09-20-humor-model-v1-v2.2-experiment-design.md`는 이제 설계서 본문을 담지 않고 이 문서를 가리키는 포인터로만 남겨뒀다.

```
git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'
git show origin/pr/82:docs/AI_TACTIC/Pally_Communicative_Purpose_Aware_Experiment_Design_2026-09-22.md
```

```
[조건 A: Direct]         사용자 턴 → Formality/Humor/Curiosity 직접 예측 → 응답
[조건 B: Purpose-aware]  사용자 턴 → 대화 목적(10종) 예측 → 목적을 입력받은 3축 예측 → 응답 (동일 생성기)
```

- **주 결과는 3축 정확도가 아니라 최종 응답 품질** — 익명화된 A/B 응답을 연구팀 3인 + 다른 계열 LLM judge 3개가 양방향 순서로 블라인드 쌍대 평가(승/동률/둘다부적합), 연구자 사전 정의 응답 명세(reference_response/required_properties/forbidden_errors) 기준.
- **과정 지표**: 대화 목적 macro-F1, 축별 MAE·Spearman, 목적 오분류→축 오류→응답 오류 전파율.
- **필수 조작 점검**: B가 예측한 목적이 3축 평가기 입력에 실제로 연결돼야 함 (동시 출력이면 실험 조작 자체가 성립 안 함).
- **⚠️ 13절 — 실험 전 반드시 처리해야 할 구현 격차 (실제 코드 점검 결과)**:
  - `PALLY_AXIS_ANALYZER` 기본값 `rule` → 실험용 고정 모델/checkpoint 명시 필요
  - 3축 점수가 계산은 되지만 Gemini 응답 생성 함수에 전달 안 됨
  - 대화 목적 분류기 자체가 없음 (B 경로 신규 개발 필요)
  - 이전 대화 최대 10턴이 Gemini에 전달되는 중 → 실험에서는 `history=[]` 강제해야 함
  - 프롬프트에 1문장/1–2문장 지시 혼재, 운영 EMA·관계 상태가 개입 가능 → 실험은 운영 `/api/chat`을 직접 고치지 말고 별도 experiment runner로 격리 권장
- Energy/Intimacy는 측정 안 함(`null`). remainder50 기존 5축 점수는 전부 폐기(v2.1→v2.2 이름만 바꿔 재사용 금지).
- IRB: 신규 외부 참여자 모집 안 함(연구팀 내부 평가), 그래도 "IRB 불필요"를 이 문서만으로 단정하지 않음 — 소속기관 확인 필요(11.3절).

**⚠️ 미확인 — 다음에 할 일:** 새 정식 문서의 7.1절 슬라이스 구성(clear 40% / ambiguous_informal 35% / surface_shortcut 25%)은 이전 "Boundary-aware" 문서의 6개 층 쿼터와 다르다. 지금 있는 `humor_v2.2_scoring_slot{A-D}.xlsx` 워크북(57개: remainder50 재사용 50 + humor_extra 7)이 이 새 3-슬라이스 목표에 맞는 구성인지 다시 확인해야 한다 — 그대로 재사용 가능한지, 후보를 다시 골라야 하는지 아직 모름.

**폐기된 이전 설계들** (참고용, 사용 금지):
1. "v1.0(회색지대 무시 학습) vs v2.2(회색지대 반영 학습)" 가중치 비교 — 은혜님이 "의미 있다/없다를 따질 수준이 아니라 그냥 업데이트했다가 된다"고 지적해서 폐기.
2. "End-to-end(3축만) vs Oracle-function(발화기능 먼저 판정)" 비교 — 2026-09-22 초에 세션 내에서 확정.
3. "v2.2 Base(clear만) vs v2.2 Boundary-aware(clear+boundary)" 비교(Humor MAE 기준, 교수 검토 전 초안으로 세션에 붙여넣어짐) — 잠시 "최종"으로 채택됐다가, PR #82에 실제로 올라온 더 상세한 정식 문서(Purpose-aware, 구조상 2번과 유사하나 훨씬 엄밀)를 다시 확인하면서 최종적으로 대체됨.

**참고:** PR #79는 이번 연구와 무관 (결제/쿼터 기능 PR, docs/data/scripts 변경 없음).

---

## 4. 아직 해결 안 된 것 / 조심할 것

- ~~"Base vs Boundary-aware" 문서의 미완성 문장 2곳, 43개 데이터 격차~~ — 그 문서 자체가 PR #82 정식 문서로 대체돼 더 이상 유효하지 않음(3절). PR #82 문서엔 그런 미완성 부분이 없음.
- **PR82 13절 구현 격차가 최우선** — 대화 목적 분류기(B 경로)가 아예 없고, 3축이 Gemini 응답 함수에 전달 안 되고, 이력 10턴이 그대로 전달되는 등 실험을 실제로 돌리기 전 코드 작업이 여러 건 필요함(3절 참고). 채점 시트보다 먼저 이 격차부터 팀과 우선순위를 정해야 할 수 있음.
- **워크북 재사용 여부 미확인** — `humor_v2.2_scoring_slot{A-D}.xlsx`(57개)가 PR82 7.1절의 새 슬라이스 구성(clear 40%/ambiguous_informal 35%/surface_shortcut 25%)에 맞는지 확인 안 됨.
- **채점 진행 0건** — slot A/B/C/D 전부 `reviewer_id` 플레이스홀더 상태, 채점 미시작 (2026-09-21 세션에서 확인, 재확인 필요).
- **60개 bias-calibration 데이터** (`ml_transition_bias_calib_review.slotA/B`) — 독립 채점인데 85% 일치했던 정합성 문제, **미해결. 이 데이터는 어디에도 쓰지 않는다.**
- **"3일 실험 계획"(슬랭 의미 판별) 문서**와 지금 이 v2.2 실험은 **서로 다른 실험**이다. 논문에 어느 쪽을 쓸지(혹은 둘 다인지) 최종 확답을 최윤서한테 받은 적은 없음 — 다만 최근 대화 흐름상 v2.2(일반 유희적 의도) 쪽으로 사실상 정착된 것으로 보임.
- 논문 초안(연구배경/목적) 작성 시, "속어의 이중적 의미 판별(BIO/슬랭)" 프레이밍으로 쓰면 지금 실험(v2.2, 유희적 의도 전반)과 안 맞는다 — 이미 한 번 지적함, 재발 주의.
- PR #76(v2.1), #82(v2.2) 둘 다 **main에 아직 병합 안 됨.** 읽을 땐 `git show origin/pr/{76,82}:...`로.

---

## 5. 로드맵 (9/30 마감 기준, 9/21 시점)

| 날짜 | 할 일 |
|---|---|
| 9/21~22 | 4개 워크북 채점 완료 (최소 2인 독립) |
| 9/23 | 모델 A(End-to-end), 모델 B(발화기능 반영) 학습 |
| 9/24 | 결과 비교, `case_type`별 분리 보고 |
| 9/25~26 | 논문 초안(서론·방법·결과) |
| 9/27 | 한계·고찰 작성 + 지도교수님 첨삭 요청 |
| 9/28 | 첨삭 반영 |
| 9/29 | 팀 최종 검토 |
| 9/30 | 제출 |

채점(9/21~22)이 늦어지면 전체가 밀림 — 9/25~26 논문 작성 기간을 줄여서 흡수하고 9/27 첨삭 요청일은 사수 권장.
