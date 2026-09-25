-- backend/migrations/0002_rls.sql
-- Row-Level Security. SÓ roda no Supabase — depende de auth.uid(), função que
-- não existe num Postgres genérico (por isso não é aplicada no banco de teste).
--
-- NOTA DE ARQUITETURA: o backend FastAPI conecta via connection string direta
-- (DATABASE_URL, papel `postgres`), não via cliente Supabase/PostgREST — então
-- estas policies NÃO são o mecanismo que isola tenants nas queries do backend.
-- Esse isolamento é feito explicitamente por `seller_id = $N` em cada query,
-- com o seller_id resolvido em backend/deps.py a partir do JWT validado.
-- RLS aqui é defesa em profundidade: protege qualquer acesso ao Postgres que
-- não passe pelo backend (ex.: a API REST automática do Supabase).

alter table sellers enable row level security;
create policy "sellers_select_own" on sellers
    for select using (user_id = auth.uid());
create policy "sellers_update_own" on sellers
    for update using (user_id = auth.uid());

alter table orders enable row level security;
create policy "orders_own" on orders for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);

alter table order_items enable row level security;
create policy "order_items_own" on order_items for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);

alter table items_cache enable row level security;
create policy "items_cache_own" on items_cache for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);

alter table categories_cache enable row level security;
create policy "categories_cache_own" on categories_cache for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);

alter table claims enable row level security;
create policy "claims_own" on claims for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);

alter table oauth_tokens enable row level security;
create policy "oauth_tokens_own" on oauth_tokens for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
