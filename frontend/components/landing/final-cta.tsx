import Link from "next/link";

/**
 * Seção final — faixa de fechamento. Mantém o ritmo escuro→claro→escuro
 * aberto pelo herói: mesma cor `bg-ink`, sem inventar um terceiro tom escuro
 * só pra esta seção.
 *
 * É AQUI que mora o empurrão, e não no herói. Uma headline que afirma a tese
 * ("poucos têm as respostas") e ao mesmo tempo cutuca o leitor a agir faz os
 * dois mal, e cobrança na primeira tela afasta quem acabou de chegar. No fim
 * da página, depois de ver as telas e entender o que ganha, "falta você
 * olhar" é convite. Não mover isto pra cima.
 */
export function FinalCta() {
  return (
    <section className="bg-ink py-20 text-center sm:py-28">
      <div className="mx-auto max-w-2xl px-4 sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Os seus últimos 6 meses já estão lá. Falta você olhar.
        </h2>
        <p className="mt-4 text-lg text-white/70">
          Conectar leva dois minutos. Grátis para começar, sem cartão.
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
