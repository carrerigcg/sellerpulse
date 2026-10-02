import { FlowChart } from "@/components/analytics/flow-chart";
import { totalizarFluxo } from "@/components/analytics/executive-totals";
import { KpiCard } from "@/components/analytics/kpi-card";
import { PeriodPicker } from "@/components/analytics/period-picker";
import { janelaAnterior, type FluxoDia } from "@/lib/api";
import { getDemoFluxoFinanceiro, periodoPadraoDaDemo } from "@/lib/demo";

/**
 * Executive da demonstração pública — mesmo conteúdo de `/dashboard`, dados
 * de `/demo/fluxo-financeiro`. Cartões de KPI e gráfico de fluxo vêm de
 * `components/analytics/`, os mesmos componentes da tela autenticada.
 */

export default async function DemoExecutivePage({
  searchParams,
}: PageProps<"/demo">) {
  const params = await searchParams;
  const padrao = periodoPadraoDaDemo();
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
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Executive</h1>
          <p className="mt-1 text-sm text-muted">
            Receita, custos do Mercado Livre e margem de contribuição — dados de
            demonstração.
          </p>
        </div>
        <PeriodPicker de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : fluxo.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum pedido nesta janela de demonstração. Tente outro período.
        </p>
      ) : (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <KpiCard rotulo="Receita bruta" valor={atual.receita} anterior={passado.receita} />
            {/* Mesmos rótulos de `/dashboard` — a demo não pode prometer uma
                conta diferente da que o produto entrega. */}
            <KpiCard
              rotulo="Custos do Mercado Livre"
              valor={atual.custo}
              anterior={passado.custo}
              subirEhRuim
            />
            <KpiCard
              rotulo="Margem de contribuição"
              valor={atual.margem}
              anterior={passado.margem}
              nota="receita − comissão do Mercado Livre − frete"
            />
          </div>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Fluxo financeiro por dia</h2>
            <p className="mt-0.5 text-xs text-muted">
              {fluxo.length} dias com pedidos pagos
            </p>
            <FlowChart dias={fluxo} />
          </section>
        </>
      )}
    </>
  );
}
