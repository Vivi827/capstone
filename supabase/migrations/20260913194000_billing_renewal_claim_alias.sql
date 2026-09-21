-- Disambiguate the order record variable from the SQL table alias.
create or replace function public.billing_claim_renewal() returns jsonb language plpgsql set search_path = public as $$
declare a billing_accounts; o billing_orders;
begin
  select * into a from billing_accounts b where renewal_enabled and next_charge_at<=now()
    and not exists(select 1 from billing_orders bo where bo.user_id=b.user_id and bo.kind='renewal' and bo.due_at=b.next_charge_at)
    order by next_charge_at for update skip locked limit 1;
  if not found then return null; end if;
  insert into billing_orders(user_id,idempotency_key,kind,product_id,amount,partner_user_id,status,due_at)
  values(a.user_id,'renewal:'||a.next_charge_at::text,'renewal',a.product_id,
    case when a.product_id='pro_yearly' then 99000 else 9900 end,a.partner_user_id,'processing',a.next_charge_at)
    returning * into o;
  return to_jsonb(o)||jsonb_build_object('sid',a.sid);
end $$;
