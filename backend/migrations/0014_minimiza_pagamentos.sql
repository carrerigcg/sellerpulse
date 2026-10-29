-- backend/migrations/0014_minimiza_pagamentos.sql
-- DDL portatil: roda no Supabase E no banco de teste (la, sem linha nenhuma,
-- e no-op).
--
-- Migration de DADO, nao de schema. Vai como migration, e nao como UPDATE
-- solto, para ficar registrada no APLICADAS.tsv e passar pela trava da CI.
--
-- Tira de orders.raw_json->payments[] os identificadores do meio de pagamento
-- do comprador. Nenhuma analise os usa, e sao o dado mais sensivel da base
-- (LGPD, art. 6o, III). Os VALORES do pagamento ficam. A mesma lista vive em
-- CAMPOS_DE_PAGAMENTO_DESCARTADOS (backend/ml/ingest_pg.py), que faz o corte
-- daqui para frente. Ver docs/specs/2026-10-28-minimizacao-pagamentos-design.md.
--
-- WITH ORDINALITY + ORDER BY: o jsonb_agg devolve os pagamentos na ordem
-- original, e o pedido com dois pagamentos nao troca a ordem deles.
update orders
   set raw_json = jsonb_set(
         raw_json,
         '{payments}',
         (select coalesce(
                   jsonb_agg(
                     p - array['card_id', 'authorization_code', 'payer_id',
                               'issuer_id', 'activation_uri', 'atm_transfer_reference']
                     order by ordem),
                   '[]'::jsonb)
            from jsonb_array_elements(raw_json->'payments') with ordinality as t(p, ordem))
       )
 where jsonb_typeof(raw_json->'payments') = 'array'
   and exists (
         select 1
           from jsonb_array_elements(raw_json->'payments') p
          where p ?| array['card_id', 'authorization_code', 'payer_id',
                           'issuer_id', 'activation_uri', 'atm_transfer_reference']
       );
