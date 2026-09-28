import Link from "next/link";

import { ApiError, getAbcPareto, getCohortProduto, type AbcLinha, type ClasseAbc, type CohortLinha } from "@/lib/api";

import { GraficoPareto } from "./grafico-pareto";

/**
 * Produtos — curva ABC de Pareto e cohort de lançamento.
 *
 * Responde duas perguntas: quais produtos sustentam o faturamento (Pareto +
 * classes A/B/C) e se produto novo segura receita depois do pico de
 * lançamento ou só dá um estouro e desaparece (cohort).
 *
 * Os dois vêm de `/segmentation/abc` e `/segmentation/cohort` — nenhuma
 * query nova, os endpoints já existem e estão testados desde a Sprint 1.
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

const pct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

export default async function ProdutosPage({
  searchParams,
}: PageProps<"/dashboard/produtos">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let abc: AbcLinha[] = [];
  let cohort: CohortLinha[] = [];
  let erro: string | null = null;

  try {
    [abc, cohort] = await Promise.all([getAbcPareto(de, ate), getCohortProduto(de, ate)]);
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
          <h1 className="text-2xl font-semibold tracking-tight">Produtos</h1>
          <p className="mt-1 text-sm text-muted">
            Quais produtos sustentam o faturamento, e quais só ocupam espaço.
          </p>
        </div>
        <SeletorPeriodo de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : abc.length === 0 ? (
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
          <CartoesClasse abc={abc} />

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Curva ABC de Pareto</h2>
            <p className="mt-0.5 text-xs text-muted">
              Receita por produto, em ordem decrescente, com o percentual acumulado.
            </p>
            <GraficoPareto dados={abc} />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Produtos</h2>
            <p className="mt-0.5 text-xs text-muted">{abc.length} produtos no período</p>
            <TabelaProdutos abc={abc} />
          </section>

          <section className="mt-6 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Cohort de lançamento</h2>
            <p className="mt-0.5 text-xs text-muted">
              Receita de cada leva de produtos (agrupados pelo mês da primeira venda) em
              cada mês corrente. Mostra se produto novo segura receita depois do mês de
              lançamento ou só dá um pico e some.
            </p>
            <Cohort linhas={cohort} />
          </section>
        </>
      )}
    </>
  );
}

/** Classe A/B/C é ordinal — uma fronteira acumulada, não uma categoria solta.
 *  Por isso usa uma única família de cor (accent) em três intensidades já
 *  tokenizadas, em vez de três matizes diferentes: A sólido, B no tom suave
 *  já existente (`accent-soft`), C neutro. Nenhum hex novo. */
function estiloClasse(classe: ClasseAbc): string {
  switch (classe) {
    case "A":
      return "bg-accent text-white";
    case "B":
      return "bg-accent-soft text-accent";
    case "C":
      return "bg-surface text-muted border border-line";
  }
}

