# Pally 현재 데이터 필드 해설표

기준일: 2026-09-17  
확인 범위: [`puter8/capstone`](https://github.com/puter8/capstone) 커밋 `1d2f93e2ef8fa14df18888792e872df0a378dd3b`의 데이터 파일, ML loader, Supabase migration 및 주요 대화 저장 경로. **새 v2.1 권장 스키마가 아니라 현재 저장소에 실제로 있는 필드**를 설명한다. DB의 실제 운영 환경에 migration이 적용됐는지까지 접속해 검증한 것은 아니다.

## 먼저 구분할 네 종류

| 위치 | 무엇을 담는가 | 현재 모델과의 관계 |
|---|---|---|
| `sessions`·`messages` DB | Pally 서비스의 대화 이력과 분석 결과 | 서비스 대화·누적 점수 저장. 학습 데이터 파일과 별개다. |
| `data/axis_dataset_week2.jsonl` | 기본 ML loader가 우선 읽는 338행 파일 | 환경변수 `PALLY_AXIS_DATASET`이 없고 파일이 있으면 kNN 학습에 사용. 기본 서비스 분석기 자체는 여전히 `rule`이다. |
| `data/fixtures/axis_dataset_combined_real_speech_experimental.jsonl` | 실제 발화와 seed가 섞인 3,137행 실험 파일 | 별도로 지정해야 ML 실험에 사용. 인간 gold로 간주하지 않는다. |
| `data/fixtures/ml_transition_*.jsonl` | 기존 gold-200, calibration 후보, 예약 최종 pool 등 | 평가·검수·예약의 각기 다른 목적. 일반 학습 loader에 무심코 넣지 않는다. |

근거: [기본 데이터 loader](../work/capstone/ai/ml_baseline.py), [DB migration](../work/capstone/supabase/migrations/20260522000000_sessions_messages.sql), [기존 평가 계약](../work/capstone/docs/ml-transition-contract.md).

## A. 서비스 DB: `sessions` 필드

| 필드 | 뜻 | 현재 사용/주의 |
|---|---|---|
| `id` | 대화 세션의 고유 UUID | `messages.session_id`가 참조한다. 연구 데이터의 `conversation_id`와 자동으로 같은 것은 아니다. |
| `user_id` | 세션 소유 사용자 UUID | 계정과 세션 연결. 같은 사용자의 여러 세션을 찾는 데 쓸 수 있지만 현재 5축 학습 라벨은 아니다. |
| `character_name` | 답변 프롬프트에 쓰는 캐릭터 이름 | 기본 `Pally`. 성향 수치 전체가 프롬프트에 전달된다는 뜻은 아니다. |
| `level` | 사용자 영어 수준 | 현재 허용값 `A2`, `B1`, `B2`, `C1`; Gemini 프롬프트에 사용. 말투/성격 점수와 분리해야 한다. |
| `created_at` | 세션 생성 시각 | 관계 친숙도 계산에 쓸 후보지만 단독으로 사용량을 뜻하지 않는다. |
| `ended_at` | 세션 종료 시각 | 활성/완료 표시. |
| `reopened_at` | 종료 후 다시 연 시각 | 대화 재개 이력. |
| `reopen_count` | 재개 횟수 | 사용 이벤트의 한 신호일 수 있으나 그대로 친숙도 점수는 아니다. |

## B. 서비스 DB: `messages` 필드

| 필드 | 뜻 | 현재 사용/주의 |
|---|---|---|
| `id` | 메시지 행의 고유 UUID | 한 턴은 보통 사용자 행과 Pally 응답 행 두 개로 저장된다. |
| `session_id` | 소속 세션 UUID | 대화 이력을 시간순으로 불러온다. |
| `role` | 발화 주체 | `user` 또는 `pally`. 학습자 발화와 AI 응답을 혼동하면 안 된다. |
| `transcript` | 발화/답변 텍스트 | 사용자 행은 STT 결과, Pally 행은 생성 답변일 수 있다. 원음이나 STT 신뢰도는 이 필드에 남지 않는다. |
| `axes` | 기존 Formality/Energy/Intimacy/Humor/Curiosity 5축 JSON | 사용자 행에 EMA 적용 결과 저장. Pally 응답 행은 보통 `null`. 인간이 채점한 정답이 아니다. |
| `character` | 5축에서 계산한 캐릭터 제어 수치 JSON | 저장·응답에는 포함되지만 주요 Gemini 답변 호출이나 TTS 호출의 제어 인자로 연결되지는 않았다. |
| `created_at` | 메시지 생성 시각 | 이전 대화 로드와 턴 순서에 사용. |
| `idempotency_key` | 중복 요청 방지 키 | 같은 요청 재시도 시 사용자 턴을 중복 저장하지 않기 위한 값. 사용자 행에만 기록. |
| `feedback` | 교정 결과 JSON 배열 | `null`은 피드백 실패/미완, `[]`는 생성은 됐으나 교정 없음. 5축 인간 라벨이 아니다. |

근거: [세션/메시지 생성](../work/capstone/supabase/migrations/20260522000000_sessions_messages.sql), [소유자 연결](../work/capstone/supabase/migrations/20260526000000_sessions_messages_rls.sql), [재개·피드백](../work/capstone/supabase/migrations/20260812200000_week4_history_feedback.sql), [중복 방지](../work/capstone/supabase/migrations/20260812100000_messages_idempotency.sql), [대화 저장 경로](../work/capstone/backend/main.py).

## C. 현재 ML 학습 loader가 실제로 읽는 필드

| 필드 | 데이터 안의 뜻 | 기본 kNN 학습에서 사용되는가? |
|---|---|---|
| `utterance` | 학습 입력인 사용자 발화 텍스트 | **예.** TF-IDF 단어 특징을 만든다. 앞뒤 턴·원음은 기본 모델 입력이 아니다. |
| `axes` | 기존 5축 점수 객체, 각 축 0~100 | **예.** 정답값으로 사용한다. 기본 배포 경로는 5축 모두 있어야 한다. |
| `style` | 발화 유형 문자열 | **읽어 보관하지만** 기본 kNN 예측 특징은 아니다. 11개 style 범주와 5축은 별개다. |
| `source` | 자료 출처 문자열 | **읽어 보관하지만** 기본 kNN의 입력 특징은 아니다. `gemini_assisted` 같은 출처명은 인간 라벨 품질 보증이 아니다. |
| `source_group` | 원본 대화·화자 등 분할 관련 출처 그룹 문자열 | **읽어 보관하지만** 기본 kNN의 입력 특징은 아니다. 빈 값/누락 가능, 그룹 분할 감사에 활용한다. |
| `label_source` | 축마다 라벨이 `human`, `ai_draft` 등 어디서 왔는지 | **부분 라벨 허용 실험 경로에서만 읽는다.** 기본 배포 loader는 이 필드로 라벨 품질을 자동 판별하지 않는다. |

`split`과 `notes`는 JSONL에 있어도 기본 ML loader의 `AxisTrainingExample`으로 옮겨지지 않는다. `PALLY_AXIS_DATASET` 환경변수로 다른 파일을 지정하면 그 파일을 읽고, 지정하지 않으면 `data/axis_dataset_week2.jsonl`을 읽는다. 해당 파일이 없을 때만 코드 속 seed 예시로 대체된다. 이 설명은 **ML을 선택했을 때의 데이터 경로**이고, 현재 서비스 기본 분석기는 `rule`이다. 근거: [ML loader](../work/capstone/ai/ml_baseline.py), [분석기 선택](../work/capstone/ai/analyzers.py).

## D. 3,137행 실험 JSONL의 공통 필드

표에서 “일부”는 해당 출처의 행에만 존재한다는 뜻이다. 이 파일은 여러 corpus의 원래 필드를 하나의 JSONL에 보존하므로 **모든 행의 열 구성이 같지 않다**.

| 필드 | 뜻 | 범위·주의 |
|---|---|---|
| `utterance` | 분석/라벨링 대상 발화 텍스트 | 모든 행. 실제 음성 파일 자체는 아니다. |
| `axes` | 기존 5축 점수 | 모든 행. seed·AI draft·수용된 draft가 섞여 있어 동일 등급의 human gold가 아니다. |
| `style` | 11개 대화 스타일 범주 중 하나인 발화 유형 | 모든 행. 5축과 다른 분류 체계. |
| `split` | 당시 파일 제작 시 붙인 `train`/`dev`/`test` 태그 | 모든 행. 새 v2.1의 그룹 분할이나 untouched final을 보장하지 않는다. |
| `notes` | 라벨/선정 과정의 설명 문자열 | 모든 행. 독립 인간 채점 근거와 동일한 것으로 보지 않는다. |
| `source` | 원 자료 또는 seed 제작 경로 | 모든 행. `nict_jle_real`, `ami_real`, `chime6_real`, `hcrc_maptask_real`, `taskmaster1_woz_user_real`, AI-assisted seed 등. |
| `label_status` | 라벨의 당시 처리 상태 | 일부 행. 이름만으로 독립성 판단 금지. NICT 600행의 `human_reviewed`는 기존 draft 값 수용 경로이며 독립 blind 재채점이 아니다. |
| `labeler` | 라벨 작성/수용 경로의 식별 문자열 | 일부 행. 실제 독립 검수자 ID로 해석하면 안 된다. |
| `sample_bucket` | 후보 발화의 선정 유형 | 외부 draft 행에 사용. 질문·요청·반응 등 표본 구성 확인용. |
| `source_line` | NICT 원본 파일의 행 위치 | NICT 행에 사용. 원본과 그룹을 복구할 때 중요하다. |
| `source_record_id` | 원본 데이터 내 레코드 식별자 | 해당 외부 corpus 행에 사용. |
| `source_group` | 출처별 원본 그룹 정보 | 일부 외부 corpus 행. 누락·형식 차이가 있으므로 전체 공통 `split_group_id`와 동일시하지 않는다. |

## E. corpus별로 추가 보존되는 필드

| corpus/용도 | 필드 | 뜻 |
|---|---|---|
| NICT | `source_line` | 원본 행 위치. 이 통합 실험 파일의 NICT 행에는 화자·세션·앞뒤 턴 필드가 직접 들어 있지 않아 원본 대조가 필요하다. |
| CHiME-6 | `raw_split`, `session_id`, `speaker`, `location`, `start_time`, `end_time`, `reference`, `annotation_events` | 원 자료의 분할·세션·화자·위치·시간·참조·주석 사건. 구간 정보가 있어도 이 실험 JSONL에 음성 파일이 내장된 것은 아니다. |
| HCRC Map Task | `dialogue_id`, `participant_role`, `utterance_id`, `move_label`, `start_time`, `end_time` | 대화·참가자 역할·발화·대화행위·시간 정보. `move_label`은 Pally의 질문 참여 점수가 아니다. |
| Taskmaster-1 | `conversation_id`, `instruction_id`, `dialogue_turn_index` | 대화·태스크 지시·턴 순서. 새 질문 축에서는 지시된 질문을 자발적 질문과 분리할 때 필요하다. |
| AMI | `meeting_id`, `speaker`, `speaker_id`, `speaker_native_language`, `speaker_role`, `dialogue_act`, `dialogue_act_gloss`, `start_time`, `end_time`, `annotation_events` | 회의·화자·역할·대화행위·시간·원본 주석 메타데이터. `dialogue_act`는 새로운 Pally 5항목의 인간 정답이 아니다. |

출처별 필드 해석과 현재 샘플링 과정은 [실제 발화 corpus 기록](../work/capstone/docs/real-speech-corpus-benchmark.md) 및 [실험 파일](../work/capstone/data/fixtures/axis_dataset_combined_real_speech_experimental.jsonl)에 근거한다.

## F. 기존 인간 dev·검수 후보·예약 자료에 추가된 필드

| 필드 | 주로 나타나는 곳 | 뜻과 주의 |
|---|---|---|
| `reviewer_id` | gold-200 | 검수자 식별자. 이 값만으로 모든 행이 같은 독립 채점 절차를 거쳤다고 단정하지 않는다. |
| `review_set` | gold-200 | 기존 검수 자료의 묶음. |
| `review_axes` | gold-200, calibration 후보 | 검토 대상 축 목록. 실제 점수가 완성됐다는 뜻은 아니다. |
| `focus_bucket` | gold-200, 후보 | 선택·층화에 사용한 관심 사례 유형. 평가자에게 blind로 숨겨야 할 수 있다. |
| `source_record_id`, `source_group` | gold-200, 후보, 예약 | 원본 레코드/그룹 추적. 새 `split_group_id` 생성 때 검증 필요. |
| `conversation_id`, `turn_index`, `speaker` | calibration 후보, 예약 | 원본 대화·턴·화자 추적. |
| `previous_turn`, `previous_turn_speaker`, `next_turn`, `next_turn_speaker` | calibration 후보, 예약 | 대상 발화의 앞뒤 맥락. 현재 기본 ML 모델이 자동으로 읽지는 않는다. |
| `review_partition` | calibration 후보, 예약 | 후보 선정 과정의 분할 태그. 실제 모델 개발 역할과 구별한다. |
| `annotation_batch` | calibration 후보 | 예: `calibration`. 검수 배치 이름. |
| `dataset_partition` | calibration 후보 | 예: `dev`. 이 자료를 개발·기준 조정에 쓰려는 역할. |
| `word_count`, `filler_ratio` | calibration 후보, 예약 | 발화 길이와 머뭇거림 비율. 품질·선정 조건이지 Pally 스타일 정답은 아니다. |
| `source_file`, `instruction_id`, `dialogue_turn_index` | 일부 후보/예약 | 원본 파일·지시·대화 턴 위치. |
| `canonical_group` | 예약 자료 | 정규화한 보호/비교 그룹 식별자. 원본 그룹 복구 결과를 확인해야 한다. |
| `train_overlap`, `dev_overlap`, `provenance_verified`, `exposure_status` | 예약 자료 | 기존 학습·dev 노출과 원본 확인 상태를 기록한 감사 플래그. |
| `reservation_role`, `reference_only`, `reservation_seed` | 예약 자료 | legacy `final_gate`/재현 역할, 참고용 여부, 고정 선정 seed. |
| `nict_raw_sha256`, `training_sha256` | 예약 자료 | 원본 NICT와 기존 학습 파일의 스냅샷 해시. 파일 바뀜을 탐지한다. |

**특히 중요한 예외:** gold-200 파일은 `split: "test"`를 담지만 이미 모델 진단에 반복 사용되었으므로 현재의 **실제 역할은 legacy dev**다. calibration 후보의 `axes: null`은 아직 채점되지 않았음을 뜻한다. 예약 176행도 `axes: null`이며, 개발 중 정답·예측을 열람하지 않는 것이 기존 계약이다. 근거: [기존 평가 계약](../work/capstone/docs/ml-transition-contract.md), [gold-200](../work/capstone/data/fixtures/ml_transition_gold_human_200.jsonl), [calibration 후보](../work/capstone/data/fixtures/ml_transition_calibration_candidates_90.jsonl).

## G. 아직 현재 공통 저장 필드로 없는 것

앞서 제안한 `audio_ref`, `human_spoken`, `split_group_id`, `annotation_view`, `modality`, `rubric_version`, `missing_reason`, `observation_window`, `relationship_state`, `adaptation_log`는 **위 기존 파일과 DB의 공통 구현 필드가 아니다.** 출처별 시간·화자 정보가 일부 있어도 서비스 대화의 원음 참조와 새 5항목 평가 조건이 자동으로 갖춰지는 것은 아니다. 추가 필드의 목적은 [최종 솔루션](Pally_Final_Solution_2026-09-17.md)에 설명했다.
