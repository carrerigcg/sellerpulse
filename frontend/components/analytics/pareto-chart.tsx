"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AbcLinha } from "@/lib/api";

/**
 * Curva de Pareto: barras de receita por produto (a ordem já vem decrescente
 * do backend) com o percentual acumulado sobreposto num segundo eixo.
 *
 * É o gráfico clássico de Pareto, e é uma exceção deliberada à regra geral
 * de "um eixo só": a linha não é uma métrica independente disputando espaço
 * com a barra, é a soma corrida da própria barra — os dois eixos descrevem
 * o mesmo fenômeno em duas unidades (R$ e % acumulado), o que é exatamente
 * o que torna a regra 80/20 visível.
 *
 * Sem rótulo por produto no eixo X: em qualquer catálogo com mais de ~15
 * itens os rótulos colidem e viram ruído. Qual produto é aparece no tooltip.
 *
 * Compartilhado entre `/dashboard/produtos` (autenticado) e `/demo/produtos`
 * (público) desde o Checkpoint 2 da Sprint 3 — as duas telas mostram o
 * mesmo gráfico, só a fonte do dado muda.
 */

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

export function ParetoChart({ dados }: { dados: AbcLinha[] }) {
  return (
    <div className="mt-5">
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={dados} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--sp-border)" vertical={false} />
            <XAxis
              dataKey="sku"
              tick={false}
              axisLine={{ stroke: "var(--sp-border)" }}
              tickLine={false}
            />
            <YAxis
              yAxisId="receita"
              tickFormatter={(v: number) => brlCompacto.format(v)}
              tick={{ fill: "var(--sp-muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={56}
            />
            <YAxis
              yAxisId="pct"
              orientation="right"
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fill: "var(--sp-muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            <ReferenceLine
              yAxisId="pct"
              y={80}
              stroke="var(--sp-muted)"
              strokeDasharray="4 4"
              label={{ value: "80%", position: "insideTopRight", fill: "var(--sp-muted)", fontSize: 11 }}
            />
            <ReferenceLine
              yAxisId="pct"
              y={95}
              stroke="var(--sp-muted)"
              strokeDasharray="4 4"
              label={{ value: "95%", position: "insideTopRight", fill: "var(--sp-muted)", fontSize: 11 }}
            />
            <Tooltip content={<TooltipPareto />} cursor={{ fill: "var(--sp-surface)" }} />
            <Bar yAxisId="receita" dataKey="receita" fill="var(--sp-accent)" radius={[2, 2, 0, 0]} />
            <Line
              yAxisId="pct"
              dataKey="receita_acumulada_pct"
              stroke="var(--sp-text)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex items-center gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-sm bg-accent" /> Receita por produto
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-0 w-3 border-t-2"
            style={{ borderColor: "var(--sp-text)" }}
          />
          % acumulado
        </span>
      </div>
    </div>
  );
}

function TooltipPareto({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: AbcLinha }>;
}) {
  if (!active || !payload || !payload.length) return null;
  const linha = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">{linha.titulo}</p>
      <p className="text-muted">{linha.sku}</p>
      <p className="tabular mt-1">
        {brl.format(linha.receita)} · classe {linha.classe}
      </p>
      <p className="tabular text-muted">
        {linha.receita_acumulada_pct.toFixed(1)}% acumulado
      </p>
    </div>
  );
}
