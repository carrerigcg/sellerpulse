import { BuyersTable } from "@/components/analytics/buyers-table";
import { PeriodPicker } from "@/components/analytics/period-picker";
import { RfmChart } from "@/components/analytics/rfm-chart";
import { RfmLegend } from "@/components/analytics/rfm-legend";
import { SegmentBand } from "@/components/analytics/segment-band";
import type { RfmLinha } from "@/lib/api";
import { getDemoRfmScores } from "@/lib/demo";

/**
 * Clientes da demonstração pública — mesmo conteúdo de `/dashboard/clientes`,
 * dados de `/demo/rfm`. O gráfico, a faixa de segmentos e a tabela vêm de
 * `components/analytics/`, os mesmos componentes da tela autenticada.
 */

// Mesmo padrão de janela das telas autenticadas: últimos 90 dias corridos.
function periodoPadrao() {
  const hoje = new Date();
  const noventaDiasAtras = new Date(hoje);
  noventaDiasAtras.setDate(hoje.getDate() - 90);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { de: fmt(noventaDiasAtras), ate: fmt(hoje) };
}

export default async function DemoClientesPage({
  searchParams,
}: PageProps<"/demo/clientes">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let rfm: RfmLinha[] = [];
  let erro: string | null = null;

  try {
    rfm = await getDemoRfmScores(de, ate);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Clientes</h1>
          <p className="mt-1 text-sm text-muted">
            Quem compra de novo, quem está sumindo, e quanto isso vale.
          </p>
        </div>
        <PeriodPicker de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : rfm.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum comprador nesta janela de demonstração. Tente outro período.
        </p>
      ) : (
        <>
          <SegmentBand rfm={rfm} />

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Dispersão RFM</h2>
            <p className="mt-0.5 text-xs text-muted">
              Cada ponto é um comprador. Quem está embaixo à direita — comprou há muito
              tempo e gasta pouco — é quem está indo embora.
            </p>
            <RfmChart dados={rfm} />
            <RfmLegend />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Compradores</h2>
            <p className="mt-0.5 text-xs text-muted">{rfm.length} compradores no período</p>
            <BuyersTable dados={rfm} />
          </section>
        </>
      )}
    </>
  );
}
