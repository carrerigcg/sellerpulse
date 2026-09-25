import { ApiError, getFluxoFinanceiro, janelaAnterior, type FluxoDia } from "@/lib/api";

/**
 * Executive — receita, custos e lucro do período, com variação sobre a
 * janela anterior, mais o fluxo diário.
 *
 * Escopo: esta é a visão que a Sprint 1 entrega. As páginas de Produtos
 * (Pareto ABC, cohort) e Clientes (RFM) são da Sprint 3 — os endpoints
 * já existem e estão testados, falta a tela.
 */

// A base sintética é ancorada em agosto/2026 (o gerador em src/demo_data.py
// usa data fixa pra ser determinístico), então um "últimos 90 dias" a partir
// de hoje viria vazio. Enquanto a ingestão real do Mercado Livre não entra
// (Sprint 2), o padrão aponta para onde os dados de exemplo existem.
const PERIODO_PADRAO = { de: "2026-05-01", ate: "2026-08-02" };

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

export default async function ExecutivePage({
  searchParams,
}: PageProps<"/dashboard">) {
  const params = await searchParams;
  const de = typeof params.de === "string" ? params.de : PERIODO_PADRAO.de;
  const ate = typeof params.ate === "string" ? params.ate : PERIODO_PADRAO.ate;

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

  const atual = totais(fluxo);
  const passado = totais(anterior);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Executive</h1>
          <p className="mt-1 text-sm text-muted">
            Receita, custos e resultado do período.
          </p>
        </div>
        <SeletorPeriodo de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : fluxo.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum pedido pago neste período.
        </p>
      ) : (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Kpi
              rotulo="Receita bruta"
              valor={atual.receita}
              anterior={passado.receita}
            />
            <Kpi
              rotulo="Custo total"
              valor={atual.custo}
              anterior={passado.custo}
              subirEhRuim
            />
            <Kpi
              rotulo="Lucro líquido"
              valor={atual.liquido}
              anterior={passado.liquido}
            />
          </div>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Fluxo financeiro por dia</h2>
            <p className="mt-0.5 text-xs text-muted">
              {fluxo.length} dias com pedidos pagos
            </p>
            <GraficoFluxo dias={fluxo} />
          </section>
        </>
      )}
    </>
  );
}

function totais(dias: FluxoDia[]) {
  return dias.reduce(
    (acc, d) => ({
      receita: acc.receita + d.receita_bruta,
      custo: acc.custo + d.taxas_ml + d.frete + d.custo_estimado,
      liquido: acc.liquido + d.liquido,
    }),
    { receita: 0, custo: 0, liquido: 0 },
  );
}

function Kpi({
  rotulo,
  valor,
  anterior,
  subirEhRuim = false,
}: {
  rotulo: string;
  valor: number;
  anterior: number;
  subirEhRuim?: boolean;
}) {
  const temBase = anterior !== 0;
  const pct = temBase ? (100 * (valor - anterior)) / anterior : 0;
  // Em custo, subir é resultado pior — o sinal da cor inverte.
  const bom = subirEhRuim ? pct < 0 : pct >= 0;

  return (
    <div className="rounded-xl border border-line p-5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted">
        {rotulo}
      </span>
      <p className="tabular mt-2 text-3xl font-semibold">{brl.format(valor)}</p>
      {temBase && (
        <span
          className={`mt-3 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
            bom ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
          }`}
        >
          {pct >= 0 ? "+" : ""}
          {pct.toFixed(1)}% vs. período anterior
        </span>
      )}
    </div>
  );
}

/**
 * Gráfico de barras em SVG, sem biblioteca.
 *
 * Para uma série diária de uma métrica só, 30 linhas de SVG resolvem e
 * evitam somar uma dependência ao bundle. A Sprint 3 traz Pareto, cohort
 * (heatmap) e dispersão RFM — aí uma lib de gráficos passa a se pagar.
 */
function GraficoFluxo({ dias }: { dias: FluxoDia[] }) {
  const maximo = Math.max(...dias.map((d) => d.receita_bruta), 1);
  const largura = 100 / dias.length;

  return (
    <div className="mt-5">
      <svg
        viewBox="0 0 100 32"
        preserveAspectRatio="none"
        className="h-40 w-full"
        role="img"
        aria-label={`Receita bruta diária de ${dias[0].date} a ${dias[dias.length - 1].date}`}
      >
        {dias.map((d, i) => {
          const altura = (d.receita_bruta / maximo) * 30;
          return (
            <rect
              key={d.date}
              x={i * largura + largura * 0.15}
              y={32 - altura}
              width={largura * 0.7}
              height={altura}
              rx={0.3}
              className="fill-accent/70"
            />
          );
        })}
      </svg>
      <div className="mt-2 flex justify-between text-xs text-muted">
        <span>{dias[0].date}</span>
        <span className="tabular">
          pico {brl.format(maximo)}
        </span>
        <span>{dias[dias.length - 1].date}</span>
      </div>
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
