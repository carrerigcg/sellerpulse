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
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-6">
            <Wordmark className="text-base" />
            <DemoNav />
          </div>
          <div className="flex items-center gap-3">
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
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
