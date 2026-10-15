import Link from "next/link";

import { AbcClassCards } from "@/components/analytics/abc-class-cards";
import { AbcTable } from "@/components/analytics/abc-table";
import { CohortHeatmap } from "@/components/analytics/cohort-heatmap";
import { ExportButton } from "@/components/analytics/export-button";
import { IndicadorCobertura } from "@/components/analytics/indicador-cobertura";
import { ParetoChart } from "@/components/analytics/pareto-chart";
import { PeriodPicker } from "@/components/analytics/period-picker";
import { ApiError, getAbcPareto, getCohortProduto, type AbcLinha, type CohortLinha } from "@/lib/api";
import { COLUNAS_ABC } from "@/lib/colunas-export";
import { coberturaDosProdutos, produtosSemCusto } from "@/lib/cobertura";
import { incluiDiasNaoConsolidados, temVisitaColhida } from "@/lib/visitas";
import { DesempenhoAnuncios } from "@/components/analytics/desempenho-anuncios";

/**
 * Produtos — curva ABC de Pareto e cohort de lançamento.
 *
 * Responde duas perguntas: quais produtos sustentam o faturamento (Pareto +
 * classes A/B/C) e se produto novo segura receita depois do pico de
 * lançamento ou só dá um estouro e desaparece (cohort).
 *
 * Os dois vêm de `/segmentation/abc` e `/segmentation/cohort` — nenhuma
 * query nova, os endpoints já existem e estão testados desde a Sprint 1.
 *
 * Os gráficos e a tabela vivem em `components/analytics/` — a mesma versão
 * é usada por `/demo/produtos` (Checkpoint 2 da Sprint 3).
 */

// Mesmo padrão de janela do Executive: últimos 90 dias corridos.
function periodoPadrao() {
  const hoje = new Date();
  const noventaDiasAtras = new Date(hoje);
  noventaDiasAtras.setDate(hoje.getDate() - 90);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { de: fmt(noventaDiasAtras), ate: fmt(hoje) };
}

export default async function ProdutosPage({
  searchParams,
}: PageProps<"/dashboard/produtos">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let abc: AbcLinha[] = [];
  let cohort: CohortLinha[] = [];
  let erro: string | null = null;

  try {
    [abc, cohort] = await Promise.all([getAbcPareto(de, ate), getCohortProduto(de, ate)]);
  } catch (e) {
    erro =
      e instanceof ApiError && e.status === 401
        ? "Sua sessão expirou. Entre de novo."
        : "Não foi possível carregar os dados. O backend está no ar?";
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
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : abc.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum pedido pago neste período.{" "}
          <Link
            href="/dashboard/conectar"
            className="text-accent underline hover:text-accent-hover"
          >
            Conectar uma conta do Mercado Livre
          </Link>
          .
        </p>
      ) : (
        <>
          <AbcClassCards abc={abc} />

          {/* A margem de cada produto só está completa se houver custo
              informado para ele. Aqui a conta é por produto. */}
          <IndicadorCobertura
            cobertura={coberturaDosProdutos(abc)}
            semCusto={produtosSemCusto(abc)}
            href={"/dashboard/custos"}
          />

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Curva ABC de Pareto</h2>
            <p className="mt-0.5 text-xs text-muted">
              Receita por produto, em ordem decrescente, com o percentual acumulado.
            </p>
            <ParetoChart dados={abc} />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">Produtos</h2>
                <p className="mt-0.5 text-xs text-muted">{abc.length} produtos no período</p>
              </div>
              <ExportButton
                linhas={abc}
                colunas={COLUNAS_ABC}
                tela="produtos"
                de={de}
                ate={ate}
              />
            </div>
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
