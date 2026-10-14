-- backend/migrations/0009_rls_custo_de_produto.sql
-- SO roda no Supabase — depende de auth.uid(), que nao existe num Postgres
-- generico. Mesma convencao da 0002 e da 0005, e o mesmo motivo de arquivo
-- separado: o banco de teste aplica a 0008 e pula esta.
--
-- Defesa em profundidade, como as outras: o isolamento real continua sendo o
-- `seller_id = $N` explicito em cada query, com o seller_id resolvido do JWT
-- em backend/deps.py. Esta policy cobre quem alcancar o Postgres sem passar
-- pelo backend -- a API REST automatica do Supabase, por exemplo.
--
-- `for all` e nao so `select`: product_costs e a primeira tabela do sistema em
-- que o VENDEDOR escreve, entao insert e update tambem precisam da trava.
alter table product_costs enable row level security;
create policy "product_costs_own" on product_costs for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
