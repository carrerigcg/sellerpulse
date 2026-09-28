import Link from "next/link";

import { ApiError, getRfmScores, type RfmLinha } from "@/lib/api";

import { GraficoRfm } from "./grafico-rfm";
import { SEGMENTOS } from "./segmentos";
import { TabelaCompradores } from "./tabela-compradores";

/**
 * Clientes — dispersão e segmentação RFM.
 *
 * Responde quem compra de novo, quem está sumindo, e quanto isso vale. Vem
 * de um endpoint só, `/segmentation/rfm` — já existe e está testado desde
 * a Sprint 1, esta tela só consome.
 */

// Mesmo padrão de janela do Executive: últimos 90 dias corridos.
function periodoPadrao() {
  const hoje = new Date();
  const noventaDiasAtras = new Date(hoje);
  noventaDiasAtras.setDate(hoje.getDate() - 90);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { de: fmt(noventaDiasAtras), ate: fmt(hoje) };
}

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

export default async function ClientesPage({
  searchParams,
}: PageProps<"/dashboard/clientes">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let rfm: RfmLinha[] = [];
  let erro: string | null = null;

  try {
    rfm = await getRfmScores(de, ate);
  } catch (e) {
    erro =
      e instanceof ApiError && e.status === 401
        ? "Sua sessão expirou. Entre de novo."
        : "Não foi possível carregar os dados. O backend está no ar?";
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
        <SeletorPeriodo de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : rfm.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum comprador com pedido pago neste período.{" "}
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
          <FaixaSegmentos rfm={rfm} />

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Dispersão RFM</h2>
            <p className="mt-0.5 text-xs text-muted">
              Cada ponto é um comprador. Quem está embaixo à direita — comprou há muito
              tempo e gasta pouco — é quem está indo embora.
            </p>
            <GraficoRfm dados={rfm} />
            <Legenda />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Compradores</h2>
            <p className="mt-0.5 text-xs text-muted">{rfm.length} compradores no período</p>
            <TabelaCompradores dados={rfm} />
          </section>
        </>
      )}
    </>
  );
}

function FaixaSegmentos({ rfm }: { rfm: RfmLinha[] }) {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {SEGMENTOS.map((def) => {
        const linhas = rfm.filter((l) => l.segmento === def.chave);
        const receita = linhas.reduce((acc, l) => acc + l.monetary, 0);

        return (
          <div key={def.chave} className="rounded-xl border border-line p-5">
            <div className="flex items-center justify-between">
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${def.badge}`}>
                {def.rotulo}
              </span>
              <span className="tabular text-xs text-muted">
                {linhas.length} {linhas.length === 1 ? "comprador" : "compradores"}
              </span>
            </div>
            <p className="tabular mt-2 text-2xl font-semibold">{brl.format(receita)}</p>
            <p className="mt-2 text-xs text-muted">{def.descricao}</p>
          </div>
        );
      })}
    </div>
  );
}

function Legenda() {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
      {SEGMENTOS.map((def) => (
        <span key={def.chave} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{
              backgroundColor: def.contornoGrafico ? "transparent" : def.corGrafico,
              border: def.contornoGrafico ? `1.5px solid ${def.contornoGrafico}` : undefined,
            }}
          />
          {def.rotulo}
        </span>
      ))}
    </div>
  );
}

function SeletorPeriodo({ de, ate }: { de: string; ate: string }) {
  return (
    <form className="flex items-end gap-2">
      <label className="text-xs text-muted">
        De
        <input
          type="date"
          name="de"
          defaultValue={de}
          className="mt-1 block rounded-lg border border-line px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>
      <label className="text-xs text-muted">
        Até
        <input
          type="date"
          name="ate"
          defaultValue={ate}
          className="mt-1 block rounded-lg border border-line px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>
      <button
        type="submit"
        className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-hover"
      >
        Aplicar
      </button>
    </form>
  );
}
