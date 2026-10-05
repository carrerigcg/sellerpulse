"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { GRUPOS_DEMO } from "@/components/nav/itens";
import { Sidebar } from "@/components/nav/sidebar";

/**
 * Casca client que monta o `<Sidebar>` da demonstração.
 *
 * Existe pelo mesmo motivo de `app/dashboard/navegacao.tsx`: `grupos` carrega
 * componentes de ícone e `rodape` é função, e função não atravessa a fronteira
 * entre Server e Client Component. Montar o `<Sidebar>` direto no layout
 * derruba a página — e o `npm run build` passa assim mesmo, porque estas rotas
 * são dinâmicas e nunca são renderizadas no build.
 */
export function NavegacaoDemo({ children }: { children: ReactNode }) {
  return (
    <Sidebar
      grupos={GRUPOS_DEMO}
      rodape={(comRotulos) => (
        <div className="flex flex-col gap-2">
          <Link
            href="/signup"
            title="Criar conta grátis"
            /* O tamanho do botão também tem três situações, e medir foi o que
               mostrou isso. No trilho a caixa útil é de 39px (64 do `md:w-16`
               menos os 12+12 do `p-3`), e "Criar" em `text-sm` ocupa 31,8px —
               que com os 24px do `px-3` dá 56px e faz a última letra ser
               desenhada fora da pílula laranja. Em `text-xs` com `px-1` o
               conjunto fecha em 35,3px e sobra folga.

               O `xl:` devolve o tamanho cheio na faixa de rótulos; o ramo de
               `comRotulos` existe porque na gaveta o `xl:` nunca vale e lá o
               botão tem largura de sobra. Mesmo motivo do `Monograma` no
               lugar do `Wordmark` no trilho. */
            className={`rounded-lg bg-accent py-2 text-center font-medium text-white transition hover:bg-accent-hover ${
              comRotulos ? "px-3 text-sm" : "px-1 text-xs xl:px-3 xl:text-sm"
            }`}
          >
            {/* Três situações, não duas. `comRotulos` é `true` só na gaveta;
                dentro do `<aside>` quem distingue trilho de rótulos continua
                sendo o `xl:`. */}
            {comRotulos ? (
              "Criar conta grátis"
            ) : (
              <>
                <span className="xl:hidden">Criar</span>
                <span className="hidden xl:inline">Criar conta grátis</span>
              </>
            )}
          </Link>
          <Link
            href="/login"
            className={`px-1 text-xs text-muted transition hover:text-ink ${
              comRotulos ? "block" : "hidden xl:block"
            }`}
          >
            Entrar
          </Link>
        </div>
      )}
    >
      {children}
    </Sidebar>
  );
}
