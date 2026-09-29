import type { RfmLinha } from "@/lib/api";

import { SEGMENTOS } from "./segmentos";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/** Faixa de segmentos — contagem e receita por Champions/Loyal/At Risk/... */
export function SegmentBand({ rfm }: { rfm: RfmLinha[] }) {
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
