import { PeriodPicker } from "@/components/analytics/period-picker";
import { TabelaCustos } from "@/components/analytics/tabela-custos";
import { ApiError, getCustos, type CustoLinha } from "@/lib/api";
import { coberturaInformada } from "@/lib/cobertura";

/**
 * Tela de Custos — onde o vendedor informa quanto cada produto custa a ele.
 *
 * É o que faz a margem de contribuição passar a ser verdade. Até esta tela
 * existir, o número era `receita − comissão − frete`: faltava o maior custo
 * variável de todos, o da mercadoria, então não era uma margem parcial — era
 * uma margem errada para mais.
 *
 * A janela serve para escolher QUAIS produtos aparecem (os vendidos no
 * período) e com que receita, não para escolher a vigência: o que se digita
 * aqui passa a valer de hoje em diante. Editar o passado é outra tela, e por
 * ora não existe.
 */

function periodoPadrao() {
  const hoje = new Date();
  const noventaDiasAtras = new Date(hoje);
  noventaDiasAtras.setDate(hoje.getDate() - 90);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { de: fmt(noventaDiasAtras), ate: fmt(hoje) };
}

export default async function CustosPage({ searchParams }: PageProps<"/dashboard/custos">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let linhas: CustoLinha[] = [];
  let erro: string | null = null;

  try {
    linhas = await getCustos(de, ate);
  } catch (e) {
    erro =
      e instanceof ApiError && e.status === 401
        ? "Sua sessão expirou. Entre de novo."
        : "Não foi possível carregar os produtos. O backend está no ar?";
  }

  const cobertura = coberturaInformada(linhas);
  const comCusto = linhas.filter((l) => l.custo_unitario !== null).length;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Custos</h1>
          <p className="mt-1 text-sm text-muted">
            Quanto cada produto custa a você. É o que falta para a margem ser a margem.
          </p>
        </div>
        <PeriodPicker de={de} ate={ate} />
      </div>

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : linhas.length === 0 ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum produto vendido neste período. Escolha uma janela com vendas para informar custos.
        </p>
      ) : (
        <>
          <section className="mt-6 rounded-xl border border-line bg-surface p-5">
            <h2 className="text-sm font-semibold">
              {comCusto} de {linhas.length}{" "}
              {linhas.length === 1 ? "produto com custo" : "produtos com custo informado"}
            </h2>
            <p className="mt-0.5 text-xs text-muted">
              {cobertura.completa
                ? "Todo o faturamento do período está coberto: a margem já desconta o custo dos produtos."
                : `Isso cobre ${cobertura.pct}% da receita do período. O que falta aparece como receita sem custo nas outras telas.`}
            </p>
          </section>

          <section className="mt-4 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Produtos vendidos no período</h2>
            <p className="mt-0.5 text-xs text-muted">
              Em ordem de receita, que é a ordem em que informar o custo muda mais a conta. O valor
              salva sozinho ao sair do campo e passa a valer de hoje em diante — a margem dos meses
              já fechados não muda. Campo vazio significa &ldquo;não informado&rdquo;, que é
              diferente de zero.
            </p>
            <div className="mt-4">
              <TabelaCustos linhas={linhas} />
            </div>
          </section>
        </>
      )}
    </>
  );
}
