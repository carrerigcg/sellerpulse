import type { CohortLinha } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

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
 *
 * Compartilhado entre `/dashboard/produtos` e `/demo/produtos` desde o
 * Checkpoint 2 da Sprint 3.
 */
export function CohortHeatmap({ linhas }: { linhas: CohortLinha[] }) {
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
        return <CelulaCohort key={corrente} valor={numerico} maximo={maximo} />;
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
