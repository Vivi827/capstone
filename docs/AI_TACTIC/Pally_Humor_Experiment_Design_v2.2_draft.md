# Pally v2.2 Humor 경계 사례 학습 실험설계서 초안

작성일: 2026-09-20  
연구 단계: 교수 검토 전 초안  
측정 기준: [Pally 측정 Rubric v2.2](Pally_RUBRIC_v2.2_md)  
주 평가축: **Humor**  
보조 평가축: **Formality, Curiosity**  
미측정축: **Energy, Intimacy (`null`)**

## 1. 연구 배경과 문제

Pally는 사용자 발화를 Formality, Energy, Intimacy, Humor, Curiosity의 다섯 축으로 분석해 이후 캐릭터와 대화 적응에 활용하려 한다. 그러나 기존 AI·rule 기반 라벨이 인간의 스타일 지각을 학습했다는 근거는 충분하지 않다. 특히 문법 오류, 비표준 표현, 밈·슬랭, 아이러니처럼 복수 해석이 가능한 발화에서는 표면 단어만으로 Humor를 판단하기 어렵다.

본 연구에서는 v1.0을 비교 대상으로 사용하지 않는다. v2.2의 단일 발화 정의와 가중치를 고정한 뒤, **독립 인간 평가로 확인한 Humor 경계 사례를 추가하는 것이 같은 v2.2 모델의 인간 판단 일치도를 개선하는지** 탐색한다.

이 연구는 다음을 주장하지 않는다.

- 사용자의 성격이나 장기적인 유머 성향을 측정했다는 주장
- 새로운 범용 Humor 모델을 확립했다는 주장
- 50개 표본으로 제품 배포 성능을 확증했다는 주장
- 높은 Humor가 더 좋은 대화 스타일이라는 주장
- `human_spoken=true`가 인간 정답 라벨을 뜻한다는 주장

## 2. 연구 목적

1. 단일 발화 기반 v2.2 Humor rubric의 인간 평가자 간 일치도를 확인한다.
2. 명확한 사례와 의미적 경계 사례에서 모델의 오류가 어떻게 달라지는지 확인한다.
3. 인간이 판정한 경계 사례를 추가한 v2.2 모델이 경계 사례를 추가하지 않은 v2.2 Base 모델보다 인간 Humor 점수에 가까워지는지 평가한다.
4. 문법 오류와 의도적 비표준 표현, 문자적 의미와 슬랭 의미, 진술과 아이러니 사이에서 나타나는 오류 유형을 정리한다.

## 3. 연구 질문과 가설

### 주 연구 질문

**RQ1.** 독립 인간 평가로 확인한 Humor 경계 사례를 학습에 추가한 v2.2 Boundary-aware 모델은 v2.2 Base 모델보다 untouched final test에서 인간 Humor 점수와 높은 일치도를 보이는가?

### 보조 연구 질문

**RQ2.** 두 모델의 차이는 `clear` 사례와 `boundary` 사례에서 다르게 나타나는가?

**RQ3.** 문법 오류·의도적 비표준 표현, 문자적 의미·슬랭 의미, 진심·아이러니의 구분은 인간 평가자 간 불일치와 모델 오류에 어떤 영향을 미치는가?

**RQ4.** v2.2의 10개 발화 기능과 `language_form` 분류는 Humor 오류를 설명하는 진단 정보로 유용한가?

### 사전 가설

- **H1:** Boundary-aware 모델의 final Humor MAE가 Base 모델보다 낮을 것이다.
- **H2:** 개선 폭은 `clear`보다 `boundary` 사례에서 더 클 것이다.
- **H3:** `intent_unclear`와 `context_insufficient` 사례에서는 인간 간 차이와 모델 오차가 모두 커질 것이다.

결과가 가설과 다르거나 차이가 없어도 그대로 보고한다.

## 4. 연구 설계 개요

```text
Pally Rubric v2.2 고정
        ↓
독립 인간 4인 평가
        ↓
발화 기능·language_form·3축 점수·경계 상태 기록
        ↓
Train/Dev에서만 모델 구성
        ↓
┌──────────────────────┬─────────────────────────┐
│ v2.2 Base            │ v2.2 Boundary-aware     │
│ 명확 사례 중심 학습  │ 동일 학습 + 경계 사례   │
└──────────────────────┴─────────────────────────┘
        ↓ 동일한 untouched final test
전체 / clear / boundary / context-insufficient 결과 분리
```

