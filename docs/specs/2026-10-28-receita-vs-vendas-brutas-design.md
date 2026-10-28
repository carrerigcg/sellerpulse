# Receita bruta x "vendas brutas" do Mercado Livre

Estado: mergeada em `ed71ef8` (#29), no ar no Render e na Vercel em 2026-10-28.
Primeira entrega feita pela skill `/entregar`; os três revisores deram "não bloqueia".

## Por quê

O Guilherme comparou o Financeiro com o painel do Mercado Livre, no mesmo
período (01/09 a 28/09), e os números não batiam:

| painel | pedidos | unidades | valor |
| --- | --- | --- | --- |
| Mercado Livre, "Vendas brutas" | 186 | 198 | R$ 28.674 |
| SellerPulse, "Receita bruta" | — | — | R$ 22.919 |

A diferença fecha até o centavo, pelos dados da conta real:

| | pedidos | unidades | valor |
| --- | --- | --- | --- |
| pagos de 01/09 a 27/09 (o que a tela mostrava) | 148 | 159 | R$ 22.919,30 |
| \+ pagos em 28/09 ("Até" exclusivo) | 6 | 6 | R$ 750,00 |
| \+ cancelados e devolvidos de 01/09 a 28/09 | 32 | 33 | R$ 5.004,00 |
| = "Vendas brutas" do ML | 186 | 198 | R$ 28.673,30 |

Os R$ 5.004 são exatamente as 15 canceladas (R$ 2.535) mais as 17 devolvidas
(R$ 2.469) do painel do ML.

Nenhum dos dois números está errado. O ML chama de "venda bruta" tudo o que
foi vendido, mesmo o que voltou depois. O SellerPulse chama de "receita bruta"
o que continua pago. O defeito é que a tela não dizia isso. Quem compara os
dois painéis conclui que o nosso número está errado, e confiança em número é o
que este produto vende.

## Decisões travadas

1. **A receita bruta continua sendo só a de pedidos pagos.** É o dinheiro que
   ficou, e é sobre ele que a margem se calcula. Incluir cancelado inflaria a
   margem.
2. **O cartão diz o que conta.** A nota da "Receita bruta" passa a ser: "Só
   vendas pagas. Canceladas e devolvidas ficam fora."
3. **O que ficou de fora aparece na tela, com o valor.** Uma linha abaixo dos
   cartões mostra quantos pedidos foram cancelados ou devolvidos no período e
   quanto somam. Também diz que o "vendas brutas" do Mercado Livre soma esse
   valor. Com ela, a conta contra o painel do ML fecha na própria tela.
4. **Cancelada e devolvida aparecem juntas.** Na nossa base as duas chegam como
   `cancelled`. Separar exigiria ler o motivo no payload de cada pedido, e
   para fechar a conta com o ML a soma basta.
5. **A janela é a mesma dos cartões**, por `date_closed` no fuso do vendedor,
   com o "Até" exclusivo. A conciliação acima foi medida assim.
6. **O dado vem de um endpoint próprio**, com o total da janela
   (`/metrics/cancelamentos` e `/demo/cancelamentos`), e não de uma coluna nova
   no fluxo diário. No fluxo, um dia só com cancelamento viraria linha nova com
   receita zero, o que mudaria o gráfico, o CSV e o Resumo.
7. **Se a busca falhar, a linha some, e o resto da tela continua.** É
   informação de apoio: sem ela a tela fica menos clara, mas nada fica errado.

## Fora desta spec

- Separar cancelada de devolvida.
- Levar a mesma linha para o Resumo.
