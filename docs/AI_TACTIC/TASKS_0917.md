# Gemini 대화로 만드는 Pally 평가·학습 자료: 최소 파일 가이드

기준일: 2026-09-17  
기준: [Pally Rubric v2.1](https://github.com/Vivi827/capstone/blob/main/docs/AI_TACTIC/Pally_RUBRIC_v2.1_md).

## 1. 대화 상대는 Gemini로

현재 Pally 대신 Gemini와 자연스럽게 대화하며 수집할 수 있다. 상대 AI를 별도로 파인튜닝할 필요는 없다. 실제 사람이 자유롭게 반응한 발화여야 하며, Gemini가 사용자 역할까지 만들어 낸 가상 대화는 독립 인간 발화 자료와 구분해야 한다. 아래 예시도 설명을 위한 가상 자료이지 수집 완료된 데이터가 아니다.

사용자의 원음을 확보할 수 있어야 음성 표현성 평가가 가능하다. Gemini와 음성으로 대화했다는 사실만으로 원음 파일이 자동으로 연구 자료로 남는다고 가정하지 않는다. 사용하는 수집 방식에서 원음 보존이 가능한지 먼저 확인한다.

상대 AI 발화는 채점 대상이 아니라 맥락이다. 예를 들어 사용자 말이 “What did you do yesterday?”일 때 앞선 AI 말이 “Ask me what I did yesterday.”였다면 지시된 질문이고, “I had an interesting day yesterday.”였다면 자발적인 질문일 수 있다. 상대 말을 버리면 현재 rubric의 구분을 검증하기 어렵다.

Gemini 대화는 공손성·음성 표현성·질문·밈 사용 측정의 초기 자료로 쓸 수 있다. 다만 그 결과만으로 실제 Pally에서의 질문 기회·말투 분포·제품 효과까지 입증하지는 않는다. 관계 친숙도를 위한 **Pally 사용 이력**도 Gemini와 한 번 대화한 자료로 대체할 수 없다.

## 2. 최소 식별 정보와 시간

| 정보 | 최소 보존 이유 | 모델의 스타일 입력으로 넣는가? |
|---|---|---|
| `user_id` | 같은 사람의 여러 대화를 연결하고 화자 분리 평가에 사용. `u001` 같은 가명으로 충분 | 보통 아니오 |
| `session_id` | 같은 대화가 train과 final에 나뉘지 않게 관리 | 아니오 |
| `turn_id` | 원음·STT·확인 전사·평가자의 점수를 같은 발화에 연결 | 아니오 |
| `turn_index` | 대화 순서를 복원하고 앞선 맥락을 선택 | 순서 복원에 사용하며 ID 값 자체는 스타일 특징이 아님 |
| 실제 날짜·시각 | 사용 주기·비활성 시간에 따른 관계 친숙도 계산 | 관계 상태 계산에 사용. 나머지 네 항목의 첫 파일럿에는 정확한 시각이 필수가 아님 |
| 음성 시작·끝 위치 | 세션 전체 녹음에서 특정 사용자 발화를 찾아 듣기 | 음성 구간 추출에 사용. 발화별 파일로 나눴다면 별도 구간 시각을 생략 가능 |

## 3. 추천 폴더와 파일

```text
pally_dataset/
  README.md                 # rubric 버전, 수집 방식, AI 설정 설명
  conversations.jsonl       # 대화 원본과 사용자 음성·전사 연결
  annotations.csv           # 사람별 독립 평가 원점수
  splits.csv                # 대화/화자 그룹의 train·dev·final 배정
  audio/                    # 실제 사용자 음성 파일
  activity.csv              # 관계 친숙도 검증 단계에서만 추가
```

처음에는 `conversations.jsonl`과 `annotations.csv`, 실제 `audio/` 파일부터 준비한다. `splits.csv`의 역할 배정은 학습 시작 전에 완료하고, final은 개발 중 열람하지 않는다. JSONL은 한 줄에 하나의 JSON 객체를 쓰는 텍스트 형식이다.

### conversations.jsonl: 한 줄이 한 턴

다음은 설명용 가상 예시다. 표기된 음성 파일은 실제로 존재한다고 가정한 경로다. 실제 수집 시 파일과 경로가 일치해야 한다.

```jsonl
{"user_id":"u001","session_id":"s001","turn_id":"s001_t01","turn_index":1,"role":"assistant","text":"Tell me about your weekend.","audio_path":null,"stt_text":null,"verified_text":null}
{"user_id":"u001","session_id":"s001","turn_id":"s001_t02","turn_index":2,"role":"user","text":null,"audio_path":"audio/s001_t02.wav","stt_text":"i watched a movie","verified_text":"I watched a movie."}
{"user_id":"u001","session_id":"s001","turn_id":"s001_t03","turn_index":3,"role":"assistant","text":"What kind of movies do you like?","audio_path":null,"stt_text":null,"verified_text":null}
{"user_id":"u001","session_id":"s001","turn_id":"s001_t04","turn_index":4,"role":"user","text":null,"audio_path":"audio/s001_t04.wav","stt_text":"comedies what about you","verified_text":"Comedies. What about you?"}
```

- `text`: AI가 실제로 사용자에게 제시한 말. 사용자 원문은 STT와 확인 전사를 분리해 보존한다.
- `stt_text`: 원본 STT 출력. 사람이 나중에 고쳐 덮어쓰지 않는다.
- `verified_text`: 원음을 듣고 확인한 실제 발화. 문법이나 어휘를 더 좋은 영어로 바꾸지 않는다.
- `audio_path`: 사용자 원음의 경로. 원음이 없으면 `null`이며 음성 표현성 채점도 보류한다.
- 수집 조건과 Gemini 모델·프롬프트는 README에 기록한다. 조건이 바뀌면 세션별 수집 조건 표를 추가한다.

이 구조는 수집·보존용 제안이다. 현재 저장소의 ML loader에 그대로 넣으면 학습되는 형식은 아니므로 학습용 변환 과정이 필요하다.

### annotations.csv: 한 줄이 한 평가자의 한 항목 평가

아래는 빈 채점 틀이다. 점수와 유형은 독립 평가자가 입력한다. A와 B는 실제로 다른 평가자여야 한다.

```csv
turn_id,annotator_id,criterion,score,category,input_view,rubric_version,note
s001_t04,A,politeness,,,verified_text_with_past_context,v2.1,
s001_t04,B,politeness,,,verified_text_with_past_context,v2.1,
s001_t04,A,vocal_expressiveness,,,audio_with_past_context,v2.1,
s001_t04,B,vocal_expressiveness,,,audio_with_past_context,v2.1,
s001_t04,A,question_event,,,verified_text_with_past_context,v2.1,
s001_t04,B,question_event,,,verified_text_with_past_context,v2.1,
s001_t04,A,meme_usage_event,,,verified_text_with_past_context,v2.1,
s001_t04,B,meme_usage_event,,,verified_text_with_past_context,v2.1,
```

`score`는 공손성·음성 표현성처럼 연속 점수를 매기는 항목에 쓴다. `category`는 질문 유형이나 밈 사용 유형 등 사건 분류에 쓴다. 허용 유형은 rubric의 적용 규칙으로 고정한다. 질문과 밈의 0~100 관찰 기간 점수는 사건을 집계한 다음 계산하며 한 발화에 임의로 붙이지 않는다. 같은 발화에 여러 사건이 있다면 세부 구간과 사건별 ID를 추가하는 형태로 확장한다.

`input_view`는 평가자가 무엇을 보거나 들었는지 기록한다. 사람 확인 전사로 채점한 target과 STT 입력 모델의 결과를 비교하면 전사 오류가 포함된 서비스 조건을 평가할 수 있다. 원음을 들어야 알 수 있는 표현성 라벨을 텍스트만으로 충분히 예측할 수 있다고 가정하지 않는다.

### splits.csv: 묶음 단위의 역할 배정

```csv
session_id,split_group_id,split
s001,g001,dev
```

예시의 s001은 dev이므로 학습용 target이나 untouched final에 다시 포함하지 않는다. 같은 원음의 STT 전사와 사람 전사도 동일 split에 둔다. 새 화자 일반화를 평가한다면 같은 사용자의 다른 세션까지 같은 그룹에 둔다. 실제 배정은 참여자·세션 재고를 보고 고정한다.

### activity.csv: 관계 친숙도용으로 별도 수집

```csv
user_id,session_id,started_at,ended_at,valid_user_turns
```

같은 사용자·세션에 대한 유효 활동과 시각을 기록한다. 접속만 한 것과 실제 대화를 구분한다. 이것은 발화 점수 예측 모델의 학습표가 아니라 관계 상태 계산기의 입력이다. 날짜가 없으면 비활성 기간에 따른 감소를 계산할 수 없다.

## 4. 실제 학습용으로 바뀌는 과정

```text
대화 원본 + 사람별 독립 평가
  → 원점수 일치도 확인·불일치 처리
  → split별로 분리
  → 항목별 입력과 target을 추출
  → 선택한 학습 방식에 맞게 변환
```

| 측정 대상 | 학습/검증 입력 | target 또는 계산 결과 |
|---|---|---|
| 공손성 | 현재 텍스트 + 앞선 대화 | 인간 공손성 점수 |
| 음성 표현성 | 사용자 원음 + 정한 맥락 조건 | 인간 청취 점수 |
| 질문 사건 | 현재 텍스트 + 앞선 대화 | 질문 여부·유형·과제 지시 여부 |
| 밈 사용 사건 | 현재 텍스트 + 앞선 대화 + 검수 목록 | 사용/뜻 질문/인용 등의 유형 |
| 관계 친숙도 | 사용자 활동 이력 + 경과시간 | 버전 있는 계산식의 상태값; 초기에는 ML 학습 불필요 |

JSONL로 저장하는 것만으로 AI가 자동 학습하지 않는다. 학습 프로그램이 위 입력과 target을 읽도록 연결해야 한다. Gemini가 rubric에 따라 판별하도록 프롬프트를 주는 방식은 파인튜닝과 다르며, 첫 단계에서는 별도 모델 학습 없이 인간 dev와의 비교부터 할 수 있다. 처음 만든 약 100개를 dev anchor로 사용한다면, 그 자료를 그대로 학습에 넣고 같은 자료의 점수로 성능을 입증하지 않는다.
