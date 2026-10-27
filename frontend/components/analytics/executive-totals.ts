import type { FluxoDia } from "@/lib/api";

/**
 * Soma receita, custos do Mercado Livre e margem de contribuição da janela.
 *
 * Usado por `/dashboard` e `/demo` (visão Executive) pra alimentar os
 * `KpiCard` — extraído junto com os componentes visuais no Checkpoint 2 da
 * Sprint 3 pra não duplicar a mesma conta nas duas telas.
 *
 * `custo` é a comissão do ML, e nada mais. O frete ficava somado aqui, mas
 * ainda não é calculado (`lib/frete.ts`): chega como `null`, e somá-lo como
 * zero seria afirmar um frete que ninguém mediu. A parcela de custo estimado
 * em 55% da receita saiu antes, pelo mesmo motivo — número inventado somado a
 * números reais. Ver o comentário no topo de `src/metrics.py`.
 *
 * `custoProdutos` fica separado dele de propósito, e não somado: o cartão da
 * tela se chama "Comissão do Mercado Livre", e juntar as duas coisas num
 * rótulo só repetiria, com outro nome, a mentira do custo total.
 *
 * Existe porque sem ele a conta da tela não fecha: receita menos custos do ML
 * não dá a margem quando há custo de produto descontado. Três números grandes
 * que não batem são piores que quatro que batem.
 */
export function totalizarFluxo(dias: FluxoDia[]) {
  return dias.reduce(
    (acc, d) => ({
      receita: acc.receita + d.receita_bruta,
      custo: acc.custo + d.taxas_ml,
      custoProdutos: acc.custoProdutos + d.custo_produtos,
      margem: acc.margem + d.margem_contribuicao,
    }),
    { receita: 0, custo: 0, custoProdutos: 0, margem: 0 },
  );
}