## 5. 비교 조건

### 5.1 공통 조건

두 모델에서 다음을 동일하게 유지한다.

- 모델 구조와 기반 모델 버전
- 텍스트 전처리
- 입력: 현재 사용자 발화 한 문장
- 출력: 주 발화 기능, `language_form`, Formality·Humor·Curiosity 점수, 축별 `case_type`
- v2.2 구성요소 정의와 가중치
- 학습 반복 수, random seed, 정규화, 기타 hyperparameter
- dev 선택 절차와 final 평가 코드

### 5.2 v2.2 Base

- `clear`이며 `score_status=final`인 독립 인간 라벨을 학습한다.
- `boundary` Humor 점수 라벨은 학습하지 않는다.
- `context_insufficient`의 잠정 점수는 학습하지 않는다.

### 5.3 v2.2 Boundary-aware

- Base와 동일한 `clear` 학습 자료를 사용한다.
- 여기에 `boundary`이며 `score_status=final`인 인간 Humor 라벨을 추가한다.
- `context_insufficient`는 Humor 회귀 target으로 쓰지 않고 `case_type` 분류에만 사용한다.

이 비교는 **경계 사례 라벨을 추가하는 통합 효과**를 평가한다. Boundary-aware 조건의 학습 행 수가 더 많으므로, 결과를 “경계 사례라는 유형만의 순수 인과 효과”로 표현하지 않는다. 가능하면 같은 수의 추가 `clear` 사례를 넣은 matched-size 보조 조건을 만들 수 있지만, 필수 조건은 아니다.

### 5.4 Gemini를 사용하는 경우

Gemini에 rubric과 예시를 프롬프트로 제공하는 것은 parameter fine-tuning이 아니다. 이 경우 조건명을 다음처럼 기록한다.

- `v2.2_rubric_only`: v2.2 정의·가중치만 제공
- `v2.2_boundary_fewshot`: 동일한 지침에 train/dev 경계 예시를 추가

동일 Gemini model ID, temperature, 출력 형식, 호출 횟수를 유지한다. 이 결과는 **rubric/few-shot adaptation**으로 보고하며 “Gemini를 새 corpus로 학습했다”고 표현하지 않는다.

## 6. 자료 구성과 split

### 6.1 권장 구성

| 자료 | 권장 수 | 역할 | final 성능에 사용 |
|---|---:|---|---|
| 기존 `remainder50` | 50 | v2.2 3축 인간 라벨 확보, Base/Boundary-aware 학습 후보 | 아니오 |
| 신규 Humor 중심 자료 | 10 | dev: rubric 적용 점검·모델 선택·오류 코드 확정 | 아니오 |
| 신규 Humor 중심 자료 | 40 | untouched final test | 예 |

`remainder50`은 원래 Energy·Curiosity·Intimacy 검토 후보로 추출된 자료이므로 Humor 경계 사례를 충분히 포함한다고 가정하지 않는다. 인간 라벨링 후 유효한 `boundary` 사례가 너무 적으면, 부족한 유형의 **별도 train 전용 자료**를 추가한다. final 40개를 학습 자료로 이동하지 않는다.

### 6.2 신규 Humor 50개 후보 구성

후보 선정 단계에서는 다음 층을 의도적으로 포함하되, 최종 `case_type`은 인간 평가 결과로 정한다.

| 후보 층 | dev 10 권장 | final 40 권장 | 예시 |
|---|---:|---:|---|
| 명확한 비유머·문자적 발화 | 2 | 10 | 일반 사실·경험·요청 |
| 명확한 유희적 발화 | 2 | 10 | 말장난·과장·명확한 유희 프레이밍 |
| 문자 의미와 슬랭 의미의 경계 | 2 | 8 | `ate`, `dead`, `sick` 등의 의미 충돌 |
| 진심과 아이러니·비꼼의 경계 | 2 | 6 | “Well, that went great.” |
| 문법 오류와 의도적 변형의 경계 | 1 | 4 | 학습자 오류와 밈 문형의 구분 |
| 단일 발화로 문맥이 부족한 사례 | 1 | 2 | “Sure, genius.” / “Really?” |

