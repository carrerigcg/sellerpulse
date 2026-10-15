import { AbcClassCards } from "@/components/analytics/abc-class-cards";
import { AbcTable } from "@/components/analytics/abc-table";
import { CohortHeatmap } from "@/components/analytics/cohort-heatmap";
import { IndicadorCobertura } from "@/components/analytics/indicador-cobertura";
import { ParetoChart } from "@/components/analytics/pareto-chart";
import { PeriodPicker } from "@/components/analytics/period-picker";
import type { AbcLinha, CohortLinha } from "@/lib/api";
import { getDemoAbcPareto, getDemoCohortProduto, periodoPadraoDaDemo } from "@/lib/demo";
import { coberturaDosProdutos, produtosSemCusto } from "@/lib/cobertura";
import { incluiDiasNaoConsolidados, temVisitaColhida } from "@/lib/visitas";
import { DesempenhoAnuncios } from "@/components/analytics/desempenho-anuncios";

/**
 * Produtos da demonstração pública — mesmo conteúdo de `/dashboard/produtos`,
 * dados de `/demo/abc` e `/demo/cohort`. Os gráficos e a tabela vêm de
 * `components/analytics/`, os mesmos componentes da tela autenticada.
 */

export default async function DemoProdutosPage({
  searchParams,
}: PageProps<"/demo/produtos">) {
  const params = await searchParams;
  const padrao = periodoPadraoDaDemo();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let abc: AbcLinha[] = [];
  let cohort: CohortLinha[] = [];
  let erro: string | null = null;

  try {
    [abc, cohort] = await Promise.all([
      getDemoAbcPareto(de, ate),
      getDemoCohortProduto(de, ate),
    ]);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Produtos</h1>
          <p className="mt-1 text-sm text-muted">
            Quais produtos sustentam o faturamento, e quais só ocupam espaço.
          </p>
        </div>
        <PeriodPicker de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : abc.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum pedido nesta janela de demonstração. Tente outro período.
        </p>
      ) : (
        <>
          <AbcClassCards abc={abc} />

          {/* A margem de cada produto só está completa se houver custo
              informado para ele. Aqui a conta é por produto. */}
          <IndicadorCobertura
            cobertura={coberturaDosProdutos(abc)}
            semCusto={produtosSemCusto(abc)}
            href="/demo/custos"
            rotuloDoAtalho="Ver custos"
          />

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Curva ABC de Pareto</h2>
            <p className="mt-0.5 text-xs text-muted">
              Receita por produto, em ordem decrescente, com o percentual acumulado.
            </p>
            <ParetoChart dados={abc} />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Produtos</h2>
            <p className="mt-0.5 text-xs text-muted">{abc.length} produtos no período</p>
            <AbcTable abc={abc} />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Cohort de lançamento</h2>
            <p className="mt-0.5 text-xs text-muted">
              Receita de cada leva de produtos (agrupados pelo mês da primeira venda) em
              cada mês corrente. Mostra se produto novo segura receita depois do mês de
              lançamento ou só dá um pico e some.
            </p>
            <CohortHeatmap linhas={cohort} />
          </section>

          {/* O funil fica abaixo do cohort e separado da tabela ABC: aquela e
              sobre receita e precisa continuar ordenada por ela (a classe
              A/B/C e o acumulado SAEM dessa ordem). Esta e sobre o funil e
              pode ser ordenada por qualquer coluna sem quebrar nada. */}
          <DesempenhoAnuncios abc={abc} />

          {/* Aviso dos 48h aqui, junto do que ele descreve. */}
          {temVisitaColhida(abc) && incluiDiasNaoConsolidados(ate) && (
            <p className="mt-3 rounded-lg bg-highlight-soft px-3 py-2 text-xs leading-relaxed text-ink">
              As visitas dos últimos dois dias ainda estão sendo consolidadas pelo Mercado
              Livre. A conversão desse período tende a aparecer mais alta do que vai ficar.
            </p>
          )}
        </>
      )}
    </>
  );
}
