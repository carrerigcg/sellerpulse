import Link from "next/link";

import { FlowChart } from "@/components/analytics/flow-chart";
import { totalizarFluxo } from "@/components/analytics/executive-totals";
import { KpiCard } from "@/components/analytics/kpi-card";
import { PeriodPicker } from "@/components/analytics/period-picker";
import { ApiError, getFluxoFinanceiro, janelaAnterior, type FluxoDia } from "@/lib/api";

import { DisparaDelta } from "./delta";

/**
 * Executive — receita, custos do Mercado Livre e margem de contribuição do
 * período, com variação sobre a janela anterior, mais o fluxo diário.
 *
 * Escopo: esta é a visão que a Sprint 1 entrega. As páginas de Produtos
 * (Pareto ABC, cohort) e Clientes (RFM) são da Sprint 3 — os endpoints
 * já existem e estão testados, falta a tela.
 *
 * Os cartões de KPI e o gráfico de fluxo vivem em `components/analytics/`
 * — a mesma versão é usada por `/demo` (Checkpoint 2 da Sprint 3).
 */

// A Sprint 2 trouxe a ingestão real do Mercado Livre, então o padrão deixa
// de apontar pra janela fixa de agosto/2026 (onde só existia a base
// sintética) e passa a ser os últimos 90 dias corridos a partir de hoje.
function periodoPadrao() {
  const hoje = new Date();
  const noventaDiasAtras = new Date(hoje);
  noventaDiasAtras.setDate(hoje.getDate() - 90);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { de: fmt(noventaDiasAtras), ate: fmt(hoje) };
}

export default async function ExecutivePage({
  searchParams,
}: PageProps<"/dashboard">) {
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
    erro =
      e instanceof ApiError && e.status === 401
        ? "Sua sessão expirou. Entre de novo."
        : "Não foi possível carregar os dados. O backend está no ar?";
  }

  const atual = totalizarFluxo(fluxo);
  const passado = totalizarFluxo(anterior);

  return (
    <>
      <DisparaDelta />

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Executive</h1>
          <p className="mt-1 text-sm text-muted">
            Receita, custos do Mercado Livre e margem de contribuição do período.
          </p>
        </div>
        <PeriodPicker de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : fluxo.length === 0 ? (
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
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <KpiCard rotulo="Receita bruta" valor={atual.receita} anterior={passado.receita} />
            {/* "Custos do Mercado Livre", não "Custo total": este cartão é
                comissão + frete, e chamá-lo de total seria repetir num rótulo
                novo a mentira do custo estimado que saiu daqui. */}
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
