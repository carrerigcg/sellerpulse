-- backend/migrations/0016_planos_e_aceite.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Desenho em docs/specs/2026-10-28-planos-e-acesso-design.md.
--
-- Sem plano e sem aceite dos termos, o vendedor so ve a demonstracao. As duas
-- tabelas abaixo sao o que o backend consulta para decidir isso.

-- O plano NAO e coluna em `sellers` de proposito. Ate a 0015, a policy
-- `sellers_update_own` (0002) deixava o proprio usuario alterar a sua linha em
-- `sellers` com a chave publica do Supabase, e um plano guardado ali seria
-- autoconcedido. A 0015 fechou isso, mas o plano e o que libera o produto: ele
-- mora numa tabela que nunca teve escrita pelo cliente, e nao depende de
-- ninguem lembrar disso ao mexer em `sellers`. Esta tabela so recebe policy
-- de leitura (0017); quem escreve e o backend.
create table assinaturas (
    seller_id  uuid primary key references sellers(id) on delete cascade,
    plano      text not null check (plano in ('essencial', 'exclusive', 'premium')),
    -- `manual` enquanto nao ha gateway; `gateway` quando a cobranca atribuir.
    origem     text not null check (origem in ('manual', 'gateway')),
    desde      timestamptz not null default now()
);

-- A prova do aceite dos Termos de Uso. So cresce: aceitar a versao nova nao
-- apaga a anterior, e e o historico que mostra o que foi aceito e quando.
create table aceites_de_termos (
    id         bigint generated always as identity primary key,
    seller_id  uuid not null references sellers(id) on delete cascade,
    versao     text not null,
    aceito_em  timestamptz not null default now(),
    ip         text,
    user_agent text,
    unique (seller_id, versao)
);
