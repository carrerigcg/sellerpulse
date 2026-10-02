import Link from "next/link";

import { Wordmark } from "@/components/brand";

import { DemoNav } from "./nav";

/**
 * Layout da demonstração pública — sem `createClient`/`getUser`: ao
 * contrário de `dashboard/layout.tsx`, esta árvore inteira não tem sessão
 * pra checar. É esse o ponto da demo.
 *
 * Três elementos fixos em toda tela: o aviso de que os dados são fictícios
 * (discreto, mas em toda página — não só na primeira), a navegação entre as
 * três telas, e um caminho visível de volta pro cadastro pra quem gostou do
 * que viu.
 */
export default function DemoLayout({ children }: LayoutProps<"/demo">) {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="border-b border-line bg-highlight/10 px-6 py-1.5 text-center text-xs text-muted">
        Você está vendo dados de demonstração fictícios, não uma loja real.
      </div>
      <header className="border-b border-line">
        {/* Duas linhas no celular, uma só a partir de `sm`.
            Em 375px a marca, a navegação e o botão de ação somam mais que a
            largura da tela, e quem era empurrado pra fora era justamente o
            "Criar conta grátis" — o caminho que esta tela existe pra oferecer.
            Por isso a navegação desce pra uma faixa própria embaixo (`order-3
            w-full`) e a ação sobe pro lado da marca. O `order` devolve a ordem
            original a partir de `sm`, então o desktop não muda: marca, nav e
            ações continuam na mesma linha, com os mesmos 24px de intervalo. */}
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-2.5 sm:h-14 sm:flex-nowrap sm:py-0">
          <Wordmark className="order-1 text-base" />
          <div className="order-2 ml-auto flex items-center gap-3 sm:order-3">
            <Link
              href="/login"
              className="hidden text-sm text-muted hover:text-ink sm:inline"
            >
              Entrar
            </Link>
            <Link
              href="/signup"
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-hover"
            >
              Criar conta grátis
            </Link>
          </div>
          <DemoNav className="order-3 w-full sm:order-2 sm:w-auto" />
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
