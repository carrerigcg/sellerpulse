-- backend/migrations/0023_varias_contas_por_usuario.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- O Premium conecta ate 3 contas do Mercado Livre num login so. Cada conta e
-- um seller, porque todo o dado, a fila e o worker ja sao por `sellers.id`.
-- Spec: docs/specs/2026-11-06-premium-varias-contas-design.md.
--
-- Plano, aceite e cobranca continuam na conta principal. O indice parcial
-- garante uma principal so por usuario: com duas, o plano do usuario seria
-- o de qual delas? Toda linha que existe hoje e principal (o padrao), e o
-- trigger de cadastro continua criando a principal sem mudar.
--
-- As policies de RLS ja usam `seller_id in (select id from sellers where
-- user_id = auth.uid())`, que cobre varias contas sem mudar.

alter table sellers add column principal boolean not null default true;

create unique index uniq_conta_principal on sellers (user_id) where principal;

-- O UNIQUE de `user_id` servia tambem de indice para achar o seller do
-- usuario; sem ele, a busca por todas as contas do usuario precisa deste.
create index idx_sellers_user on sellers (user_id);

alter table sellers drop constraint sellers_user_id_key;