이 숫자는 **후보 구성 목표**다. 평가자에게 분포를 알려주지 않으며, 인간 정답을 이 비율에 맞추지 않는다.

### 6.3 누출 방지 단위

다음 중 하나라도 공유하면 같은 `split_group_id`에 둔다.

- 같은 원 대화·세션
- 같은 화자·학습자
- 인접 턴
- 동일 음성의 STT 전사와 사람 전사
- 동일 문장을 구두점·대소문자·철자만 바꾼 변형
- 동일 템플릿을 단어만 교체한 변형
- 같은 밈·슬랭 표현을 같은 의미 대조 방식으로 만든 lexical family

같은 `split_group_id`는 train/dev/final을 넘지 않는다. final은 rubric과 모델을 동결한 뒤 한 번만 연다.

## 7. 인간 평가 절차

### 7.1 평가자와 평가량

- 평가자: 4명
- 방식: 전 항목 독립 평가
- 50개 신규 자료라면 총 200개의 평가자×문장 판정
- 반복 판정 수는 독립 문장 수로 계산하지 않는다.

평가자가 팀원인 경우 연구자와 평가자가 동일 집단이라는 한계를 기록한다. 새로운 인간 참여 연구의 심의·면제 여부는 소속기관 기준을 확인하며, 이 문서만으로 IRB 불필요를 선언하지 않는다.

### 7.2 블라인드 조건

평가자는 다음을 보지 않는다.

- 모델 출력과 기존 AI 점수
- 다른 평가자의 점수·근거
- corpus 이름과 기존 라벨
- train/dev/final 구분
- 후보 층의 목표 분포

평가자마다 문장 순서를 다르게 무작위화한다.

### 7.3 문장별 평가 순서

1. `primary_function` 10개 중 하나 선택
2. 필요하면 `secondary_function` 선택
3. `function_ambiguous` 선택
4. `language_form` 5개 중 하나 선택
5. Formality 구성요소 3개를 각각 0–4로 평가
6. Humor 구성요소 4개를 각각 0–4로 평가
7. Curiosity 구성요소 4개를 각각 0–4로 평가
8. 수식으로 세 축 0–100 점수 자동 계산
9. 각 축의 `case_type`, `score_status`, confidence 1–5, 짧은 근거 기록

평가자가 최종 점수를 임의로 다시 수정하지 않는다. 수식 결과가 부적절하다고 느끼면 점수를 덮어쓰지 않고 `rubric_issue`와 이유를 기록한다. 이는 가중치 문제를 사후에 숨기지 않고 진단하기 위함이다.

### 7.4 독립 원점수와 참조값

- 평가자별 구성요소와 계산 점수를 모두 보존한다.
- Humor 연속 참조값은 네 평가자의 **개별 계산 점수 중앙값**으로 정한다.
- 범주형 필드는 3명 이상이 같은 값을 선택하면 다수 참조값으로 사용한다.
- 2:2 동률은 `unresolved`로 남기고 임의로 결정하지 않는다.
- 토론이나 조정 전 원점수로 평가자 간 일치도를 계산한다.
- 조정을 실시하면 원래 값과 조정 값을 모두 저장하고, 조정 후 일치도를 독립 일치도로 보고하지 않는다.

## 8. 모델 출력과 점수 계산

모델은 가능한 한 다음 구조를 출력한다.

```json
{
  "primary_function": "opinion_evaluate",
  "language_form": "playful_deviation",
  "components": {
    "Formality": {"respect_face": 2, "mitigation": 2, "spoken_register": 1},
    "Humor": {
      "playful_framing": 3,
      "nonliteral_incongruity": 4,
      "humor_meme_slang_cue": 3,
      "expressive_reinforcement": 2
    },
    "Curiosity": {
      "inquiry_strength": 0,
      "exploration_depth": 0,
      "answer_openness": 0,
      "epistemic_signal": 0
    }
  },
  "case_type": {
    "Formality": "boundary",
    "Humor": "clear",
    "Curiosity": "clear"
  }
}
```

