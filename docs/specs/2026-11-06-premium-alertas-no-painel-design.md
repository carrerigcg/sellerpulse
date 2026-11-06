# Premium: alertas no painel

Estado: em implementação na branch `feat/premium-alertas`. Item 4 das funções
do Premium. O envio por e-mail fica para depois (decisão 4.1).

## O pedido

O Guilherme escolheu, em 2026-11-06, 1.1, 2.1 e 3.1: alertas no painel de
margem negativa e de anúncio parado, num card no topo do Resumo, só no
Premium.

## O que se mediu (loja real, 2026-11-06, últimos 90 dias, só leitura)

- 564 pedidos pagos, todos com um item só; 14 dos 538 envios são carrinho.
- Nenhum produto tem custo informado. O alerta de margem não dispara até o
  vendedor informar custos.
- 487 produtos venderam, quase todos poucas vezes. Só 7 venderam em 5 dias
  ou mais nos últimos 120, e 3 deles passam da regra de parado hoje.

## Decisões travadas

1. **Margem negativa (1.1), nos últimos 30 dias, no dia do vendedor:**
   receita − taxa do ML − frete − custo, por produto.
   - A taxa e o frete são do pedido e do envio. Cada item fica com a parte
     proporcional à sua receita: a taxa dentro do pedido, e o frete do
     carrinho entre os pedidos pagos do mesmo envio.
   - **Só entra o produto com todas as vendas do período com custo
     informado e com o frete conhecido.** Margem com custo faltando seria
     inventada. Pedido sem envio tem frete zero conhecido, como no fluxo.
   - Sem nenhum produto avaliado, o card diz para informar o custo, e não
     "nenhum alerta": "nenhum" afirmaria que a margem está boa.
2. **Anúncio parado (2.1), pelo ritmo do próprio produto:**
   - entra o produto com venda em pelo menos 5 dias distintos nos últimos
     120; sem ritmo, não dá para dizer que parou;
   - o intervalo normal é a mediana dos dias entre vendas;
   - parado é ficar sem vender mais que `max(3 × intervalo, 7)` dias.
   - **Os dias contam até o dia da última sincronização, e não até hoje.**
     Com a sincronização parada, todo produto pareceria parado sem estar.
     Sem sincronização nenhuma, não há alerta.
3. **Onde aparece (3.1):** card "Alertas" no topo do Resumo, só para quem
   tem `Recurso.ALERTAS` (só o Premium). Cada alerta leva a um lugar:
   margem negativa à tela de Custos, onde se confere o custo; parado ao
   anúncio no Mercado Livre.
   - **Sem cadeado nos outros planos enquanto o Premium estiver fora de
     venda:** "Fazer upgrade" para um plano que não se pode contratar seria
     um botão que não leva a nada. O cadeado entra com a volta à venda.
4. **Endpoint `GET /metrics/alertas`**, com `exige(Recurso.ALERTAS)`. As
   janelas (30 e 120 dias) cabem no histórico de todo plano que tem o
   recurso.
5. **No máximo 5 alertas de cada tipo no card**, os piores primeiro (menor
   margem; mais vezes acima do intervalo normal), com o total ao lado.

## Fora desta entrega

- Alertas por e-mail (depende do domínio e do Resend).
- A demo: o card não aparece nela por enquanto.
- O cadeado nos outros planos: com a volta do Premium à venda.
- Escala (`auditor-de-escala`, medido em 2026-11-06): ~12 ms de servidor na
  loja real e 230 a 270 ms numa loja sintética de 3.000 itens e 50 mil
  pedidos por ano. Não bloqueia. Ficam três melhorias para quando houver loja
  grande: devolver só os 5 piores de cada tipo mais o total, guardar o
  resultado em cache pela `last_synced_at`, e juntar as três consultas numa
  só (hoje são três idas e voltas em série).
- O rateio da taxa dentro do pedido é pela receita, não pelo `sale_fee` de
  cada item (que está no `raw_json`). Na loja real todo pedido tem um item
  só, então a diferença é zero.
