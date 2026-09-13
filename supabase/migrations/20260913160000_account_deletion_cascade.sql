-- Delete conversations and messages atomically with the Supabase Auth account.
-- NOT VALID preserves legacy orphan sessions; new writes still enforce ownership.
alter table public.sessions
  add constraint sessions_user_id_auth_fkey
  foreign key (user_id) references auth.users(id) on delete cascade not valid;

create index if not exists sessions_user_id_idx on public.sessions(user_id);

-- The API must fail closed if this migration has not been applied.
create or replace function public.account_deletion_ready()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from pg_catalog.pg_constraint
    where conname = 'sessions_user_id_auth_fkey'
      and conrelid = 'public.sessions'::regclass
      and confrelid = 'auth.users'::regclass
      and confdeltype = 'c'
  );
$$;

revoke all on function public.account_deletion_ready() from public, anon, authenticated;
grant execute on function public.account_deletion_ready() to service_role;
