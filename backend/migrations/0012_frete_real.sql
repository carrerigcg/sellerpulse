-- backend/migrations/0012_frete_real.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Desenho em docs/specs/2026-10-27-frete-real-design.md.
--
-- O frete que o vendedor paga nao esta no pedido. `orders.shipping_cost` vem
-- de um campo da raiz que o ML nunca preenche (1.091 de 1.091 pedidos com
-- zero na loja real), e `paid_amount - total_amount` nao diz quem pagou. O
-- valor so existe em GET /shipments/{id}/costs, como `senders[].cost`.

-- Carrinho com varios produtos vira varios pedidos com UM envio. O custo e do
-- envio, e somar por pedido contaria o mesmo frete varias vezes.
alter table orders add column shipment_id bigint;

-- Os pedidos ja ingeridos tem o id do envio no payload cru.
update orders
   set shipment_id = (raw_json->'shipping'->>'id')::bigint
 where raw_json->'shipping'->>'id' is not null;

create index idx_orders_shipment on orders (seller_id, shipment_id);

create table shipment_costs (
    seller_id      uuid not null references sellers(id) on delete cascade,
    shipment_id    bigint not null,
    -- Soma de `senders[].cost`. Pode ser zero: nesse caso o comprador pagou o
    -- frete inteiro. Sem custo colhido nao ha linha -- e ausencia, nao zero.
    custo_vendedor numeric not null check (custo_vendedor >= 0),
    -- O payload inteiro de /costs, para a regra poder ser revista sem buscar
    -- tudo de novo.
    raw_json       jsonb not null,
    colhido_em     timestamptz not null default now(),
    primary key (seller_id, shipment_id)
);

-- O seller de demonstracao nao tem envio no payload (o pedido e sintetico),
-- e a tela trata pedido sem envio como frete zero CONHECIDO. Sem as duas
-- linhas abaixo, a demo publica diria "depois de pagar o frete" com frete
-- nenhum ate o proximo refresh dela, que so roda quando o dado envelhece.
-- Mesma regra do `backend/seed.py`: um envio por pedido, custo igual ao
-- `shipping_cost` sintetico. No banco de teste nao ha linha nenhuma aqui, e
-- as duas sao no-op.
update orders o
   set shipment_id = o.order_id
  from sellers s
 where s.id = o.seller_id and s.is_demo and o.shipment_id is null;

insert into shipment_costs (seller_id, shipment_id, custo_vendedor, raw_json)
select o.seller_id, o.order_id, o.shipping_cost, '{"origem": "demonstracao"}'::jsonb
  from orders o
  join sellers s on s.id = o.seller_id
 where s.is_demo and o.status = 'paid'
on conflict (seller_id, shipment_id) do nothing;

-- Job proprio, como o de visitas: uma chamada por envio, e um 429 aqui nao
-- pode atrasar a ingestao de pedidos. O nome da constraint foi conferido nos
-- dois bancos na 0010.
alter table sync_jobs drop constraint sync_jobs_kind_check;
alter table sync_jobs add constraint sync_jobs_kind_check
    check (kind in ('backfill','delta','visitas','frete'));
