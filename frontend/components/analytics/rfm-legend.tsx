import { SEGMENTOS } from "./segmentos";

/** Legenda de cores do gráfico de dispersão RFM. */
export function RfmLegend() {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
      {SEGMENTOS.map((def) => (
        <span key={def.chave} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{
              backgroundColor: def.contornoGrafico ? "transparent" : def.corGrafico,
              border: def.contornoGrafico ? `1.5px solid ${def.contornoGrafico}` : undefined,
            }}
          />
          {def.rotulo}
        </span>
      ))}
    </div>
  );
}
