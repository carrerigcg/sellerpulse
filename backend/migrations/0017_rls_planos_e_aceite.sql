-- backend/migrations/0017_rls_planos_e_aceite.sql
-- SO roda no Supabase -- depende de auth.uid(). Mesma convencao da 0002,
-- 0005, 0009, 0011 e 0013: o banco de teste aplica a 0016 e pula esta.
--
-- So leitura para o dono, e nenhuma policy de escrita: com RLS ligada e sem
-- policy de insert/update/delete, a chave publica do front nao escreve aqui.
-- Quem atribui plano e grava aceite e o backend, que conecta como dono.
alter table assinaturas enable row level security;
create policy "assinaturas_le_a_propria" on assinaturas for select using (
    seller_id in (select id from sellers where user_id = auth.uid())
);

alter table aceites_de_termos enable row level security;
create policy "aceites_le_os_proprios" on aceites_de_termos for select using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
