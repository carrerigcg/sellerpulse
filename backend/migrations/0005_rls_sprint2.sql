-- backend/migrations/0005_rls_sprint2.sql
-- SO roda no Supabase — depende de auth.uid(), que nao existe num Postgres
-- generico. Mesma convencao da 0002.

-- A policy da 0002 permitia ao papel `authenticated` ler a propria linha de
-- oauth_tokens pela API REST automatica do Supabase. Com a tabela vazia era
-- inofensivo; com token real dentro, e expor ao browser um dado que ele nunca
-- precisa ter. RLS ligada SEM policy permissiva nega tudo — e o backend
-- continua entrando pelo papel `postgres`, que nao passa por RLS.
drop policy if exists "oauth_tokens_own" on oauth_tokens;

alter table sync_jobs enable row level security;
create policy "sync_jobs_select_own" on sync_jobs for select using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
