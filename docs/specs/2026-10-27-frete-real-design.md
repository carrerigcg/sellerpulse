# Frete real do vendedor

Estado: mergeada em `c10aca0` (#25), migrations 0012 e 0013 aplicadas em
produção em 2026-10-27. Pendente: o 4b (ver "Fora desta spec").

Item 4a da auditoria de números de 2026-10-27. Até aqui, o frete gravado
vinha de `orders.shipping_cost`, um campo da raiz do pedido que o Mercado
Livre nunca preenche: 1.091 de 1.091 pedidos pagos da loja real tinham frete
R$ 0,00. Desde o commit `737de52`, o front trata o frete como ausência e diz
que ele "ainda não entra na conta". Esta spec faz o frete entrar.

## O que a sondagem mostrou

Sondagem de 10 envios reais da loja, feita em 2026-10-27, só com leitura. Em
todos, a conta fecha assim:

    custos.gross_amount = receiver.cost + Σ senders[].cost + descontos do ML

| envio | quem pagou | receiver.cost | senders.cost | gross |
| --- | --- | --- | --- | --- |
| 48358475047 | comprador | 34,99 | 0 | 34,99 |
| 48358648788 | os dois (flex) | 14,99 | 14,89 | 29,88 |
| 48359109737 | vendedor (frete grátis) | 0 | 54,10 | 89,20 |
| 48340685201 | carrinho com 7 pedidos | 46,99 | 59,64 | 106,63 |

Dois achados que mudam o desenho:

- **`paid_amount − total_amount` não diz quem pagou o frete.** Num envio de
  R$ 16,99 pago pelo comprador, `paid_amount` e `total_amount` vieram iguais.
  A regra não pode sair do pedido.
- **Carrinho é um envio só.** Os 1.100 pedidos pagos da loja são 1.053
  envios. Somar o frete pedido a pedido contaria o carrinho de 7 pedidos sete
  vezes.

## Decisões travadas

1. **O frete do vendedor é `Σ senders[].cost` de `GET /shipments/{id}/costs`.**
   Não há regra por modalidade (`mode`, `logistic_type`): o ML já entrega o
   valor que cabe ao vendedor. O payload inteiro fica guardado em `raw_json`,
   para a regra poder ser revista sem buscar tudo de novo.

2. **Um custo por envio, contado uma vez.** `orders` ganha `shipment_id`, e o
   custo mora em `shipment_costs (seller_id, shipment_id)`. No fluxo, o frete
   entra no dia do **primeiro pedido pago** do envio, e só nele.

3. **Pedido sem envio tem frete zero conhecido.** São 6 dos 1.100 pagos. Sem
   envio não há frete a pagar, e isso não é ausência de dado.

4. **Envio sem custo colhido é ausência, não zero.** O frete do dia soma só o
   que é conhecido. A receita dos pedidos sem custo de envio vai para
   `receita_sem_frete`, e a tela mostra a cobertura, do mesmo jeito que já faz
   com o custo de produto (`receita_sem_custo`).

5. **A colheita é um job próprio, `frete`, encadeado depois de `visitas`.**
   O motivo é o mesmo das visitas: é uma chamada por envio, com cadência e
   modo de falha próprios, e um 429 aqui não pode atrasar a ingestão de
   pedidos. O job busca só envios de pedido pago **sem** custo gravado. Por
   isso não precisa de cursor: a retomada recomeça do que falta. Falha de um
   envio vira aviso e é tentada de novo no ciclo seguinte. O lease é renovado
   a cada envio.

6. **Custo gravado não é recolhido.** Limitação aceita e registrada: se o ML
   cobrar depois um frete de devolução no mesmo envio, ele não entra. Recolher
   tudo a cada ciclo custaria uma chamada por envio da história inteira, para
   sempre.

7. **`orders.shipping_cost` deixa de ser lido.** A coluna continua existindo:
   apagá-la é outra mudança, e a camada `src/` congelada ainda tem o campo. A
   demo deriva o frete no seeding (`backend/seed.py`), como já faz com custo e
   visita: `shipment_id = order_id` e o custo é o `shipping_cost` sintético. O
   `data/demo.db` não muda.

8. **O front volta a mostrar o frete.** Sai `frontend/lib/frete.ts`, as frases
   deixam de dizer "o frete ainda não entra", e o Financeiro ganha o aviso de
   cobertura do frete.

## Ordem de deploy

A trava `checa_migrations.py` exige que a migration esteja aplicada em
produção **antes** do merge. Isso abre uma janela em que o schema é novo e o
código ainda é velho, e ela tem duas consequências tratadas no código:

- **Pedido ingerido na janela fica sem `shipment_id`.** A colheita
  (`frete_pg.py`) preenche a coluna a partir do `raw_json` antes de listar os
  envios. Sem isso, o fluxo leria esses pedidos como "sem envio", ou seja,
  como frete zero conhecido.
- **A demo pública não tem envio no payload.** A 0012 grava, para o seller
  `is_demo`, um envio por pedido com o frete sintético, a mesma regra do
  seed. Sem isso, a demo diria "depois de pagar o frete" sem frete nenhum até
  o próximo refresh, que só roda quando o dado envelhece.

Front e back sobem separados (Vercel e Render). Por um ou dois minutos o
front novo pode falar com o backend velho, que não manda
`receita_sem_frete`. Por isso `lib/frete.ts` trata a coluna ausente como "toda
a receita sem frete buscado", e não como zero.

## Fora desta spec

- **4b, pedido que muda de status depois** (reembolso parcial): é outro PR, e
  ainda está pendente. O delta só pede ao ML pedidos `paid` e `cancelled`.
  Um pedido que vira `partially_refunded` nunca é relido e fica como pago,
  com o valor cheio (0,3% a 0,6% da receita, pela auditoria). Recomendação
  já combinada: manter o pedido na receita, descontando o valor reembolsado.
- O frete por produto na curva ABC: o envio pode juntar vários produtos, e
  ratear seria inventar uma regra.

## Custo de escala

É uma chamada ao ML por envio, uma única vez. A loja real tem cerca de 1.053
envios na primeira colheita e depois um envio por venda nova. O padrão é o
mesmo do job de visitas, que já roda em produção com uma chamada por item.