최종 점수는 모델이 자유롭게 작성한 숫자가 아니라 v2.2 수식으로 평가 코드가 계산한다. 출력 형식 실패, 범위 밖 수준, 누락 필드는 별도 오류로 기록한다.

인간이 선택한 발화 기능을 모델에 입력하는 경우는 `oracle-function` 조건이다. 실제 end-to-end 성능과 섞지 않는다.

## 9. 평가 지표

### 9.1 인간 평가 신뢰도

| 대상 | 지표 | 해석 |
|---|---|---|
| Humor 0–100 | ICC(2,k) | 네 평가자의 평균 평정 신뢰도 |
| Humor 순위 | 평가자 쌍별 Spearman 및 중앙값 | 문장 순서의 일관성 |
| Humor 점수 차이 | 평가자 쌍별 MAE | 실제 점수 차이의 크기 |
| 발화 기능·`language_form`·`case_type` | Krippendorff’s α | 3개 이상 명목 범주의 일치도 |
| 완전 일치 | exact agreement | 네 명이 같은 범주를 고른 비율 |

ICC·α가 낮으면 합의 정답을 억지로 확정하기보다 어떤 유형에서 불일치가 발생했는지 분석한다. 비정상적으로 높은 exact agreement가 나타나면 평가 독립성과 채점 경로를 확인할 때까지 해당 결과를 보류하며, 특정 평가자의 부정행위를 단정하지 않는다.

### 9.2 모델의 주 지표

**주 지표:** untouched final에서 인간 Humor 참조값에 대한 MAE

```text
MAE = mean(|model_humor − human_humor_reference|)
주 효과 = MAE(Base) − MAE(Boundary-aware)
```

양수이면 Boundary-aware 모델의 오차가 더 작다.

### 9.3 보조 지표

- Humor Spearman 상관
- ±10점 이내 일치율
- `case_type` macro-F1 및 confusion matrix
- 발화 기능 accuracy와 macro-F1
- `clear`, `boundary`, `context_insufficient`별 Humor MAE
- `language_form`별 Humor MAE
- Formality·Curiosity MAE와 Spearman: 보조 결과로만 보고
- 모델 출력 형식 실패율

`context_insufficient`의 잠정 Humor 점수는 주 MAE에서 제외하고 별도 민감도 분석으로 보고한다. `boundary`이며 `score_status=final`인 사례는 주 MAE에 포함한다.

### 9.4 불확실성 보고

- 두 모델은 같은 final 문장에 적용하므로 문장 단위 대응 차이를 사용한다.
- 95% paired bootstrap confidence interval을 보고한다.
- 같은 lexical family나 템플릿 변형이 있으면 `split_group_id` 단위로 재표집한다.
- final 40개는 작은 탐색 표본이므로 p-value만으로 결론을 내리지 않고 효과 크기, 구간, 개별 오류를 함께 제시한다.

## 10. 오류 분석 코드

모델 결과를 보기 전에 다음 오류 코드를 고정한다.

| 코드 | 오류 유형 |
|---|---|
| `E1_LITERAL_SLANG` | 문자적 의미와 슬랭 의미 혼동 |
| `E2_SARCASM` | 진심 표현과 아이러니·비꼼 혼동 |
| `E3_GRAMMAR_INTENT` | 학습자 오류와 의도적 비표준 표현 혼동 |
| `E4_KEYWORD_SHORTCUT` | 밈·슬랭 단어 존재만으로 Humor를 높게 판단 |
| `E5_PUNCTUATION_SHORTCUT` | 느낌표·대문자·웃음 표기에 과도하게 의존 |
| `E6_FUNCTION_CONFUSION` | 발화 기능을 잘못 분류해 Humor 해석이 달라짐 |
| `E7_CONTEXT_MISSING` | 단일 발화로 부족한데 확정적으로 판단 |
| `E8_RUBRIC_GAP` | 기존 rubric만으로 우세한 판단을 만들기 어려움 |
| `E9_OUTPUT_FAILURE` | 형식 오류·필드 누락·범위 밖 출력 |

