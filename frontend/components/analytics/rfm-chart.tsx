"use client";

import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { RfmLinha } from "@/lib/api";

import { definicaoSegmento } from "./segmentos";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const brlCompacto = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

/**
 * Dispersão RFM: recência no eixo X, valor no Y, frequência no tamanho do
 * ponto, segmento na cor. Quem está embaixo à direita — comprou há muito
 * tempo e gasta pouco — é quem está indo embora.
 *
 * Um `Scatter` só com uma `Cell` por ponto, em vez de um `Scatter` por
 * segmento: com múltiplas séries cada uma geraria sua própria entrada de
 * legenda automática, duplicando a faixa de segmentos que já existe embaixo
 * do gráfico. A ordem das `Cell` casa com a ordem de `dados` — é assim que
 * o Recharts liga cada célula ao ponto de mesmo índice.
 *
 * Compartilhado entre `/dashboard/clientes` e `/demo/clientes` desde o
 * Checkpoint 2 da Sprint 3.
 */
export function RfmChart({ dados }: { dados: RfmLinha[] }) {
  const maxRecencia = Math.max(...dados.map((d) => d.recency_dias), 1);
  const maxMonetary = Math.max(...dados.map((d) => d.monetary), 1);

  return (
    <div className="mt-5 h-96 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 24 }}>
          <CartesianGrid stroke="var(--sp-border)" />
          <XAxis
            type="number"
            dataKey="recency_dias"
            domain={[0, Math.ceil(maxRecencia * 1.1)]}
            tick={{ fill: "var(--sp-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--sp-border)" }}
            tickLine={false}
            label={{
              value: "Dias desde a última compra",
              position: "insideBottom",
              offset: -10,
              fill: "var(--sp-muted)",
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="monetary"
            domain={[0, Math.ceil(maxMonetary * 1.1)]}
            tickFormatter={(v: number) => brlCompacto.format(v)}
            tick={{ fill: "var(--sp-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={56}
          />
          <ZAxis dataKey="frequency" range={[50, 500]} />
          <Tooltip content={<TooltipRfm />} cursor={{ stroke: "var(--sp-border)" }} />
          <Scatter data={dados} isAnimationActive={false}>
            {dados.map((linha) => {
              const def = definicaoSegmento(linha.segmento);
              return (
                <Cell
                  key={linha.buyer_id}
                  fill={def.corGrafico}
                  stroke={def.contornoGrafico ?? def.corGrafico}
                  strokeWidth={def.contornoGrafico ? 1.5 : 0}
                  fillOpacity={0.8}
                />
              );
            })}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function TooltipRfm({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: RfmLinha }>;
}) {
  if (!active || !payload || !payload.length) return null;
  const linha = payload[0].payload;
  const def = definicaoSegmento(linha.segmento);
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">{def.rotulo}</p>
      <p className="tabular text-muted">{linha.recency_dias} dias sem comprar</p>
      <p className="tabular">
        {brl.format(linha.monetary)} · {linha.frequency}x
      </p>
      <p className="tabular text-muted">
        R{linha.r_score} F{linha.f_score} M{linha.m_score}
      </p>
    </div>
  );
}
