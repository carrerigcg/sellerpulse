import Link from "next/link";

import { Wordmark } from "@/components/brand";

/**
 * Cabeçalho da landing: logo, "Ver demonstração" e um "Entrar" discreto.
 *
 * Sem botão de cadastro aqui de propósito — os pontos de cadastro moram
 * dentro da rolagem (seções 1, 3, 5 e 7), não no cabeçalho. Repetir o CTA
 * no topo empataria com eles e diluiria qual botão é "o" botão de cada
 * seção.
 *
 * Quem já tem sessão vê "Ir pro dashboard" no lugar de "Entrar" — a landing
 * não esconde o produto de quem já é cliente, só não pula pra lá sozinha.
 */
export function LandingHeader({ loggedIn }: { loggedIn: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="shrink-0">
          <Wordmark className="text-lg" />
        </Link>
        <nav className="flex items-center gap-4 sm:gap-6">
          <Link
            href="/demo"
            className="text-sm font-medium text-muted transition hover:text-ink"
          >
            Ver demonstração
          </Link>
          {loggedIn ? (
            <Link
              href="/dashboard"
              className="rounded-lg bg-accent px-3.5 py-1.5 text-sm font-medium text-white transition hover:bg-accent-hover"
            >
              Ir pro dashboard
            </Link>
          ) : (
            <Link
              href="/login"
              className="text-sm font-medium text-muted transition hover:text-ink"
            >
              Entrar
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
