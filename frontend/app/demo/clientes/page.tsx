import { BuyersTable } from "@/components/analytics/buyers-table";
import { ExportButton } from "@/components/analytics/export-button";
import { RfmChart } from "@/components/analytics/rfm-chart";
import { RfmLegend } from "@/components/analytics/rfm-legend";
import { SegmentBand } from "@/components/analytics/segment-band";
import type { RfmLinha } from "@/lib/api";
import { COLUNAS_RFM } from "@/lib/colunas-export";
import { getDemoRfmScores } from "@/lib/demo";
import { periodoPadrao } from "@/lib/periodo";
import { segmentoDaUrl } from "@/lib/segmento-da-url";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Clientes da demonstração pública — mesmo conteúdo de `/dashboard/clientes`,
 * dados de `/demo/rfm`. O gráfico, a faixa de segmentos e a tabela vêm de
 * `components/analytics/`, os mesmos componentes da tela autenticada.
 */

export default async function DemoClientesPage({
  searchParams,
}: PageProps<"/demo/clientes">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;
  const filtroInicial = segmentoDaUrl(params.segmento);

  let rfm: RfmLinha[] = [];
  let erro: string | null = null;

  try {
    rfm = await getDemoRfmScores(de, ate);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  const temDados = !erro && rfm.length > 0;

  return (
    <>
      <CabecalhoDeTela
        titulo="Clientes"
        subtitulo="Quem compra de novo, quem está sumindo, e quanto isso vale."
        de={de}
        ate={ate}
        tela="clientes"
        temDados={temDados}
        chegouFiltrado={filtroInicial !== null}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : !temDados ? (
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

          {/* `id` é o destino do cartão do Resumo (`lib/resumo.ts`). */}
          <section id="compradores" className="mt-6 rounded-xl border border-line p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">Compradores</h2>
                <p className="mt-0.5 text-xs text-muted">{rfm.length} compradores no período</p>
              </div>
              {/* `demo-` no nome do arquivo: o dado é de um vendedor
                  sintético, e quem reabrir o CSV semana que vem precisa
                  saber disso. A ressalva não vai DENTRO do arquivo — uma
                  linha acima do cabeçalho desloca as colunas no Excel. */}
              <ExportButton
                linhas={rfm}
                colunas={COLUNAS_RFM}
                tela="demo-clientes"
                de={de}
                ate={ate}
              />
            </div>
            {/* `key` pelo filtro: o Next reaproveita o componente quando só a
                query muda (a sidebar leva de volta a /clientes sem
                `?segmento=`), e o `useState(filtroInicial)` ficaria preso ao
                filtro de antes. */}
            <BuyersTable key={filtroInicial ?? "todos"} dados={rfm} filtroInicial={filtroInicial} />
          </section>
        </>
      )}
    </>
  );
}
