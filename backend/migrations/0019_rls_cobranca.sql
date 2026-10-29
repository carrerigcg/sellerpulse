-- backend/migrations/0019_rls_cobranca.sql
-- SO roda no Supabase. Mesma convencao das outras de RLS: o banco de teste
-- aplica a 0018 e pula esta.
--
-- `checkouts` e `eventos_do_gateway` sao do backend, e de ninguem mais: RLS
-- ligada e NENHUMA policy fecha leitura e escrita para a chave publica do
-- front. O backend conecta como dono e ignora RLS. As colunas novas de
-- `assinaturas` ja estao cobertas pela policy de leitura da 0017.
alter table checkouts enable row level security;
alter table eventos_do_gateway enable row level security;
