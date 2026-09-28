import type { AbcLinha } from "@/lib/api";

import { abcClassBadgeClass } from "./abc-class-badge";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const pct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

/** Tabela por produto — sku, título, receita, participação, classe. */
export function AbcTable({ abc }: { abc: AbcLinha[] }) {
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
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${abcClassBadgeClass(linha.classe)}`}
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
