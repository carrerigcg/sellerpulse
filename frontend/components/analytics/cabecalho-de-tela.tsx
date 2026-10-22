import { PeriodPicker } from "./period-picker";

/**
 * Título, subtítulo e seletor de período — o topo das dez telas de análise.
 *
 * As dez páginas (cinco do dashboard, cinco da demo) repetiam este bloco byte
 * a byte, variando só o texto. Em Produtos, demo e dashboard eram idênticos
 * até no subtítulo.
 *
 * É Server Component, e as quatro props são texto de propósito: o
 * `PeriodPicker` é Client, e o que chega até ele precisa ser dado puro. Se um
 * dia este componente virar `"use client"` ou receber função como prop, o erro
 * só aparece em execução — as rotas são dinâmicas e o `build` não as renderiza.
 */
export function CabecalhoDeTela({
  titulo,
  subtitulo,
  de,
  ate,
}: {
  titulo: string;
  subtitulo: string;
  de: string;
  ate: string;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        <p className="mt-1 text-sm text-muted">{subtitulo}</p>
      </div>
      <PeriodPicker de={de} ate={ate} />
    </div>
  );
}