한 사례에 복수 코드를 허용한다. 오류 코드는 모델 내부 사고를 직접 관찰한 설명이 아니라 출력 행동에 대한 분석이다.

## 11. 분석 절차

1. 평가자 원점수와 누락·범위 오류를 확인한다.
2. 인간 일치도를 토론 전 점수로 계산한다.
3. final을 열기 전에 rubric, 두 모델, 지표, 오류 코드를 동결한다.
4. 두 모델을 동일한 final 40개에 실행한다.
5. 전체 final의 Humor MAE와 Spearman을 비교한다.
6. `clear`와 `boundary`를 분리해 RQ2를 분석한다.
7. `language_form`과 오류 코드별 결과를 정리한다.
8. Formality와 Curiosity는 보조 결과로 별도 표에 제시한다.
9. final 오답을 보고 수정한 모델은 본 실험의 독립 결과로 다시 보고하지 않는다.

## 12. 결과표 틀

### 표 1. 인간 평가 일치도

| 축·범주 | ICC/α | Spearman | MAE | exact agreement | N |
|---|---:|---:|---:|---:|---:|
| Humor 전체 |  |  |  |  |  |
| Humor clear |  |  |  |  |  |
| Humor boundary |  |  |  |  |  |
| 발화 기능 |  | 해당 없음 | 해당 없음 |  |  |
| language_form |  | 해당 없음 | 해당 없음 |  |  |

### 표 2. 모델 비교

| 조건 | 전체 Humor MAE | clear MAE | boundary MAE | Spearman | ±10 일치율 |
|---|---:|---:|---:|---:|---:|
| v2.2 Base |  |  |  |  |  |
| v2.2 Boundary-aware |  |  |  |  |  |
| 차이 |  |  |  |  |  |

### 표 3. 오류 유형

| 오류 코드 | Base 건수 | Boundary-aware 건수 | 대표 사례 ID |
|---|---:|---:|---|
| E1_LITERAL_SLANG |  |  |  |
| E2_SARCASM |  |  |  |
| E3_GRAMMAR_INTENT |  |  |  |
| E4_KEYWORD_SHORTCUT |  |  |  |
| E5_PUNCTUATION_SHORTCUT |  |  |  |
| E6_FUNCTION_CONFUSION |  |  |  |
| E7_CONTEXT_MISSING |  |  |  |
| E8_RUBRIC_GAP |  |  |  |
| E9_OUTPUT_FAILURE |  |  |  |

## 13. 필요한 파일

```text
experiment_v2_2/
  README.md
  items.jsonl                 # 원문·provenance·split_group_id
  splits.csv                  # train/dev/final 배정
  annotations_raw.csv         # 평가자별 독립 원점수
  human_reference.csv         # 사전 규칙으로 계산한 참조값
  model_base_outputs.jsonl    # Base 원출력
  model_boundary_outputs.jsonl
  metrics.json
  error_analysis.csv
  rubric_snapshot/            # 실험에 사용한 v2.2 사본·해시
```

필수 provenance 필드:

```text
item_id, source, source_record_id, conversation_id, session_id,
speaker_id, turn_id, split_group_id, human_spoken, input_scope,
rubric_version, label_source, split
```

`human_spoken=true`는 인간이 말한 입력이라는 뜻이며 `label_source=independent_human`을 보장하지 않는다.

## 14. 실행 일정 예시

### 1일차

- 교수 검토 후 RQ·비교 조건·v2.2 고정
- 기존 remainder50과 신규 Humor50의 provenance 확인
- `split_group_id` 기준으로 dev 10/final 40 고정
- 평가 시트 생성 및 3–5개 연습 문장으로 절차 점검

### 2일차

- 평가자 4명 독립 평가
- 누락·범위 오류만 확인하고 점수 내용은 상호 공개하지 않음
- 독립 원점수 일치도 계산
- train/dev에서 Base와 Boundary-aware 구성

### 3일차

- 모델·rubric·평가 코드 동결
- untouched final 실행
- 주·보조 지표와 오류 분석
- 결과표, 한계, 논문 Methods/Results 초안 작성

평가가 끝나지 않거나 final 독립성을 확보하지 못하면 일정을 맞추기 위해 final을 재사용하지 않고, pilot 결과로 범위를 낮춰 보고한다.

