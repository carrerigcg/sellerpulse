import type { FluxoDia } from "@/lib/api";

/**
 * Soma receita, comissão do ML, frete, custo de produto e margem da janela.
 *
 * Usado pelo Financeiro (dashboard e demo) e pelo Resumo, para a mesma conta
 * não existir em dois lugares.
 *
 * `custo` é a comissão do ML, e nada mais. O frete fica em campo próprio,
 * como o custo de produto, e não somado a ela: o cartão se chama "Comissão do
 * Mercado Livre", e juntar coisas diferentes num rótulo só repetiria, com
 * outro nome, a mentira do custo total. A parcela de custo estimado em 55% da
 * receita saiu daqui pelo mesmo motivo — ver o topo de `src/metrics.py`.
 *
 * `receitaSemFrete` é a receita de vendas cujo frete ainda não foi buscado no
 * Mercado Livre. Enquanto for maior que zero, a margem está maior do que a
 * real — é o par do `receita_sem_custo` do custo de produto.
 *
 * Existe porque sem ele a conta da tela não fecha: receita menos comissão não
 * dá a margem quando há frete e custo de produto descontados. Números grandes
 * que não batem são piores que números que batem.
 */
export function totalizarFluxo(dias: FluxoDia[]) {
  return dias.reduce(
    (acc, d) => ({
      receita: acc.receita + d.receita_bruta,
      custo: acc.custo + d.taxas_ml,
      frete: acc.frete + d.frete,
      receitaSemFrete: acc.receitaSemFrete + d.receita_sem_frete,
      custoProdutos: acc.custoProdutos + d.custo_produtos,
      margem: acc.margem + d.margem_contribuicao,
    }),
    { receita: 0, custo: 0, frete: 0, receitaSemFrete: 0, custoProdutos: 0, margem: 0 },
  );
}

/**
 * O cartão de frete aparece quando há algum frete buscado no período.
 *
 * Com nada buscado ainda, o cartão mostraria "R$ 0" — e zero seria a
 * afirmação de que o vendedor não pagou frete nenhum. Nesse caso quem fala é
 * o `IndicadorFrete`, que diz que a busca está em andamento.
 */
export function temFreteBuscado(totais: { receita: number; receitaSemFrete: number }): boolean {
  return totais.receitaSemFrete < totais.receita;
}

/** Classe literal, e não montada, para o Tailwind enxergá-la no build. */
export const GRADE_DOS_CARTOES: Record<number, string> = {
  3: "lg:grid-cols-3",
  4: "lg:grid-cols-4",
  5: "lg:grid-cols-5",
};
