-- 5주차 결제/구독 (provider-neutral). provider = 카카오페이 예정.
-- forward-only. 실제 결제 연동은 가맹점 키 + sandbox 실호출 후.

-- 서버 기준 Pro 권한 (클라이언트 영수증 아니라 이 값만 신뢰).
create table if not exists subscriptions (
  user_id              uuid primary key references auth.users (id) on delete cascade,
  plan                 text not null default 'free',    -- free | pro
  status               text not null default 'none',    -- none|trialing|active|grace_period|canceled|expired|revoked
  entitled             boolean not null default false,
  product_id           text,
  current_period_end   timestamptz,
  will_renew           boolean not null default false,
  provider             text,                             -- kakaopay 등
  provider_customer_id text,
  updated_at           timestamptz not null default now()
);
alter table subscriptions enable row level security;
drop policy if exists subscriptions_select_own on subscriptions;
create policy subscriptions_select_own on subscriptions
  for select using (auth.uid() = user_id);

-- webhook 멱등 + 감사. 클라이언트 직접 접근 금지(service_role만) → select 정책 없음.
create table if not exists billing_events (
  provider          text not null,
  provider_event_id text not null,
  payload           jsonb,
  received_at       timestamptz not null default now(),
  primary key (provider, provider_event_id)
);
alter table billing_events enable row level security;
