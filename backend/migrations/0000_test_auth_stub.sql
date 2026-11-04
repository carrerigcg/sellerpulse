-- backend/migrations/0000_test_auth_stub.sql
-- SÓ pro Postgres de teste local. O Supabase já tem `auth.users` nativo
-- (gerenciado pelo GoTrue); aqui simulamos o mínimo que as FKs de
-- 0001_init.sql precisam. NÃO aplicar no Supabase.

create extension if not exists pgcrypto;

create schema if not exists auth;

create table if not exists auth.users (
    id    uuid primary key default gen_random_uuid(),
    email text
);

-- O segundo fator (TOTP) do Supabase Auth: o backend recusa token `aal1` de
-- quem tem um fator verificado. No Supabase a tabela tem mais colunas e enums.
create table if not exists auth.mfa_factors (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    factor_type text not null,
    status      text not null
);
