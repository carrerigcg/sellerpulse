-- backend/migrations/0027_aprovacoes_de_ia.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Spec: docs/specs/2026-11-09-premium-mcp-conta-real-design.md, decisao 7.
--
-- O token que o servidor OAuth do Supabase entrega ao cliente de IA nasce
-- `aal1`, mesmo quando quem aprovou passou pelo app autenticador, e a rota
-- de aprovacao do Supabase nao exige o segundo fator. Esta tabela e a prova,
-- gravada pelo backend so a partir de uma sessao `aal2`, de que o vendedor
-- aprovou aquele cliente com o codigo. O MCP da conta confere a aprovacao
-- contra a hora em que a sessao do token nasceu.
--
-- Uma linha por aprovacao, e nao por cliente: reaprovar nao pode apagar a
-- prova da conexao anterior, que continua valendo.
--
-- RLS ligada e sem policy: so o backend (papel `postgres`, que nao passa por
-- RLS) le e grava. Pela API de dados do Supabase, ninguem le nem grava aqui,
-- nem a sessao do site, nem o token da IA.

create table aprovacoes_de_ia (
    id          bigint generated always as identity primary key,
    user_id     uuid not null references auth.users(id) on delete cascade,
    client_id   text not null,
    aprovado_em timestamptz not null default now()
);

create index idx_aprovacoes_de_ia on aprovacoes_de_ia (user_id, client_id, aprovado_em);

alter table aprovacoes_de_ia enable row level security;
