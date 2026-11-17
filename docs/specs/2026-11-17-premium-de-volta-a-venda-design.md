# Premium de volta à venda

Estado: no ar desde 2026-11-17 (#62, `5c2200c`; Render live e Vercel com
`/termos` servindo a v2 e o cartão do Premium em `/planos`). Vendas seguem
fechadas. Fecha a etapa 11 (funções do Premium) de
`docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## O pedido

O Premium saiu da vitrine em 2026-10-30 (#38) porque prometia funções que
não existiam. Elas estão no ar desde então, e o Guilherme mandou seguir
(2026-11-17).

## O que já está no ar e provado

| Função | Spec | Prova |
| --- | --- | --- |
| Histórico de 12 meses | `2026-11-06-premium-historico-de-12-meses` | no ar desde #52 |
| Atualização a cada 6 horas | `2026-11-06-premium-sync-a-cada-6-horas` | fila de produção, 13 a 17/11: 4 rodadas por dia (00h, 06h, 12h, 18h; uma sincronização manual na mesma faixa conta como a da vez) |
| Alertas no Resumo | `2026-11-06-premium-alertas-no-painel` | no ar desde #54 |
| Até 3 contas, com a soma | `2026-11-06-premium-varias-contas` | no ar desde #55 e #56 |
| IA conectada à loja | `2026-11-09-premium-mcp-conta-real` | token real no Claude e no ChatGPT, número igual ao banco (2026-11-17) |
| Atendimento exclusivo no WhatsApp | `2026-11-09-premium-atendimento-exclusivo` | segunda a sábado, 8h às 18h |

## Decisões travadas

1. **O Premium entra no checkout e na troca de plano** (`a_venda` volta ao
   padrão). A trava `a_venda` continua no código, testada com um plano
   fora de venda simulado, para o próximo plano que nascer fora da vitrine.
2. **As vendas continuam fechadas.** `VENDAS_ABERTAS` não muda: o cartão do
   Premium aparece com "Quero saber quando abrir", como os outros.
3. **Cartão na vitrine** com uma função provada por item. O item da IA diz
   "Claude", e não "Claude e ChatGPT": no ChatGPT, conector personalizado só
   existe nos planos Business, Enterprise e Edu (ajuda da OpenAI, conferida
   em 2026-11-17). O tutorial da tela Segurança explica os dois.
4. **WhatsApp do atendimento:** o mesmo da seção 16 dos Termos,
   (11) 99234-4633 (confirmado pelo Guilherme em 2026-11-17).
5. **Termos `2026-11-v2`** (decisão do Guilherme, 2026-11-17): o Premium na
   tabela de preços (7.1) e a cláusula do atendimento do Premium (9), com o
   que cobre e o que não cobre, sem prazo de resposta; e o preço de depois
   do lançamento do Premium (R$ 169,90) na 7.2, que sustenta o riscado do
   cartão. A Política sobe junto
   só no número, porque o teste exige a mesma versão nos dois textos. Quem
   tem assinatura aceita de novo ao entrar: hoje, uma só (a do Guilherme).
   A seção 14 pede aviso de 30 dias para mudança relevante; esta não tira
   direito de ninguém, só acrescenta um plano e um atendimento.
6. **Vitrine em três colunas a partir de `lg`**; abaixo disso, um cartão por
   linha, com o recomendado (Exclusive) primeiro.

## Fora desta entrega

- Cadeado ou convite para o Premium nos outros planos (alertas, IA, a frase
  das contas extras em `fraseDasContas`): a decisão 3 da spec dos alertas era
  não mostrar enquanto o Premium estivesse fora de venda.
- Abrir as vendas (`VENDAS_ABERTAS`), que espera o Vercel Pro e a revisão
  do advogado.
- Provas que seguem abertas nas specs de origem: o card de alertas visto
  logado com dado real, o painel real com duas contas na soma, o tempo da
  primeira busca de 12 meses.
