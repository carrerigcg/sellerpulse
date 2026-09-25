-- backend/migrations/0003_auth_trigger.sql
-- Garante que todo usuário criado pelo Supabase Auth ganha exatamente uma row
-- em `sellers`. Fica no banco (trigger), não no app, pra não depender de o
-- frontend lembrar de criar o seller depois do signup.
--
-- SÓ roda no Supabase — depende do schema `auth` gerenciado por eles.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.sellers (user_id) values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- handle_new_user() é SECURITY DEFINER e só deve rodar como trigger. Exposta
-- via PostgREST (/rest/v1/rpc/) ela seria chamável por anon/authenticated —
-- flagrado pelo security advisor do Supabase. O privilégio EXECUTE de função
-- de trigger é checado no CREATE TRIGGER, não a cada disparo: revogar aqui
-- não afeta o signup (verificado empiricamente em 2026-09-23).
revoke all on function public.handle_new_user() from public;
revoke all on function public.handle_new_user() from anon;
revoke all on function public.handle_new_user() from authenticated;
