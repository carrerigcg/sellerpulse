-- backend/migrations/0020_rls_registros_de_acesso.sql
-- SO roda no Supabase -- depende de auth.uid(). Mesma convencao da 0017: o banco
-- de teste aplica a 0019 e pula esta.
--
-- So leitura para o dono, e nenhuma policy de escrita: quem grava e o backend,
-- que conecta como dono.
alter table registros_de_acesso enable row level security;
create policy "registros_de_acesso_le_os_proprios" on registros_de_acesso for select using (
    user_id = auth.uid()
);
