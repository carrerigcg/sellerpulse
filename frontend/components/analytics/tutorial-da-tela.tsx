"use client";

import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";

import { IconeAjuda, IconeFechar } from "@/components/nav/icones";
import {
  TUTORIAIS,
  chaveDeArmazenamento,
  contextoDaRota,
  deveAbrirSozinho,
  slidesDoContexto,
  type ChaveDeTutorial,
} from "@/lib/tutoriais";

/**
 * O tutorial de uma tela de análise: o botão "Como usar esta tela" e o modal.
 *
 * `<dialog>` nativo com `showModal()`, e não um `div` como a gaveta da
 * navegação: foco preso, ESC e a camada superior do navegador vêm prontos,
 * sem disputar `z-index` com a gaveta. Conteúdo e regras moram em
 * `lib/tutoriais.ts`; aqui fica só o que precisa do navegador.
 *
 * As duas props são dado puro — texto e booleano — porque quem renderiza isto
 * é o `CabecalhoDeTela`, que é Server Component.
 *
 * Armadilha latente: se o `next.config` um dia ligar `cacheComponents`, a
 * rota anterior passa a ser escondida com `<Activity>` em vez de desmontada,
 * e um modal aberto na hora do "voltar" fica preso sobre a página inerte.
 * Ver a seção "Dialog" de `node_modules/next/dist/docs/01-app/02-guides/preserving-ui-state.md`.
 */
