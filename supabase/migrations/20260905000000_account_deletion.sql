-- 7주차 계정 삭제 요청 (스캐폴드). PM 재인증 방식 확정 + 실제 purge 잡 전에는 비활성.
-- 보존 정책: 요청해도 즉시 하드삭제하지 않고 2년(purge_after) 보존 후 정리 대상.
-- forward-only. 기존 마이그레이션은 수정하지 않는다.

create table if not exists deletion_requests (
  user_id       uuid primary key references auth.users (id) on delete cascade,
  requested_at  timestamptz not null default now(),
  purge_after   timestamptz not null,               -- requested_at + 2년 (보존 정책)
  status        text not null default 'pending',    -- pending | canceled | purged
  reauth_method text,                                -- 재인증 방식(PM 확정 후 기록)
  updated_at    timestamptz not null default now()
);

alter table deletion_requests enable row level security;

-- 본인 요청 상태만 조회. 쓰기 정책 없음 → 클라이언트 직접 요청/취소 불가, 백엔드(service_role)만.
drop policy if exists deletion_requests_select_own on deletion_requests;
create policy deletion_requests_select_own on deletion_requests
  for select using (auth.uid() = user_id);
