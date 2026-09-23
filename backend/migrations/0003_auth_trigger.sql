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