export function TutorialDaTela({
  tela,
  temDados,
  chegouFiltrado = false,
}: {
  tela: ChaveDeTutorial;
  temDados: boolean;
  chegouFiltrado?: boolean;
}) {
  const contexto = contextoDaRota(usePathname());
  const tutorial = TUTORIAIS[tela];
  const slides = slidesDoContexto(tutorial, contexto);
  const chave = chaveDeArmazenamento(contexto, tela, tutorial.versao);

  const [indice, setIndice] = useState(0);
  const dialogo = useRef<HTMLDialogElement>(null);
  const primario = useRef<HTMLButtonElement>(null);
  const voltar = useRef<HTMLButtonElement>(null);
  const pressionouNoFundo = useRef(false);
  const idTitulo = useId();
  const idTexto = useId();

  // Depois de montar, e não durante o render: no servidor não há
  // `localStorage`, e ler lá em cima daria uma resposta em cada lado — erro
  // de hidratação.
  useEffect(() => {
    let jaVisto = false;
    let armazenamentoDisponivel = true;
    try {
      jaVisto = localStorage.getItem(chave) !== null;
    } catch {
      armazenamentoDisponivel = false;
    }
    if (deveAbrirSozinho({ jaVisto, temDados, armazenamentoDisponivel, chegouFiltrado })) {
      abrir(dialogo.current, primario.current);
    }
  }, [chave, temDados, chegouFiltrado]);

  const ultimo = indice === slides.length - 1;

  function irPara(novo: number) {
    if (novo < 0 || novo >= slides.length) return;
    // O "Voltar" some no primeiro slide. Se o foco estava nele, cairia no
    // `<body>` com o modal aberto.
    if (novo === 0 && document.activeElement === voltar.current) primario.current?.focus();
    setIndice(novo);
  }

  // O único ponto por onde passam ✕, ESC, clique fora e "Entendi" — por isso
  // é aqui que marca como visto, e não em cada botão.
  function aoFechar() {
    setIndice(0);
    try {
      localStorage.setItem(chave, "1");
    } catch {
      // Sem armazenamento não há o que lembrar — e, pelo mesmo motivo, o
      // tutorial também não abre sozinho.
    }
  }

  function aoTeclar(e: KeyboardEvent<HTMLDialogElement>) {
    if (e.key === "ArrowRight") irPara(indice + 1);
    else if (e.key === "ArrowLeft") irPara(indice - 1);
  }

  // Com o `<dialog>` em `p-0` e o conteúdo num `div` interno que o preenche,
  // o alvo é o próprio diálogo quando o ponteiro está no fundo. Mas o `click`
  // vai para o ancestral comum de onde o botão desceu e de onde subiu: quem
  // seleciona o texto e arrasta até o fundo, ou aperta "Próximo", desiste e
  // solta fora, também chega aqui com alvo no diálogo. Só fecha se as duas
  // pontas foram no fundo.
  function aoClicar(e: MouseEvent<HTMLDialogElement>) {
    if (pressionouNoFundo.current && e.target === e.currentTarget) e.currentTarget.close();
  }

  // O segundo clique de um duplo clique cairia no slide seguinte — ou no
  // "Entendi", fechando antes de a pessoa ver o último. O botão fica parado
  // sob o cursor de propósito (ver o grid dos slides), então acontece. Pelo
  // teclado o `detail` é 0, e nada muda.
  function aoClicarNoPrincipal(e: MouseEvent<HTMLButtonElement>) {
    if (e.detail > 1) return;
    if (ultimo) dialogo.current?.close();
    else irPara(indice + 1);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => abrir(dialogo.current, primario.current)}
        aria-haspopup="dialog"
        className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm text-muted transition hover:bg-surface hover:text-ink"
      >
        <IconeAjuda className="h-4 w-4" />
        Como usar esta tela
      </button>

      <dialog
        ref={dialogo}
        aria-labelledby={idTitulo}
        aria-describedby={idTexto}
        onClose={aoFechar}
        onKeyDown={aoTeclar}
        onPointerDown={(e) => {
          pressionouNoFundo.current = e.target === e.currentTarget;
        }}
        onClick={aoClicar}
        className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-line bg-bg p-0 text-ink shadow-xl backdrop:bg-ink/40 backdrop:backdrop-blur-sm"
      >
        <div className="relative p-6">
          <button
            type="button"
            onClick={() => dialogo.current?.close()}
            aria-label="Fechar tutorial"
            className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center rounded-lg text-muted transition hover:bg-surface hover:text-ink"
          >
            <IconeFechar />
          </button>

          <div aria-live="polite">
            {slides.length > 1 && (
              <p className="pr-10 text-xs font-medium text-muted">
                Passo {indice + 1} de {slides.length}
              </p>
            )}
            {/* Todos os slides na mesma célula do grid, só o atual visível: a
                célula fica com a altura do maior, e o modal não muda de tamanho
                entre um e outro. Centralizado e com altura variável, ele
                crescia para cima e para baixo, e o "Próximo" fugia do cursor
                de quem clicava em sequência. */}
            <div className="grid">
              {slides.map((s, i) => {
                const atual = i === indice;
                return (
                  <div
                    key={i}
                    aria-hidden={!atual}
                    className={`col-start-1 row-start-1 ${
                      atual ? "motion-safe:animate-[tutorial-entra_150ms_ease-out]" : "invisible"
                    }`}
                  >
                    <h2
                      id={atual ? idTitulo : undefined}
                      className="mt-1 pr-10 text-lg font-semibold tracking-tight"
                    >
                      {s.titulo}
                    </h2>
                    <p id={atual ? idTexto : undefined} className="mt-2 text-sm leading-relaxed text-muted">
                      {s.texto}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3">
            {slides.length > 1 && (
              // Decorativo: o "Passo 2 de 3" acima já diz o mesmo em texto. A
              // largura marca o atual, para não depender só de cor.
              <div className="flex gap-1.5" aria-hidden>
                {slides.map((_, i) => (
                  <span
                    key={i}
                    className={`h-1.5 rounded-full motion-safe:transition-all ${
                      i === indice ? "w-4 bg-ink" : "w-1.5 bg-muted/50"
                    }`}
                  />
                ))}
              </div>
            )}
            <div className="ml-auto flex gap-2">
              {indice > 0 && (
                <button
                  ref={voltar}
                  type="button"
                  onClick={() => irPara(indice - 1)}
                  className="min-h-11 rounded-lg px-4 text-sm font-medium text-muted transition hover:bg-surface hover:text-ink"
                >
                  Voltar
                </button>
              )}
              <button
                ref={primario}
                type="button"
                onClick={aoClicarNoPrincipal}
                className="min-h-11 rounded-lg bg-accent px-5 text-sm font-medium text-white transition hover:bg-accent-hover"
              >
                {ultimo ? "Entendi" : "Próximo"}
              </button>
            </div>
          </div>
        </div>
      </dialog>
    </>
  );
}

/**
 * A guarda é para o StrictMode do desenvolvimento, que roda o efeito duas
 * vezes. O padrão atual ignora `showModal` num diálogo que já é modal, mas
 * versões anteriores lançavam `InvalidStateError` — a guarda não depende disso.
 *
 * O foco vai à mão para o botão principal: o `autoFocus` do React age na
 * montagem, quando o diálogo ainda está fechado, e sem isto o navegador
 * focaria o ✕, que vem antes no DOM.
 */
function abrir(dialogo: HTMLDialogElement | null, primario: HTMLButtonElement | null) {
  if (!dialogo || dialogo.open) return;
  dialogo.showModal();
  primario?.focus();
}
