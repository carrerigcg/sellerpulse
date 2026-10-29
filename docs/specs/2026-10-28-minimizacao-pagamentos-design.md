# Minimização dos dados de pagamento dos pedidos

Estado: no ar desde 2026-10-28 (#32). A `0014` foi aplicada em produção antes
do merge (1.288 pedidos limpos). Com o deploy no ar, a contagem de pedidos com
identificador seguia em 0: o worker antigo não regravou nada no meio-tempo, e
não foi preciso rodar o `UPDATE` de novo.

## Por quê

Ao escrever a Política de Privacidade (`docs/legal/`, 2026-10-28), o
levantamento do que está guardado mostrou um problema. Cada pedido guarda o
payload inteiro do Mercado Livre em `orders.raw_json`, e o bloco `payments[]`
traz identificadores do meio de pagamento do comprador: `card_id`,
`authorization_code`, `payer_id`, `issuer_id`, `activation_uri` e
`atm_transfer_reference`.

Nenhuma análise usa esses campos. O backend lê do `raw_json` só o `pack_id`
(recompra) e o `shipping.id` (frete). Ainda assim, eles são o dado mais
sensível da base. A LGPD manda tratar só o necessário (art. 6º, III), e um
vazamento deles seria muito pior do que o de qualquer número de venda.

## Decisões travadas (com o Guilherme, 2026-10-28)

1. **Saem só os identificadores.** `CAMPOS_DE_PAGAMENTO_DESCARTADOS` em
   `backend/ml/ingest_pg.py`, a lista acima.
2. **Os valores ficam:** `transaction_amount`, `transaction_amount_refunded`,
   `total_paid_amount`, `shipping_cost`, `coupon_amount`, parcelas, status e
   datas. Eles não identificam ninguém, e foram exatamente esses campos que
   permitiram medir o reembolso parcial (item 4b da auditoria). Tirá-los
   acabaria com a capacidade de auditar números depois.
3. **O comprador fica como está, com ID e apelido.** O ID é a base da tela de
   Clientes. O apelido é como o vendedor reconhece o comprador dentro do ML,
   e deve servir à ação da tela de Clientes, ainda pendente.
4. **Daqui para frente:** a ingestão descarta os campos antes de gravar.
5. **O que já está guardado:** a migration `0014` limpa, com o mesmo critério,
   os pedidos que já estão no banco. É dado, não schema, mas vai como
   migration para ficar registrada no `APLICADAS.tsv` e passar pela trava da
   CI, em vez de virar um `UPDATE` solto em produção.

## O que se perde

Cruzar um pagamento específico com o suporte do Mercado Pago a partir da
nossa base. Não é perda definitiva: os identificadores continuam na API do
ML, pelo número do pedido.

## Fora desta spec

- A exclusão de conta pelo próprio usuário.
- Revisar os outros blocos do payload (`context`, `feedback`, `mediations`).
  Eles não trazem identificador de pagamento; fica para outra rodada.
- A ingestão legada em SQLite (`src/`), que é congelada e não usa a Supabase.
- Pendências opcionais dos revisores: teste da migration com dois pagamentos
  (a ordem foi conferida à mão) e um elemento de `payments[]` que não seja
  objeto, que aborta a migration. Em produção não havia nenhum.
