import { FlowChart } from "@/components/analytics/flow-chart";
import { totalizarFluxo } from "@/components/analytics/executive-totals";
import { IndicadorCobertura } from "@/components/analytics/indicador-cobertura";
import { KpiCard } from "@/components/analytics/kpi-card";
import { ExportButton } from "@/components/analytics/export-button";
import { mensagemDeFalhaAoCarregar, getFluxoFinanceiro, janelaAnterior, type FluxoDia } from "@/lib/api";
import { COLUNAS_FLUXO } from "@/lib/colunas-export";

import { coberturaDoFluxo } from "@/lib/cobertura";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";
import { SemPedidosNoPeriodo } from "@/components/analytics/sem-pedidos-no-periodo";

/**
 * Financeiro — receita, custos do Mercado Livre e margem de contribuição do
 * período, com variação sobre a janela anterior, mais o fluxo diário.
 *
 * Até 2026-10-23 era o "Executive" e morava em `/dashboard`, que virou o
 * Resumo. `tela="executive"` continua: é a chave do "já vi" do tutorial e o
 * nome do CSV exportado, e renomeá-los é outro projeto.
 *
 * Os cartões de KPI e o gráfico de fluxo vivem em `components/analytics/`
 * — a mesma versão é usada por `/demo` (Checkpoint 2 da Sprint 3).
 */

export default async function FinanceiroPage({
  searchParams,
}: PageProps<"/dashboard/financeiro">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let fluxo: FluxoDia[] = [];
  let anterior: FluxoDia[] = [];
  let erro: string | null = null;

  try {
    const [antDe, antAte] = janelaAnterior(de, ate);
    [fluxo, anterior] = await Promise.all([
      getFluxoFinanceiro(de, ate),
      getFluxoFinanceiro(antDe, antAte),
    ]);
  } catch (e) {
    erro = mensagemDeFalhaAoCarregar(e);
  }

  const atual = totalizarFluxo(fluxo);
  const passado = totalizarFluxo(anterior);

  const temDados = !erro && fluxo.length > 0;

  return (
    <>
      <CabecalhoDeTela
        titulo="Financeiro"
        subtitulo="Receita, custos do Mercado Livre e margem de contribuição do período."
        de={de}
        ate={ate}
        tela="executive"
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
          {/* Quatro colunas quando há custo de produto, três quando não há:
              com o cartão a conta fecha na tela (receita − custos do ML −
              custo dos produtos = margem), e sem ele a tela fica como era. */}
          <div
            className={`mt-6 grid gap-4 sm:grid-cols-2 ${
              atual.custoProdutos > 0 ? "lg:grid-cols-4" : "lg:grid-cols-3"
            }`}
          >
            <KpiCard rotulo="Receita bruta" valor={atual.receita} anterior={passado.receita} />
            {/* "Comissão do Mercado Livre", não "Custo total": o frete ainda não
                é calculado (`lib/frete.ts`), e chamá-lo de total seria repetir num rótulo
                novo a mentira do custo estimado que saiu daqui. */}
            <KpiCard
              rotulo="Comissão do Mercado Livre"
              valor={atual.custo}
              anterior={passado.custo}
              subirEhRuim
            />
            {atual.custoProdutos > 0 && (
              <KpiCard
                rotulo="Custo dos produtos"
                valor={atual.custoProdutos}
                anterior={passado.custoProdutos}
                subirEhRuim
              />
            )}
            <KpiCard
              rotulo="Margem de contribuição"
              valor={atual.margem}
              anterior={passado.margem}
              nota="receita − comissão do Mercado Livre − custo dos produtos. O frete ainda não entra na conta."
            />
          </div>

          {/* A regra de honestidade: a margem acima só está completa se
              houver custo informado para toda a receita do período. */}
          <IndicadorCobertura
            cobertura={coberturaDoFluxo(fluxo)}
            href={"/dashboard/custos"}
          />

          <section className="mt-6 rounded-xl border border-line p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">Fluxo financeiro por dia</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {fluxo.length} dias com pedidos pagos
                </p>
              </div>
              <ExportButton
                linhas={fluxo}
                colunas={COLUNAS_FLUXO}
                tela="executive"
                de={de}
                ate={ate}
              />
            </div>
            <FlowChart dias={fluxo} />
          </section>
        </>
      )}
    </>
  );
}
