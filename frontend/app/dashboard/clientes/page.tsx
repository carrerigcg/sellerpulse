import { BuyersTable } from "@/components/analytics/buyers-table";
import { ExportButton } from "@/components/analytics/export-button";
import { RfmChart } from "@/components/analytics/rfm-chart";
import { RfmLegend } from "@/components/analytics/rfm-legend";
import { SegmentBand } from "@/components/analytics/segment-band";
import { Cadeado } from "@/components/planos/cadeado";
import { getAcesso, mensagemDeFalhaAoCarregar, getRfmScores, type RfmLinha } from "@/lib/api";
import { COLUNAS_RFM } from "@/lib/colunas-export";
import { getDemoRfmScores } from "@/lib/demo";
import { podeUsar } from "@/lib/plano";
import { periodoPadrao } from "@/lib/periodo";
import { segmentoDaUrl } from "@/lib/segmento-da-url";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";
import { SemPedidosNoPeriodo } from "@/components/analytics/sem-pedidos-no-periodo";

/**
 * Clientes — dispersão e segmentação RFM.
 *
 * Responde quem compra de novo, quem está sumindo, e quanto isso vale. Vem
 * de um endpoint só, `/segmentation/rfm` — já existe e está testado desde
 * a Sprint 1, esta tela só consome.
 *
 * O gráfico, a faixa de segmentos e a tabela vivem em `components/analytics/`
 * — a mesma versão é usada por `/demo/clientes` (Checkpoint 2 da Sprint 3).
 */

export default async function ClientesPage({
  searchParams,
}: PageProps<"/dashboard/clientes">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;
  const filtroInicial = segmentoDaUrl(params.segmento);

  const acesso = await getAcesso().catch(() => null);
  if (!podeUsar(acesso, "clientes")) {
    return <ClientesTrancado de={de} ate={ate} />;
  }

  let rfm: RfmLinha[] = [];
  let erro: string | null = null;

  try {
    rfm = await getRfmScores(de, ate);
  } catch (e) {
    erro = mensagemDeFalhaAoCarregar(e);
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
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : !temDados ? (
        <SemPedidosNoPeriodo mensagem="Nenhum comprador com pedido pago neste período." />
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
              {podeUsar(acesso, "exportar") && (
                <ExportButton
                  linhas={rfm}
                  colunas={COLUNAS_RFM}
                  tela="clientes"
                  de={de}
                  ate={ate}
                />
              )}
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

/**
 * Clientes no plano que não os cobre: a amostra é da demonstração, nunca dos
 * compradores do vendedor — o backend nem os manda (403 `fora-do-plano`).
 */
async function ClientesTrancado({ de, ate }: { de: string; ate: string }) {
  const amostra = await getDemoRfmScores(de, ate).catch(() => null);
  return (
    <>
      <CabecalhoDeTela
        titulo="Clientes"
        subtitulo="Quem compra de novo, quem está sumindo, e quanto isso vale."
        de={de}
        ate={ate}
        tela="clientes"
        temDados={false}
      />
      <Cadeado
        titulo="Quem compra de novo, e quem está sumindo"
        descricao="Cada comprador classificado por recência, frequência e valor, para você saber quem vale reconquistar antes que vá embora."
      >
        {amostra && amostra.length > 0 && (
          <>
            <SegmentBand rfm={amostra} />
            <RfmChart dados={amostra} />
          </>
        )}
      </Cadeado>
    </>
  );
}
