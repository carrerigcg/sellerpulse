import type { FluxoDia } from "@/lib/api";

/**
 * Soma receita, custos do Mercado Livre e margem de contribuição da janela.
 *
 * Usado por `/dashboard` e `/demo` (visão Executive) pra alimentar os
 * `KpiCard` — extraído junto com os componentes visuais no Checkpoint 2 da
 * Sprint 3 pra não duplicar a mesma conta nas duas telas.
 *
 * `custo` é comissão do ML + frete, e nada mais: a parcela de custo estimado
 * em 55% da receita saiu, porque era número inventado sendo somado a dois
 * números reais. Ver o comentário no topo de `src/metrics.py`.
 */
export function totalizarFluxo(dias: FluxoDia[]) {
  return dias.reduce(
    (acc, d) => ({
      receita: acc.receita + d.receita_bruta,
      custo: acc.custo + d.taxas_ml + d.frete,
      margem: acc.margem + d.margem_contribuicao,
    }),
    { receita: 0, custo: 0, margem: 0 },
  );
}
