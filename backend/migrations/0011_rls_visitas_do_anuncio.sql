-- backend/migrations/0011_rls_visitas_do_anuncio.sql
-- SO roda no Supabase — depende de auth.uid(). Mesma convencao da 0002, 0005
-- e 0009, e o mesmo motivo de arquivo separado: o banco de teste aplica a
-- 0010 e pula esta.
--
-- POR QUE ESTA MIGRATION EXISTE SEPARADA DA 0010, E NAO DENTRO DELA
--
-- Porque a 0010 saiu sem RLS, e isso foi um buraco. Medido em producao logo
-- depois de aplicar: `item_visits` era a UNICA tabela do schema `public` com
-- `relrowsecurity = false`, e o papel `anon` -- que e a chave publica
-- embutida no bundle do front-end -- tinha SELECT, INSERT, UPDATE, DELETE e
-- TRUNCATE sobre ela, concedidos pelo default do Supabase.
--
-- Sem dado dentro e sem o codigo que escreve ainda no ar, o estrago possivel
-- era inserir lixo ou truncar. Com a colheita rodando, seria visita de todo
-- vendedor legivel por qualquer um com a chave publica.
--
-- Fica como arquivo proprio em vez de emendado na 0010 porque a 0010 ja foi
-- aplicada em producao: reescrever uma migration ja aplicada e mentir sobre o
-- historico, e o `APLICADAS.tsv` deixaria de bater com o que o banco tem.
--
-- A licao, registrada: o padrao do projeto e "toda tabela de tenant ganha
-- policy". Segui a spec, que nao mencionava RLS, em vez de comparar com o
-- schema ao lado.
alter table item_visits enable row level security;
create policy "item_visits_own" on item_visits for all using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
