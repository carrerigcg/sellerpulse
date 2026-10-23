import type { ChaveDeTutorial } from "@/lib/tutoriais";

import { PeriodPicker } from "./period-picker";
import { TutorialDaTela } from "./tutorial-da-tela";

/**
 * Título, subtítulo, tutorial e seletor de período — o topo das dez telas de
 * análise.
 *
 * As dez páginas (cinco do dashboard, cinco da demo) repetiam este bloco byte
 * a byte, variando só o texto. Em Produtos, demo e dashboard eram idênticos
 * até no subtítulo.
 *
 * É Server Component, e as props são dado puro de propósito — texto e um
 * booleano: o `TutorialDaTela` é Client, e o que chega até ele precisa
 * atravessar a fronteira. Se um dia este componente virar
 * `"use client"` ou receber função como prop, o erro só aparece em execução —
 * as rotas são dinâmicas e o `build` não as renderiza.
 *
 * O tutorial mora aqui, e não no layout, para ficar fora da vitrine e de
 * `/dashboard/conectar` por construção: só estas dez páginas usam este
 * cabeçalho. `temDados` vem da página porque só ela sabe se a tela está vazia
 * ou com erro — e o tutorial não abre sozinho sobre nenhuma das duas. As
 * páginas usam o mesmo `temDados` no próprio ramo de vazio: escrito duas
 * vezes, mudar a regra de vazio deixaria o tutorial para trás.
 */
export function CabecalhoDeTela({
  titulo,
  subtitulo,
  de,
  ate,
  tela,
  temDados,
  chegouFiltrado = false,
}: {
  titulo: string;
  subtitulo: string;
  de: string;
  ate: string;
  tela: ChaveDeTutorial;
  temDados: boolean;
  /** Veio por um atalho que já filtra a tela — ver `deveAbrirSozinho`. */
  chegouFiltrado?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        <p className="mt-1 text-sm text-muted">{subtitulo}</p>
        {/* `-ml-2` desfaz o `px-2` do botão: o ícone alinha com o texto de cima. */}
        <div className="-ml-2 mt-1">
          <TutorialDaTela tela={tela} temDados={temDados} chegouFiltrado={chegouFiltrado} />
        </div>
      </div>
      <PeriodPicker de={de} ate={ate} />
    </div>
  );
}
