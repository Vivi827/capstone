-- Sandbox payment credentials and orders are server-only, separate from readable entitlements.
create table public.billing_accounts (
  user_id uuid primary key references auth.users(id) on delete cascade,
  partner_user_id uuid not null default gen_random_uuid(),
  sid text,
  product_id text check (product_id in ('pro_monthly', 'pro_yearly')),
  trial_used boolean not null default false,
  anchor_at timestamptz,
  cycle integer not null default 0,
  next_charge_at timestamptz,
  renewal_enabled boolean not null default false,
  deactivation_pending boolean not null default false,
  closing boolean not null default false,
  updated_at timestamptz not null default now()
);
alter table public.billing_accounts enable row level security;
revoke all on public.billing_accounts from anon, authenticated;
grant all on public.billing_accounts to service_role;

create table public.billing_orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.billing_accounts(user_id) on delete cascade,
  idempotency_key text not null,
  kind text not null check (kind in ('initial', 'renewal')),
  product_id text not null check (product_id in ('pro_monthly', 'pro_yearly')),
  amount integer not null check (amount in (0, 9900, 99000)),
  trial_days integer not null default 0 check (trial_days in (0, 7)),
  status text not null default 'preparing' check (status in
    ('preparing', 'ready', 'processing', 'approved', 'failed', 'uncertain', 'canceled')),
  partner_user_id uuid not null,
  tid text unique,
  callback_state text,
  success_url text,
  cancel_url text,
  checkout_url text,
  mobile_url text,
  due_at timestamptz,
  expires_at timestamptz not null default now() + interval '15 minutes',
  approved_at timestamptz,
  receipt jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, idempotency_key)
);
create index billing_orders_user_created on public.billing_orders(user_id, created_at desc);
alter table public.billing_orders enable row level security;
revoke all on public.billing_orders from anon, authenticated;
grant all on public.billing_orders to service_role;

create function public.billing_begin_checkout(p_user_id uuid, p_product_id text,
  p_idempotency_key text, p_callback_state text, p_success_url text, p_cancel_url text)
returns jsonb language plpgsql set search_path = public as $$
declare a billing_accounts; o billing_orders; trial integer;
begin
  if p_product_id not in ('pro_monthly','pro_yearly') then raise exception 'invalid_product'; end if;
  insert into billing_accounts(user_id) values(p_user_id) on conflict do nothing;
  select * into a from billing_accounts where user_id=p_user_id for update;
  if a.closing then raise exception 'account_closing'; end if;
  select * into o from billing_orders where user_id=p_user_id and idempotency_key=p_idempotency_key;
  if found then
    if o.product_id<>p_product_id then raise exception 'idempotency_conflict'; end if;
    return to_jsonb(o);
  end if;
  if a.deactivation_pending or a.renewal_enabled or exists(select 1 from subscriptions where user_id=p_user_id
    and entitled and current_period_end>now()) then raise exception 'subscription_active'; end if;
  if exists(select 1 from billing_orders where user_id=p_user_id and (
    status in ('processing','uncertain') or (status in ('preparing','ready') and expires_at>now())))
    then raise exception 'checkout_pending'; end if;
  update billing_orders set status='canceled',updated_at=now() where user_id=p_user_id
    and status in ('preparing','ready') and expires_at<=now();
  trial := case when p_product_id='pro_yearly' and not a.trial_used then 7 else 0 end;
  insert into billing_orders(user_id,idempotency_key,kind,product_id,amount,trial_days,
    partner_user_id,callback_state,success_url,cancel_url)
  values(p_user_id,p_idempotency_key,'initial',p_product_id,
    case when trial=7 then 0 when p_product_id='pro_yearly' then 99000 else 9900 end,
    trial,a.partner_user_id,p_callback_state,p_success_url,p_cancel_url) returning * into o;
  return to_jsonb(o);
end $$;

create function public.billing_claim_approval(p_order_id uuid) returns boolean
language plpgsql set search_path = public as $$
declare uid uuid; claimed uuid;
begin
  select user_id into strict uid from billing_orders where id=p_order_id;
  perform 1 from billing_accounts where user_id=uid for update;
  update billing_orders set status='processing',updated_at=now()
    where id=p_order_id and kind='initial' and status='ready' and expires_at>now()
    returning id into claimed;
  return claimed is not null;
end $$;

