import { AbcClassCards } from "@/components/analytics/abc-class-cards";
import { AbcTable } from "@/components/analytics/abc-table";
import { CohortHeatmap } from "@/components/analytics/cohort-heatmap";
import { ExportButton } from "@/components/analytics/export-button";
import { IndicadorCobertura } from "@/components/analytics/indicador-cobertura";
import { ParetoChart } from "@/components/analytics/pareto-chart";
import { mensagemDeFalhaAoCarregar, getAbcPareto, getCohortProduto, type AbcLinha, type CohortLinha } from "@/lib/api";
import { COLUNAS_ABC } from "@/lib/colunas-export";
import { coberturaDosProdutos, produtosSemCusto } from "@/lib/cobertura";
import { incluiDiasNaoConsolidados, temVisitaColhida } from "@/lib/visitas";
import { DesempenhoAnuncios } from "@/components/analytics/desempenho-anuncios";
import { diagnosticoDaUrl } from "@/lib/diagnostico";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";
import { SemPedidosNoPeriodo } from "@/components/analytics/sem-pedidos-no-periodo";

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

export default async function ProdutosPage({
  searchParams,
}: PageProps<"/dashboard/produtos">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;
  const filtroInicial = diagnosticoDaUrl(params.diagnostico);

  let abc: AbcLinha[] = [];
  let cohort: CohortLinha[] = [];
  let erro: string | null = null;

  try {
    [abc, cohort] = await Promise.all([getAbcPareto(de, ate), getCohortProduto(de, ate)]);
  } catch (e) {
    erro = mensagemDeFalhaAoCarregar(e);
  }

  const temDados = !erro && abc.length > 0;

  return (
    <>
      <CabecalhoDeTela
        titulo="Produtos"
        subtitulo="Quais produtos sustentam o faturamento, e quais só ocupam espaço."
        de={de}
        ate={ate}
        tela="produtos"
        temDados={temDados}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : !temDados ? (
        <SemPedidosNoPeriodo mensagem="Nenhum pedido pago neste período." />
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
          {/* `key` pelo filtro: o Next reaproveita o componente quando só a query
              muda (a sidebar leva de volta a /produtos sem `?diagnostico=`), e o
              `useState(filtroInicial)` ficaria preso ao filtro de antes. */}
          <DesempenhoAnuncios
            key={filtroInicial ?? "todos"}
            abc={abc}
            filtroInicial={filtroInicial}
          />

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