function CartoesClasse({ abc }: { abc: AbcLinha[] }) {
  const total = abc.reduce((acc, l) => acc + l.receita, 0);
  const classes: ClasseAbc[] = ["A", "B", "C"];

  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-3">
      {classes.map((classe) => {
        const linhas = abc.filter((l) => l.classe === classe);
        const receita = linhas.reduce((acc, l) => acc + l.receita, 0);
        const participacao = total > 0 ? (100 * receita) / total : 0;

        return (
          <div key={classe} className="rounded-xl border border-line p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-muted">
                Classe {classe}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${estiloClasse(classe)}`}>
                {linhas.length} {linhas.length === 1 ? "produto" : "produtos"}
              </span>
            </div>
            <p className="tabular mt-2 text-3xl font-semibold">{brl.format(receita)}</p>
            <p className="tabular mt-1 text-xs text-muted">
              {pct.format(participacao)}% da receita do período
            </p>
          </div>
        );
      })}
    </div>
  );
}

function TabelaProdutos({ abc }: { abc: AbcLinha[] }) {
  return (
    <div className="mt-4 max-h-[28rem] overflow-y-auto rounded-lg border border-line">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">SKU</th>
            <th className="px-3 py-2 font-medium">Título</th>
            <th className="px-3 py-2 font-medium text-right">Receita</th>
            <th className="px-3 py-2 font-medium text-right">% receita</th>
            <th className="px-3 py-2 font-medium text-right">% acumulado</th>
            <th className="px-3 py-2 font-medium">Classe</th>
          </tr>
        </thead>
        <tbody>
          {abc.map((linha) => (
            <tr key={linha.sku} className="border-t border-line">
              <td className="px-3 py-2 text-muted">{linha.sku}</td>
              <td className="max-w-xs truncate px-3 py-2">{linha.titulo}</td>
              <td className="tabular px-3 py-2 text-right">{brl.format(linha.receita)}</td>
              <td className="tabular px-3 py-2 text-right">{pct.format(linha.receita_pct)}%</td>
              <td className="tabular px-3 py-2 text-right">
                {pct.format(linha.receita_acumulada_pct)}%
              </td>
              <td className="px-3 py-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${estiloClasse(linha.classe)}`}
                >
                  {linha.classe}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Heatmap de cohort em CSS grid — decisão travada da Sprint 3 (grid em vez
 * de lib de gráfico: é uma matriz, não uma série contínua).
 *
 * `null` vs `0`: o backend manda `null` onde a combinação não existe (mês
 * corrente antes do lançamento, estruturalmente impossível, OU cohort sem
 * nenhuma venda naquele mês — o pivot do pandas não distingue as duas) e um
 * número onde existe alguma receita agregada, que pode legitimamente
 * arredondar pra 0,00 num item de preço muito baixo. Célula vazia e célula
 * de valor zero têm que parecer coisas diferentes, senão os dois casos se
 * confundem visualmente.
 */
function Cohort({ linhas }: { linhas: CohortLinha[] }) {
  if (linhas.length === 0) {
    return (
      <p className="mt-4 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
        Nenhum produto com histórico de lançamento neste período.
      </p>
    );
  }

  const lancamentos = Array.from(new Set(linhas.map((l) => l.mes_lancamento))).sort();
  const correntesSet = new Set<string>();
  linhas.forEach((l) =>
    Object.keys(l).forEach((chave) => {
      if (chave !== "mes_lancamento") correntesSet.add(chave);
    }),
  );
  const correntes = Array.from(correntesSet).sort();

  const porLancamento = new Map(linhas.map((l) => [l.mes_lancamento, l]));
  const valores = linhas.flatMap((l) =>
    correntes.map((c) => l[c]).filter((v): v is number => typeof v === "number"),
  );
  const maximo = Math.max(...valores, 1);

  return (
    <div className="mt-4 overflow-x-auto">
      <div
        className="grid min-w-max gap-1"
        style={{
          gridTemplateColumns: `8rem repeat(${correntes.length}, minmax(4.5rem, 1fr))`,
        }}
      >
        <div />
        {correntes.map((c) => (
          <div key={c} className="px-1 pb-2 text-center text-xs font-medium text-muted">
            {formatarMes(c)}
          </div>
        ))}

        {lancamentos.map((lancamento) => {
          const linha = porLancamento.get(lancamento);
          return (
            <FragmentoLinha
              key={lancamento}
              lancamento={lancamento}
              linha={linha}
              correntes={correntes}
              maximo={maximo}
            />
          );
        })}
      </div>

      <div className="mt-3 flex items-center gap-3 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "color-mix(in srgb, var(--sp-accent) 80%, white)" }}
          />
          mais receita
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "color-mix(in srgb, var(--sp-accent) 10%, white)" }}
          />
          menos receita
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-sm border border-dashed border-line" />
          sem venda possível (antes do lançamento)
        </span>
      </div>
    </div>
  );
}

function FragmentoLinha({
  lancamento,
  linha,
  correntes,
  maximo,
}: {
  lancamento: string;
  linha: CohortLinha | undefined;
  correntes: string[];
  maximo: number;
}) {
  return (
    <>
      <div className="flex items-center px-1 text-xs font-medium text-muted">
        {formatarMes(lancamento)}
      </div>
      {correntes.map((corrente) => {
        const valor = linha?.[corrente];
        const numerico = typeof valor === "number" ? valor : null;
        return (
          <CelulaCohort key={corrente} valor={numerico} maximo={maximo} />
        );
      })}
    </>
  );
}

function CelulaCohort({ valor, maximo }: { valor: number | null; maximo: number }) {
  if (valor === null) {
    return (
      <div
        className="flex h-10 items-center justify-center rounded border border-dashed border-line text-xs text-muted"
        title="Sem venda possível (mês anterior ao lançamento)"
      >
        —
      </div>
    );
  }

  const intensidade = Math.max(6, Math.min(100, Math.round((valor / maximo) * 100)));
  return (
    <div
      className="tabular flex h-10 items-center justify-center rounded text-xs font-medium"
      style={{ backgroundColor: `color-mix(in srgb, var(--sp-accent) ${intensidade}%, white)` }}
      title={brl.format(valor)}
    >
      {brl.format(valor)}
    </div>
  );
}

function formatarMes(mes: string): string {
  const [ano, mesNumero] = mes.split("-");
  const data = new Date(Number(ano), Number(mesNumero) - 1, 1);
  return new Intl.DateTimeFormat("pt-BR", { month: "short", year: "2-digit" }).format(data);
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
