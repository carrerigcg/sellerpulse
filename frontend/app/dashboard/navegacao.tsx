"use client";

import type { ReactNode } from "react";

import { GRUPOS_DASHBOARD } from "@/components/nav/itens";
import { Sidebar } from "@/components/nav/sidebar";

import { BotaoSair } from "./sair";

/**
 * Casca cliente da sidebar do dashboard.
 *
 * Este arquivo não estava no plano, e existe porque o código da Tarefa 3
 * montava o `<Sidebar>` direto em `layout.tsx`, que é Server Component. Duas
 * das props não atravessam a fronteira servidor→cliente:
 *
 *   - `grupos` carrega `Icone: ComponentType` em cada item, e função não
 *     serializa no payload do RSC;
 *   - `rodape` é `(comRotulos: boolean) => ReactNode`, ou seja, função também.
 *
 * O resultado era "Functions cannot be passed directly to Client Components"
 * e a tela inteira caindo em erro de servidor. `npm run build` passava: a
 * rota é dinâmica (`ƒ`), então nunca é renderizada em tempo de build, e o
 * TypeScript não modela essa restrição — ela é só de runtime.
 *
 * Com a chamada do `<Sidebar>` aqui dentro, as duas props viram
 * cliente→cliente e o problema desaparece. O que cruza a fronteira agora é
 * só `email` (string) e `children` (árvore já renderizada pelo servidor),
 * que é o padrão suportado.
 *
 * A verificação de sessão fica onde estava, em `layout.tsx`: ela é
 * server-only e não pode descer pra cá.
 */
export function NavegacaoDashboard({
  email,
  children,
}: {
  email: string;
  children: ReactNode;
}) {
  return (
    <Sidebar
      grupos={GRUPOS_DASHBOARD}
      rodape={(comRotulos) => (
        <div className="flex flex-col gap-2">
          {/* `comRotulos` quer dizer "tenho rótulos garantidos", e é `true`
              SÓ na gaveta. Dentro do `<aside>` ele chega `false` até na
              faixa de rótulos, porque o `<aside>` é um elemento só que
              atravessa o trilho e os rótulos — lá quem distingue continua
              sendo o `xl:`.

              Por isso a classe e não um `{comRotulos && ...}`: esconder o
              email quando `comRotulos` é falso o apagaria também em 1440,
              onde ele aparece hoje. */}
          <span
            className={`truncate px-1 text-xs text-muted ${
              comRotulos ? "block" : "hidden xl:block"
            }`}
          >
            {email}
          </span>
          {/* Mesmo problema de largura do CTA da demo: "Sair" em `text-sm`
              com `px-3` não cabe nos 39px do trilho. Três situações de novo —
              o `xl:` resolve dentro do `<aside>`, o parâmetro resolve a
              gaveta. */}
          <BotaoSair className={comRotulos ? "px-3 text-sm" : "px-1 text-xs xl:px-3 xl:text-sm"} />
        </div>
      )}
    >
      {children}
    </Sidebar>
  );
}
