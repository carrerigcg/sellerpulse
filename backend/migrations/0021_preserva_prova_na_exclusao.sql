-- backend/migrations/0021_preserva_prova_na_exclusao.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Desenho em docs/specs/2026-11-03-exclusao-de-conta-design.md.

-- A Politica promete guardar a prova do aceite e os registros da cobranca por
-- 5 anos, e o cascade de `sellers` os apagava junto com a conta. Sem a chave
-- estrangeira, o `seller_id` fica como identificador da conta que ja nao
-- existe. Quem grava aqui e o backend, sempre com o seller da sessao.
alter table aceites_de_termos drop constraint aceites_de_termos_seller_id_fkey;
alter table checkouts drop constraint checkouts_seller_id_fkey;

-- Liga o seller apagado ao usuario e marca quando a conta saiu: e o que permite
-- achar os registros de acesso (por `user_id`) numa contestacao, e o comeco do
-- prazo de 5 anos. So identificadores, nenhum dado pessoal.
create table contas_excluidas (
    seller_id   uuid        primary key,
    user_id     uuid        not null,
    excluida_em timestamptz not null default now()
);

-- Nasce fechada, como a 0018 e a 0019. Nenhuma policy: so o backend le e
-- escreve.
alter table contas_excluidas enable row level security;
