import type { AbcLinha, ClasseAbc } from "@/lib/api";

import { abcClassBadgeClass } from "./abc-class-badge";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const pct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

/** Três cartões (A/B/C): quantos produtos e quanta receita em cada classe. */
export function AbcClassCards({ abc }: { abc: AbcLinha[] }) {
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
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${abcClassBadgeClass(classe)}`}
              >
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
