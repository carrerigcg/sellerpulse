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