## 15. 예상 contribution

1. 단일 발화 Humor를 구성요소 가중치와 경계 상태로 분리한 v2.2 operational rubric을 제시한다.
2. 학습자 문법 오류와 의도적 비표준 표현을 분리하는 주석 절차를 제시한다.
3. 연속 Humor 점수와 `clear/boundary/context_insufficient`를 함께 기록하는 인간 평가 스키마를 제시한다.
4. 경계 사례 인간 라벨 추가 전후의 모델–인간 일치도를 동일 final test에서 비교한다.
5. 문자·슬랭, 진심·아이러니, 오류·유희적 변형이 만드는 모델 실패 유형을 정리한다.

이 contribution은 제한된 영어 단일 발화와 소규모 탐색 실험 범위에 한정한다. “최초”, “범용”, “인간 수준”이라는 표현은 사용하지 않는다.

## 16. 주요 한계

- 50개 final 후보와 4명의 평가자는 작은 탐색 연구 규모다.
- 단일 발화 조건이 실제 대화의 Humor 맥락을 제거한다.
- 연구팀이 자료를 작성하거나 선정하면 자연 발화 분포를 대표하지 않을 수 있다.
- Boundary-aware 조건은 학습 자료 수 자체가 증가하므로 경계 유형의 순수 효과와 분리되지 않는다.
- 밈·슬랭의 의미는 시기·지역·집단에 따라 달라질 수 있다.
- v2.2 가중치는 본 실험의 operational proposal이며 외부 타당성이 아직 확인되지 않았다.
- Formality와 Curiosity 결과는 보조 분석이며 본 연구가 두 축의 타당성을 확증하지 않는다.

## 17. 교수님 검토 요청 사항

1. RQ1을 “경계 사례 인간 라벨 추가 효과”로 두는 것이 적절한가?
2. `remainder50`을 train 후보, 신규 Humor50을 dev 10/final 40으로 두는 split이 적절한가?
3. 4명 전 항목 독립 평가와 중앙값 참조값 생성이 가능한가?
4. `context_insufficient`의 잠정 점수를 주 MAE에서 제외하고 별도 분석하는 것이 적절한가?
5. Base와 Boundary-aware의 학습 행 수 차이를 허용할지, matched-size clear 조건을 추가할지 결정이 필요한가?
6. 합성·선정 자료를 사용할 경우 허용 가능한 논문의 주장 범위는 어디까지인가?
7. 소속기관 기준상 평가자 참여와 자료 수집에 필요한 연구윤리 절차는 무엇인가?

## 18. 실행 전 확정해야 할 항목

- 실제 분석기 종류: Ridge 등 trainable analyzer / Gemini rubric prompting
- Base와 Boundary-aware에 사용할 정확한 학습 행 ID
- 신규 Humor50의 출처와 저작권·재배포 가능 범위
- 모델 버전·seed·temperature·반복 횟수
- human reference 생성 코드와 동률 처리
- final 데이터 보관 담당자와 열람 시점
- professor-approved RQ와 논문에서 사용할 용어

위 항목이 확정되기 전에는 final 결과를 열람하지 않는다.

## 참고문헌

- Röttger et al. (2022). [Two Contrasting Data Annotation Paradigms for Subjective NLP Tasks](https://aclanthology.org/2022.naacl-main.13/). NAACL.
- Ribeiro et al. (2020). [Beyond Accuracy: Behavioral Testing of NLP Models with CheckList](https://aclanthology.org/2020.acl-main.442/). ACL.
- Pei, Sun, & Xu (2019). [Slang Detection and Identification](https://aclanthology.org/K19-1082/). CoNLL.
- Sun, Zemel, & Xu (2022). [Semantically Informed Slang Interpretation](https://aclanthology.org/2022.naacl-main.383/). NAACL.
- Sun et al. (2024). [Toward Informal Language Processing: Knowledge of Slang in Large Language Models](https://aclanthology.org/2024.naacl-long.94/). NAACL.
- Klie et al. (2024). [On Efficient and Statistical Quality Estimation for Data Annotation](https://aclanthology.org/2024.acl-long.837/). ACL.
