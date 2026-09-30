/**
 * Seção 2 — o problema. Sem CTA (ver tabela da spec): esta seção só
 * justifica por que alguém deveria continuar rolando.
 *
 * A "planilha" à direita é uma ilustração da forma do problema, não um
 * dado real — os SKUs e valores são de exemplo, coerente com a restrição
 * de honestidade (nada de prova social inventada). O "?" no lugar do lucro
 * é o ponto inteiro da seção: a planilha mostra o que entrou, não o que
 * sobrou.
 */

const PERGUNTAS = [
  "Qual produto sustenta o faturamento, e qual só ocupa espaço?",
  "Qual cliente comprou uma vez e sumiu?",
  "Quanto sobrou de verdade, depois da comissão e dos cancelamentos?",
];

export function Problem() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <div className="grid gap-12 lg:grid-cols-2 lg:items-center lg:gap-16">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Uma planilha no fim do mês não diz qual produto dá lucro.
          </h2>
          <p className="mt-4 text-lg text-muted">
            Ela mostra o que entrou — não o que sobrou depois da comissão e dos
            cancelamento. E não avisa quando um cliente bom para de comprar.
          </p>
          <ul className="mt-8 space-y-4">
            {PERGUNTAS.map((pergunta) => (
              <li key={pergunta} className="flex gap-3 text-base text-ink">
                <span className="mt-0.5 text-accent" aria-hidden>
                  →
                </span>
                {pergunta}
              </li>
            ))}
          </ul>
        </div>

        <SpreadsheetMockup />
      </div>
    </section>
  );
}

const LINHAS = [
  { sku: "MLB1004", receita: "R$ 892,10" },
  { sku: "MLB1007", receita: "R$ 1.240,00" },
  { sku: "MLB1002", receita: "R$ 340,55" },
  { sku: "MLB1011", receita: "R$ 2.108,90" },
  { sku: "MLB1003", receita: "R$ 128,00" },
];

function SpreadsheetMockup() {
  return (
    // `pt-7` (em vez de padding uniforme) reserva espaço só no topo pro
    // selo "?" flutuante não cobrir o cabeçalho "LUCRO" da tabela — as
    // duas primeiras tentativas cobriam parte do texto porque o selo e o
    // cabeçalho disputavam os mesmos 16px do canto superior direito.
    <div className="relative rounded-2xl border border-line bg-surface p-2 pt-7 shadow-sm">
      <div className="overflow-hidden rounded-xl border border-line bg-bg">
        <div className="grid grid-cols-3 border-b border-line bg-surface px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">
          <span>SKU</span>
          <span>Receita</span>
          <span className="text-right">Lucro</span>
        </div>
        {LINHAS.map(({ sku, receita }, i) => (
          <div
            key={sku}
            className={`grid grid-cols-3 px-4 py-3.5 text-sm ${i % 2 ? "bg-surface/60" : ""}`}
          >
            <span className="font-mono text-muted">{sku}</span>
            <span className="tabular text-ink">{receita}</span>
            <span className="text-right font-semibold text-negative">?</span>
          </div>
        ))}
      </div>
      <div
        className="absolute -top-4 -right-4 flex h-10 w-10 items-center justify-center rounded-full bg-negative text-lg font-bold text-white shadow-lg"
        aria-hidden
      >
        ?
      </div>
    </div>
  );
}
