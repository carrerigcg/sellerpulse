import type { FluxoDia } from "@/lib/api";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/**
 * Gráfico de barras em SVG, sem biblioteca.
 *
 * Para uma série diária de uma métrica só, 30 linhas de SVG resolvem e
 * evitam somar uma dependência ao bundle.
 *
 * Compartilhado entre `/dashboard` e `/demo` (visão Executive) desde o
 * Checkpoint 2 da Sprint 3.
 */
export function FlowChart({ dias }: { dias: FluxoDia[] }) {
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
        <span className="tabular">pico {brl.format(maximo)}</span>
        <span>{dias[dias.length - 1].date}</span>
      </div>
    </div>
  );
}
