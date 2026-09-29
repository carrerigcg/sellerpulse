import Link from "next/link";

/**
 * Seção 7 — faixa final. Fecha o ritmo escuro→claro→escuro aberto pelo
 * herói: mesma cor `bg-ink`, sem inventar um terceiro tom escuro só pra
 * esta seção.
 */
export function FinalCta() {
  return (
    <section className="bg-ink py-20 text-center sm:py-28">
      <div className="mx-auto max-w-2xl px-4 sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Grátis para começar. Sem cartão.
        </h2>
        <p className="mt-4 text-lg text-white/70">
          Conecte o Mercado Livre e veja seus últimos 6 meses em minutos.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Link
            href="/signup"
            className="rounded-lg bg-accent px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-accent/30 transition hover:bg-accent-hover"
          >
            Criar conta grátis
          </Link>
          <Link
            href="/demo"
            className="rounded-lg border border-white/30 px-8 py-3.5 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            Ver demonstração
          </Link>
        </div>
      </div>
    </section>
  );
}
