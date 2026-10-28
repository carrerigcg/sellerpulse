import { FlowChart } from "@/components/analytics/flow-chart";
import {
  GRADE_DOS_CARTOES,
  temFreteBuscado,
  totalizarFluxo,
} from "@/components/analytics/executive-totals";
import { IndicadorCobertura } from "@/components/analytics/indicador-cobertura";
import { IndicadorFrete } from "@/components/analytics/indicador-frete";
import { LinhaDeCancelamentos } from "@/components/analytics/linha-de-cancelamentos";
import { KpiCard } from "@/components/analytics/kpi-card";
import { ExportButton } from "@/components/analytics/export-button";
import {
  mensagemDeFalhaAoCarregar,
  getCancelamentos,
  getFluxoFinanceiro,
  janelaAnterior,
  type FluxoDia,
} from "@/lib/api";
import type { Cancelamentos } from "@/lib/cancelamentos";
import { COLUNAS_FLUXO } from "@/lib/colunas-export";

import { coberturaDoFluxo, coberturaDoFrete } from "@/lib/cobertura";
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
  let cancelados: Cancelamentos | null = null;
  let erro: string | null = null;

  try {
    const [antDe, antAte] = janelaAnterior(de, ate);
    // A linha de cancelamentos é apoio: se a busca dela falhar, a tela segue
    // sem ela, em vez de cair inteira junto.
    [fluxo, anterior, cancelados] = await Promise.all([
      getFluxoFinanceiro(de, ate),
      getFluxoFinanceiro(antDe, antAte),
      getCancelamentos(de, ate).catch(() => null),
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
          {/* Um cartão por parcela da conta que existe no período, para ela
              fechar na tela: receita − comissão − frete − custo dos produtos
              = margem. Frete e custo de produto só aparecem quando há algum. */}
          <div
            className={`mt-6 grid gap-4 sm:grid-cols-2 ${
              GRADE_DOS_CARTOES[
                3 + Number(temFreteBuscado(atual)) + Number(atual.custoProdutos > 0)
              ]
            }`}
          >
            <KpiCard
              rotulo="Receita bruta"
              valor={atual.receita}
              anterior={passado.receita}
              nota="Só vendas pagas. Canceladas e devolvidas ficam fora."
            />
            {/* "Comissão do Mercado Livre", e o frete em cartão próprio: um
                "Custo total" juntaria parcelas de origem e cobertura diferentes
                num número só, a mesma mentira do custo estimado que saiu daqui. */}
            <KpiCard
              rotulo="Comissão do Mercado Livre"
              valor={atual.custo}
              anterior={passado.custo}
              subirEhRuim
            />
            {temFreteBuscado(atual) && (
              <KpiCard
                rotulo="Frete pago por você"
                valor={atual.frete}
                anterior={passado.frete}
                subirEhRuim
              />
            )}
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
              nota="receita − comissão do Mercado Livre − frete − custo dos produtos."
            />
          </div>

          {/* A regra de honestidade: a margem acima só está completa se
              houver frete buscado e custo informado para toda a receita. */}
          <LinhaDeCancelamentos cancelamentos={cancelados} />
          <IndicadorFrete cobertura={coberturaDoFrete(atual)} />
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
