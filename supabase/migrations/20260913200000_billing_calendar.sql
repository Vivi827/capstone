-- Preserve Korean calendar billing dates, including month-end and leap-day anchors.
create or replace function public.billing_finish_order(p_order_id uuid, p_tid text, p_sid text, p_approved_at timestamptz)
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
  period_end := ((anchor at time zone 'Asia/Seoul') + case when o.product_id='pro_yearly'
    then make_interval(years=>n) else make_interval(months=>n) end) at time zone 'Asia/Seoul';
  -- Do not bill multiple missed periods in a catch-up loop after a long outage.
  if period_end<=p_approved_at then
    anchor := p_approved_at;
    n := 1;
    period_end := ((anchor at time zone 'Asia/Seoul') + case when o.product_id='pro_yearly'
      then interval '1 year' else interval '1 month' end) at time zone 'Asia/Seoul';
  end if;
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
