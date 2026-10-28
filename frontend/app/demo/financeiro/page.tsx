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
import { janelaAnterior, type FluxoDia } from "@/lib/api";
import { COLUNAS_FLUXO } from "@/lib/colunas-export";
import type { Cancelamentos } from "@/lib/cancelamentos";
import { getDemoCancelamentos, getDemoFluxoFinanceiro } from "@/lib/demo";
import { coberturaDoFluxo, coberturaDoFrete } from "@/lib/cobertura";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Financeiro da demonstração pública — mesmo conteúdo de
 * `/dashboard/financeiro`, dados de `/demo/fluxo-financeiro`. Cartões de KPI e gráfico de fluxo vêm de
 * `components/analytics/`, os mesmos componentes da tela autenticada.
 */

export default async function DemoFinanceiroPage({
  searchParams,
}: PageProps<"/demo/financeiro">) {
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
    [fluxo, anterior, cancelados] = await Promise.all([
      getDemoFluxoFinanceiro(de, ate),
      getDemoFluxoFinanceiro(antDe, antAte),
      getDemoCancelamentos(de, ate).catch(() => null),
    ]);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  const atual = totalizarFluxo(fluxo);
  const passado = totalizarFluxo(anterior);

  const temDados = !erro && fluxo.length > 0;

  return (
    <>
      <CabecalhoDeTela
        titulo="Financeiro"
        subtitulo="Receita, custos do Mercado Livre e margem de contribuição — dados de demonstração."
        de={de}
        ate={ate}
        tela="executive"
        temDados={temDados}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : !temDados ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum pedido nesta janela de demonstração. Tente outro período.
        </p>
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
            {/* Mesmos rótulos de `/dashboard` — a demo não pode prometer uma
                conta diferente da que o produto entrega. */}
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

          <LinhaDeCancelamentos cancelamentos={cancelados} />
          {/* A regra de honestidade: a margem acima só está completa se
              houver frete buscado e custo informado para toda a receita. */}
          <IndicadorFrete cobertura={coberturaDoFrete(atual)} />
          <IndicadorCobertura
            cobertura={coberturaDoFluxo(fluxo)}
            href="/demo/custos"
            rotuloDoAtalho="Ver custos"
          />

          <section className="mt-6 rounded-xl border border-line p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">Fluxo financeiro por dia</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {fluxo.length} dias com pedidos pagos
                </p>
              </div>
              {/* `demo-` no nome do arquivo: o dado é de um vendedor
                  sintético, e quem reabrir o CSV semana que vem precisa
                  saber disso. A ressalva não vai DENTRO do arquivo — uma
                  linha acima do cabeçalho desloca as colunas no Excel. */}
              <ExportButton
                linhas={fluxo}
                colunas={COLUNAS_FLUXO}
                tela="demo-executive"
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
