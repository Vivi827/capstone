-- History 대화 제목. 대화를 처음 종료할 때 Gemini 가 영어 제목을 한 번 생성해 저장하고,
-- 이후 재개·재종료해도 바꾸지 않는다(한 번 정해지면 고정).
-- 비어 있으면(종료 전·생성 실패) API 는 기존처럼 첫 발화를 제목으로 보여준다.
-- forward-only. 기존 마이그레이션은 수정하지 않는다.

alter table sessions add column if not exists title text;
