const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/**
 * Cartão de KPI com variação sobre o período anterior.
 *
 * Compartilhado entre `/dashboard` e `/demo` (visão Executive) desde o
 * Checkpoint 2 da Sprint 3.
 */
export function KpiCard({
  rotulo,
  valor,
  anterior,
  subirEhRuim = false,
  nota,
}: {
  rotulo: string;
  valor: number;
  anterior: number;
  subirEhRuim?: boolean;
  /**
   * Linha de legenda discreta abaixo do valor — existe pro cartão de margem
   * de contribuição poder mostrar a própria fórmula, já que o termo é
   * vocabulário de contabilidade e o vendedor não deveria ter que procurar
   * o que significa.
   */
  nota?: string;
}) {
  const temBase = anterior !== 0;
  const pct = temBase ? (100 * (valor - anterior)) / anterior : 0;
  // Em custo, subir é resultado pior — o sinal da cor inverte.
  const bom = subirEhRuim ? pct < 0 : pct >= 0;

  return (
    <div className="rounded-xl border border-line p-5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted">{rotulo}</span>
      <p className="tabular mt-2 text-3xl font-semibold">{brl.format(valor)}</p>
      {nota && <p className="mt-1 text-xs text-muted">{nota}</p>}
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
