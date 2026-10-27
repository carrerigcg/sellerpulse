import type { FluxoDia } from "./api";

/** O dia como chega da API — `receita_sem_frete` pode faltar num backend antigo. */
export type FluxoDiaDaApi = Omit<FluxoDia, "receita_sem_frete"> & { receita_sem_frete?: number };

/**
 * Garante que todo dia diga quanto da receita está sem frete buscado.
 *
 * O frete real é colhido por envio no backend (`backend/ml/frete_pg.py`), e
 * `receita_sem_frete` é o que impede a margem de parecer completa enquanto a
 * colheita não terminou. Front e back sobem separados — Vercel e Render —, e
 * por um ou dois minutos o front novo pode falar com o backend velho, que não
 * manda a coluna. Sem esta função a soma viraria `NaN` na tela.
 *
 * Coluna ausente vira "toda a receita sem frete", nunca zero: zero diria que
 * o frete do dia está completo, e quem está falando com o backend velho não
 * tem frete nenhum.
 */
export function comReceitaSemFrete(dias: readonly FluxoDiaDaApi[]): FluxoDia[] {
  return dias.map((d) => ({
    ...d,
    receita_sem_frete: d.receita_sem_frete ?? d.receita_bruta,
  }));
}
