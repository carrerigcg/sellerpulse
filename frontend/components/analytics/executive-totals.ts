import type { FluxoDia } from "@/lib/api";

/**
 * Soma receita, custo e lucro de uma janela de fluxo financeiro.
 *
 * Usado por `/dashboard` e `/demo` (visão Executive) pra alimentar os
 * `KpiCard` — extraído junto com os componentes visuais no Checkpoint 2 da
 * Sprint 3 pra não duplicar a mesma conta nas duas telas.
 */
export function totalizarFluxo(dias: FluxoDia[]) {
  return dias.reduce(
    (acc, d) => ({
      receita: acc.receita + d.receita_bruta,
      custo: acc.custo + d.taxas_ml + d.frete + d.custo_estimado,
      liquido: acc.liquido + d.liquido,
    }),
    { receita: 0, custo: 0, liquido: 0 },
  );
}
