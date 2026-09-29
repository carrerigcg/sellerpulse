-- backend/migrations/0004_ml_tokens_e_fila.sql
-- Sprint 2: tokens do ML cifrados + fila de sincronizacao.
--
-- DDL portatil de proposito: esta migration roda no Supabase E no banco de
-- teste (via setup_test_db.py). Tudo que depende de auth.uid() — RLS e a
-- remocao da policy de oauth_tokens — vive na 0005, que so roda no Supabase.

-- As colunas em texto puro nunca receberam token real (a tabela nasceu vazia
-- na Sprint 1), entao trocar o tipo agora e barato. Depois nao seria.
alter table oauth_tokens
    drop column access_token,
    drop column refresh_token,
    add column access_token_enc  text not null,
    add column refresh_token_enc text not null,
    add column key_version smallint not null default 1;

-- Quando o delta rodou por ultimo. Null = nunca sincronizou.
alter table sellers add column last_synced_at timestamptz;

create table sync_jobs (
    id            bigserial primary key,
    seller_id     uuid not null references sellers(id) on delete cascade,
    kind          text not null check (kind in ('backfill','delta')),
    status        text not null default 'queued'
                  check (status in ('queued','running','done','failed')),
    attempts      integer not null default 0,
    fase          text,
    processados   integer not null default 0,
    total         integer not null default 0,
    -- De onde retomar se a instancia morrer no meio: o backfill grava aqui o
    -- ultimo mes concluido. Sem isso, um job interrompido recomeca os 6 meses
    -- e num free tier que hiberna talvez nunca termine.
    cursor        jsonb,
    warnings      jsonb not null default '[]'::jsonb,
    erro          text,
    leased_until  timestamptz,
    created_at    timestamptz not null default now(),
    started_at    timestamptz,
    finished_at   timestamptz,
    -- O reaper procura lease vencido com `leased_until < now()`, e NULL < now()
    -- e unknown, nao true: uma linha 'running' sem lease nunca seria repescada.
    -- Pior, uniq_sync_job_ativo a conta como ativa, entao o seller ficaria sem
    -- conseguir enfileirar nada, para sempre, sem erro em lugar nenhum.
    constraint running_tem_lease check (status <> 'running' or leased_until is not null)
);

-- Um job ativo por seller. A garantia e do banco, nao de um `if` no app:
-- impede o botao manual de empilhar backfills e o delta de duplicar job.
create unique index uniq_sync_job_ativo on sync_jobs(seller_id)
    where status in ('queued','running');

-- A fila le so os candidatos; indice parcial mantem ele pequeno mesmo com
-- historico grande de jobs concluidos.
create index idx_sync_jobs_fila on sync_jobs(created_at)
    where status in ('queued','running');