-- Receipt validation happens on the server before this atomic order/entitlement transaction.
create function public.billing_finish_order(p_order_id uuid, p_tid text, p_sid text, p_approved_at timestamptz)
returns void language plpgsql set search_path = public as $$
declare o billing_orders; a billing_accounts; uid uuid; period_end timestamptz; anchor timestamptz; n integer;
begin
  select user_id into strict uid from billing_orders where id=p_order_id;
  select * into a from billing_accounts where user_id=uid for update;
  select * into o from billing_orders where id=p_order_id for update;
  if o.status='approved' then return; end if;
  if o.status not in ('processing','uncertain') then raise exception 'order_not_approvable'; end if;
  if o.tid is not null and o.tid<>p_tid then raise exception 'receipt_mismatch'; end if;
  if p_sid is null or p_sid='' then raise exception 'sid_required'; end if;
  if o.kind='initial' then
    anchor := p_approved_at + make_interval(days=>o.trial_days);
    n := case when o.trial_days=7 then 0 else 1 end;
  else
    if a.sid<>p_sid or a.next_charge_at is distinct from o.due_at then raise exception 'stale_renewal'; end if;
    anchor := a.anchor_at;
    n := a.cycle + 1;
  end if;
  period_end := anchor + case when o.product_id='pro_yearly' then make_interval(years=>n) else make_interval(months=>n) end;
  update billing_accounts set sid=p_sid,product_id=o.product_id,
    trial_used=trial_used or o.trial_days=7,anchor_at=anchor,cycle=n,
    next_charge_at=period_end,renewal_enabled=true,deactivation_pending=false,updated_at=now() where user_id=uid;
  update billing_orders set status='approved',tid=p_tid,approved_at=p_approved_at,
    updated_at=now() where id=p_order_id;
  insert into subscriptions(user_id,plan,status,entitled,product_id,current_period_end,will_renew,provider,updated_at)
    values(uid,'pro',case when o.trial_days=7 then 'trialing' else 'active' end,true,o.product_id,period_end,true,'kakaopay',now())
  on conflict(user_id) do update set plan=excluded.plan,status=excluded.status,entitled=true,
    product_id=excluded.product_id,current_period_end=excluded.current_period_end,
    will_renew=true,provider='kakaopay',updated_at=now();
end $$;

-- A durable attempt is committed before sending a charge, preventing duplicate worker charges.
create function public.billing_claim_renewal() returns jsonb language plpgsql set search_path = public as $$
declare a billing_accounts; o billing_orders;
begin
  select * into a from billing_accounts b where renewal_enabled and next_charge_at<=now()
    and not exists(select 1 from billing_orders o where o.user_id=b.user_id and o.kind='renewal' and o.due_at=b.next_charge_at)
    order by next_charge_at for update skip locked limit 1;
  if not found then return null; end if;
  insert into billing_orders(user_id,idempotency_key,kind,product_id,amount,partner_user_id,status,due_at)
  values(a.user_id,'renewal:'||a.next_charge_at::text,'renewal',a.product_id,
    case when a.product_id='pro_yearly' then 99000 else 9900 end,a.partner_user_id,'processing',a.next_charge_at)
    returning * into o;
  return to_jsonb(o)||jsonb_build_object('sid',a.sid);
end $$;

create function public.billing_stop_renewal(p_user_id uuid) returns text
language plpgsql set search_path = public as $$
declare a billing_accounts;
begin
  select * into a from billing_accounts where user_id=p_user_id for update;
  if not found then return null; end if;
  if exists(select 1 from billing_orders where user_id=p_user_id and status in ('processing','uncertain'))
    then raise exception 'payment_processing'; end if;
  update billing_accounts set renewal_enabled=false,deactivation_pending=(sid is not null),updated_at=now() where user_id=p_user_id;
  update subscriptions set will_renew=false,updated_at=now() where user_id=p_user_id;
  return a.sid;
end $$;

create function public.billing_prepare_account_deletion(p_user_id uuid) returns void
language plpgsql set search_path = public as $$
declare a billing_accounts;
begin
  insert into billing_accounts(user_id) values(p_user_id) on conflict do nothing;
  select * into a from billing_accounts where user_id=p_user_id for update;
  if a.renewal_enabled or a.deactivation_pending or exists(select 1 from billing_orders
    where user_id=p_user_id and (status in ('processing','uncertain') or
    (status in ('preparing','ready') and expires_at>now()))) then
    raise exception 'payment_processing';
  end if;
  update billing_accounts set closing=true where user_id=p_user_id;
end $$;

-- Null limit denotes a currently valid Pro entitlement; usage is still counted for learning records.
create or replace function public.reserve_turn(p_user_id uuid, p_date date, p_limit int)
returns int language plpgsql set search_path = public as $$
declare new_used int;
begin
  if p_limit is null and not exists(select 1 from subscriptions where user_id=p_user_id
    and entitled and status in ('active','trialing') and current_period_end>now()) then
    raise exception 'pro_entitlement_required';
  end if;
  insert into usage_daily(user_id,date_kst,used_turns) values(p_user_id,p_date,1)
  on conflict(user_id,date_kst) do update set used_turns=usage_daily.used_turns+1
    where p_limit is null or usage_daily.used_turns<p_limit returning used_turns into new_used;
  return coalesce(new_used,-1);
end $$;

revoke all on function public.billing_begin_checkout(uuid,text,text,text,text,text) from public,anon,authenticated;
revoke all on function public.billing_finish_order(uuid,text,text,timestamptz) from public,anon,authenticated;
revoke all on function public.billing_claim_approval(uuid) from public,anon,authenticated;
revoke all on function public.billing_claim_renewal() from public,anon,authenticated;
revoke all on function public.billing_stop_renewal(uuid) from public,anon,authenticated;
revoke all on function public.reserve_turn(uuid,date,int) from public,anon,authenticated;
grant execute on function public.billing_begin_checkout(uuid,text,text,text,text,text) to service_role;
grant execute on function public.billing_finish_order(uuid,text,text,timestamptz) to service_role;
grant execute on function public.billing_claim_approval(uuid) to service_role;
grant execute on function public.billing_claim_renewal() to service_role;
grant execute on function public.billing_stop_renewal(uuid) to service_role;
grant execute on function public.reserve_turn(uuid,date,int) to service_role;
revoke all on function public.billing_prepare_account_deletion(uuid) from public,anon,authenticated;
grant execute on function public.billing_prepare_account_deletion(uuid) to service_role;
