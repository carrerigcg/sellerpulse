-- backend/migrations/0013_rls_frete_real.sql
-- SO roda no Supabase -- depende de auth.uid(). Mesma convencao da 0002,
-- 0005, 0009 e 0011: o banco de teste aplica a 0012 e pula esta.
--
-- Escrita junto com a 0012, e nao depois. `item_visits` nasceu sem RLS e o
-- papel `anon` -- a chave publica do front -- teve ate TRUNCATE sobre ela
-- (ver 0011). Frete e dado de custo do vendedor.
alter table shipment_costs enable row level security;
create policy "shipment_costs_own" on shipment_costs for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
