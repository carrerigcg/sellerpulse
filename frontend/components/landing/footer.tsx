import Link from "next/link";

import { Wordmark } from "@/components/brand";

export function LandingFooter() {
  return (
    <footer className="border-t border-line bg-ink py-10">
      {/* Empilhado e centrado em toda largura: em linha, com as pontas de
          larguras diferentes, a frase do meio ficava fora do centro. */}
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-4 text-center text-sm text-white/60 sm:px-6">
        <Link href="/">
          <Wordmark className="text-sm text-white" />
        </Link>
        <p>Analytics para vendedores do Mercado Livre.</p>
        <nav className="flex flex-wrap justify-center gap-x-4 gap-y-1">
          <Link href="/termos" className="transition hover:text-white">
            Termos de Uso
          </Link>
          <Link href="/privacidade" className="transition hover:text-white">
            Privacidade
          </Link>
          <Link href="/login" className="transition hover:text-white">
            Entrar
          </Link>
        </nav>
      </div>
    </footer>
  );
}
