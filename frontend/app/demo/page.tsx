import { FlowChart } from "@/components/analytics/flow-chart";
import { totalizarFluxo } from "@/components/analytics/executive-totals";
import { IndicadorCobertura } from "@/components/analytics/indicador-cobertura";
import { KpiCard } from "@/components/analytics/kpi-card";
import { ExportButton } from "@/components/analytics/export-button";
import { janelaAnterior, type FluxoDia } from "@/lib/api";
import { COLUNAS_FLUXO } from "@/lib/colunas-export";
import { getDemoFluxoFinanceiro } from "@/lib/demo";
import { coberturaDoFluxo } from "@/lib/cobertura";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Executive da demonstração pública — mesmo conteúdo de `/dashboard`, dados
 * de `/demo/fluxo-financeiro`. Cartões de KPI e gráfico de fluxo vêm de
 * `components/analytics/`, os mesmos componentes da tela autenticada.
 */

export default async function DemoExecutivePage({
  searchParams,
}: PageProps<"/demo">) {
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
      getDemoFluxoFinanceiro(de, ate),
      getDemoFluxoFinanceiro(antDe, antAte),
    ]);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  const atual = totalizarFluxo(fluxo);
  const passado = totalizarFluxo(anterior);

  return (
    <>
      <CabecalhoDeTela
        titulo="Executive"
        subtitulo="Receita, custos do Mercado Livre e margem de contribuição — dados de demonstração."
        de={de}
        ate={ate}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : fluxo.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum pedido nesta janela de demonstração. Tente outro período.
        </p>
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
            {/* Mesmos rótulos de `/dashboard` — a demo não pode prometer uma
                conta diferente da que o produto entrega. */}
            <KpiCard
              rotulo="Custos do Mercado Livre"
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
              nota="receita − comissão do Mercado Livre − frete − custo dos produtos"
            />
          </div>

          {/* A regra de honestidade: a margem acima só está completa se
              houver custo informado para toda a receita do período. */}
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
