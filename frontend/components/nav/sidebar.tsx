"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Monograma, Wordmark } from "@/components/brand";

import { IconeFechar, IconeMenu } from "./icones";
import type { GrupoDeNavegacao } from "./itens";

/**
 * Navegação lateral, compartilhada por `/dashboard` e `/demo`.
 *
 * Três estágios, e o do meio é o que justifica a sidebar neste produto:
 *
 *   < md (768)      gaveta atrás de um botão
 *   md–xl           trilho de 64px, só ícones
 *   >= xl (1280)    224px com rótulos
 *
 * O trilho existe porque o conteúdo aqui é largo — tabelas de seis colunas e
 * a curva de Pareto usam os 1152px do `max-w-6xl`. Num notebook de 1366 uma
 * sidebar de 224px deixaria 1126px e apertaria justamente as telas que
 * funcionam bem; o trilho deixa 1302px e não tira nada.
 *
 * Client Component por dois motivos: `usePathname`, para marcar o item ativo,
 * e o estado da gaveta.
 */
export function Sidebar({
  grupos,
  rodape,
  children,
}: {
  grupos: GrupoDeNavegacao[];
  /**
   * Função, e não `ReactNode`, pelo mesmo motivo de `comRotulos` em
   * `renderNavegacao`: o rodapé é renderizado nos dois lugares, e a gaveta
   * só existe abaixo de 768 — então um `xl:` escrito aqui dentro nunca vale
   * lá. Um nó único com `hidden xl:block` sumiria justamente na gaveta, que
   * é onde há mais espaço. Simplificar de volta é que seria o defeito.
   */
  rodape: (comRotulos: boolean) => ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [aberta, setAberta] = useState(false);
  const painel = useRef<HTMLDivElement>(null);
  const botaoAbrir = useRef<HTMLButtonElement>(null);

  // Fecha ao trocar de rota. Sem isto a gaveta fica aberta por cima da tela
  // nova depois de cada clique — o jeito mais rápido de a navegação parecer
  // quebrada.
  //
  // Isto é ajuste de estado durante o render, e não um `useEffect`, porque a
  // regra `react-hooks/set-state-in-effect` (eslint-plugin-react-hooks 7)
  // barra `setState` no corpo de um efeito — e o `eslint-disable` não a
  // silencia, por ser regra do compilador e não do parser. O padrão abaixo é
  // o que a doc do React recomenda para "ajustar estado quando uma prop
  // muda": compara com o valor do render anterior e corrige na hora. De
  // brinde, fecha no mesmo render em que a rota troca, sem o quadro
  // intermediário com a gaveta ainda aberta que o efeito deixava passar.
  const [rotaDaGaveta, setRotaDaGaveta] = useState(pathname);
  if (rotaDaGaveta !== pathname) {
    setRotaDaGaveta(pathname);
    setAberta(false);
  }

  // Escape fecha, e a rolagem do fundo trava enquanto está aberta. Sem a
  // trava, arrastar na gaveta rola a página atrás dela.
  useEffect(() => {
    if (!aberta) return;

    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") setAberta(false);
    }
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", aoTeclar);
    painel.current?.focus();

    // `botaoAbrir.current` é lido agora, na montagem do efeito, e não dentro
    // da limpeza: o ESLint avisa, com razão, que o `.current` pode ter
    // mudado quando a limpeza roda.
    const abriu = botaoAbrir.current;

    return () => {
      document.body.style.overflow = overflowAnterior;
      document.removeEventListener("keydown", aoTeclar);
      // Devolve o foco a quem abriu — senão ele volta pro início da página.
      abriu?.focus();
    };
  }, [aberta]);

  /**
   * `comRotulos` é parâmetro e não classe CSS de propósito.
   *
   * A tentação é renderizar uma vez e sobrescrever com variante arbitrária
   * (`[&_p]:block`) dentro da gaveta. Não funciona de forma confiável:
   * `hidden` e `block` têm a mesma especificidade, então quem vence depende
   * da ordem no stylesheet gerado — que muda sem aviso entre builds. Passar
   * a decisão explícita custa um parâmetro e é determinístico.
   */
  const renderNavegacao = (comRotulos: boolean) => (
    <nav className="flex flex-1 flex-col gap-6 overflow-y-auto">
      {grupos.map((grupo, i) => (
        <div key={grupo.titulo ?? `grupo-${i}`}>
          {grupo.titulo && (
            <p
              className={`px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-muted ${
                comRotulos ? "block" : "hidden xl:block"
              }`}
            >
              {grupo.titulo}
            </p>
          )}
          <ul className="flex flex-col gap-1">
            {grupo.itens.map((item) => {
              const ativa = item.exata
                ? pathname === item.href
                : pathname.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={ativa ? "page" : undefined}
                    // `title` é o que dá o rótulo no trilho, onde o texto
                    // está escondido. Sem ele, o ícone sozinho é adivinhação.
                    title={item.rotulo}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      ativa ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface hover:text-ink"
                    }`}
                  >
                    <item.Icone />
                    <span className={`truncate ${comRotulos ? "" : "sr-only xl:not-sr-only"}`}>
                      {item.rotulo}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      {/* Sidebar fixa — some abaixo de md, onde vira gaveta. */}
      <aside className="hidden shrink-0 flex-col gap-6 border-r border-line p-3 md:flex md:w-16 xl:w-56 xl:p-4">
        {/* No trilho a marca é o monograma: o `Wordmark` tem 83px e o trilho
            oferece 40 de área útil, então ele vazava a borda por cima do
            conteúdo. Aqui o `xl:` é a ferramenta certa pelo mesmo motivo do
            rodapé — o `<aside>` é um elemento só atravessando trilho e
            rótulos, e `comRotulos` não distingue os dois. */}
        <div className="flex h-10 items-center justify-center xl:justify-start xl:px-2">
          <Monograma className="text-base xl:hidden" />
          <Wordmark className="hidden text-base xl:inline" />
        </div>
        {renderNavegacao(false)}
        <div className="border-t border-line pt-3">{rodape(false)}</div>
      </aside>

      {/*
        `inert` no conteúdo enquanto a gaveta está aberta. É o jeito limpo de
        prender o foco: o navegador tira tudo que está atrás da ordem de
        tabulação, sem código de ciclagem de Tab.

        Em React 19 o atributo é booleano (`inert?: boolean` em
        @types/react 19.3.0) e sai como atributo vazio no DOM quando `true`,
        então `inert={aberta}` já diz tudo — não precisa de spread condicional.
      */}
      <div className="flex min-w-0 flex-1 flex-col" inert={aberta}>
        {/* Cabeçalho só do celular: abre a gaveta e mostra a marca. */}
        <header className="flex h-14 items-center gap-3 border-b border-line px-4 md:hidden">
          <button
            ref={botaoAbrir}
            type="button"
            onClick={() => setAberta(true)}
            aria-label="Abrir navegação"
            aria-expanded={aberta}
            className="rounded-lg p-1.5 text-muted transition hover:bg-surface hover:text-ink"
          >
            <IconeMenu />
          </button>
          {/* No celular e na gaveta cabe a marca inteira: não é trilho. */}
          <Wordmark className="text-base" />
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
      </div>

      {aberta && (
        <>
          <button
            type="button"
            aria-label="Fechar navegação"
            onClick={() => setAberta(false)}
            className="fixed inset-0 z-40 bg-ink/40 md:hidden"
          />
          <div
            ref={painel}
            role="dialog"
            aria-modal="true"
            aria-label="Navegação"
            tabIndex={-1}
            className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col gap-6 border-r border-line bg-bg p-4 outline-none md:hidden"
          >
            <div className="flex items-center justify-between">
              <Wordmark className="text-base" />
              <button
                type="button"
                onClick={() => setAberta(false)}
                aria-label="Fechar navegação"
                className="rounded-lg p-1.5 text-muted transition hover:bg-surface hover:text-ink"
              >
                <IconeFechar />
              </button>
            </div>
            {/* Dentro da gaveta os rótulos sempre aparecem: não é trilho. */}
            {renderNavegacao(true)}
            <div className="border-t border-line pt-3">{rodape(true)}</div>
          </div>
        </>
      )}
    </div>
  );
}
