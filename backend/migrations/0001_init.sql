-- backend/migrations/0001_init.sql
-- Schema multi-tenant do SellerPulse. Aplicar no Supabase (SQL Editor) e no
-- Postgres de teste local (depois de 0000_test_auth_stub.sql, que só existe lá).

create extension if not exists pgcrypto;

create table sellers (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null unique references auth.users(id) on delete cascade,
    ml_seller_id  bigint,
    ml_nickname   text,
    created_at    timestamptz not null default now()
);

create table orders (
    order_id         bigint not null,
    seller_id        uuid not null references sellers(id) on delete cascade,
    date_closed       timestamptz not null,
    status            text not null,
    total_amount      numeric not null,
    marketplace_fee   numeric not null,
    shipping_cost     numeric not null,
    buyer_id          bigint,
    raw_json          jsonb not null,
    fetched_at        timestamptz not null,
    primary key (seller_id, order_id)
);
create index idx_orders_date on orders(seller_id, date_closed);

create table order_items (
    seller_id   uuid not null,
    order_id    bigint not null,
    item_id     text not null,
    quantity    integer not null,
    unit_price  numeric not null,
    primary key (seller_id, order_id, item_id),
    foreign key (seller_id, order_id) references orders(seller_id, order_id) on delete cascade
);

create table items_cache (
    seller_id     uuid not null references sellers(id) on delete cascade,
    item_id       text not null,
    title         text not null,
    category_id   text not null,
    fetched_at    timestamptz not null,
    primary key (seller_id, item_id)
);

create table categories_cache (
    seller_id     uuid not null references sellers(id) on delete cascade,
    category_id   text not null,
    name          text not null,
    fetched_at    timestamptz not null,
    primary key (seller_id, category_id)
);

create table claims (
    seller_id    uuid not null references sellers(id) on delete cascade,
    claim_id     bigint not null,
    order_id     bigint,
    status       text not null,
    date_created timestamptz not null,
    raw_json     jsonb not null,
    fetched_at   timestamptz not null,
    primary key (seller_id, claim_id)
);
create index idx_claims_date on claims(seller_id, date_created);

-- Schema criado agora, populado só na Sprint 2 (OAuth do Mercado Livre).
create table oauth_tokens (
    seller_id      uuid primary key references sellers(id) on delete cascade,
    access_token   text not null,
    refresh_token  text not null,
    expires_at     timestamptz not null,
    updated_at     timestamptz not null default now()
);
