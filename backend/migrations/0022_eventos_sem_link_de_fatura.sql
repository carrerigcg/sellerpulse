-- backend/migrations/0022_eventos_sem_link_de_fatura.sql
-- DDL portatil: roda no Supabase E no banco de teste (la, sem linha nenhuma,
-- e no-op).
--
-- Migration de DADO, como a 0014: vai como migration para ficar registrada no
-- APLICADAS.tsv e passar pela trava da CI.
--
-- Tira de eventos_do_gateway.payload os links da fatura, do comprovante, do
-- boleto e do checkout. Eles abrem sem login a pagina do Asaas com os dados de
-- quem pagou, e nenhum codigo os le. A mesma lista vive em _CHAVES_PESSOAIS
-- (backend/pagamentos/eventos.py), que faz o corte daqui para frente.
update eventos_do_gateway
   set payload = payload #- '{payment,invoiceUrl}'
                         #- '{payment,transactionReceiptUrl}'
                         #- '{payment,bankSlipUrl}'
                         #- '{checkout,link}'
 where payload->'payment' ?| array['invoiceUrl', 'transactionReceiptUrl', 'bankSlipUrl']
    or payload->'checkout' ? 'link';

-- O comprovante tambem vem dentro de cada estorno. WITH ORDINALITY + ORDER BY,
-- como na 0014, para os estornos nao trocarem de ordem.
update eventos_do_gateway
   set payload = jsonb_set(
         payload,
         '{payment,refunds}',
         (select jsonb_agg(r - 'transactionReceiptUrl' order by ordem)
            from jsonb_array_elements(payload->'payment'->'refunds') with ordinality as t(r, ordem))
       )
 where jsonb_typeof(payload->'payment'->'refunds') = 'array'
   and exists (
         select 1
           from jsonb_array_elements(payload->'payment'->'refunds') r
          where r ? 'transactionReceiptUrl'
       );
