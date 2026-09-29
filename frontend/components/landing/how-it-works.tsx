/**
 * Seção 4 — como funciona. Sem CTA (ver tabela da spec): o passo 1 já É a
 * ação de cadastro, listada como primeiro item da sequência, não repetida
 * como botão separado.
 */

const PASSOS = [
  {
    numero: "1",
    titulo: "Criar conta",
    // Sem menção ao Google: o provider ainda não está habilitado no Supabase,
    // e o botão devolve erro. Prometer na vitrine o que quebra no primeiro
    // clique é pior do que não oferecer. Volta a aparecer quando o OAuth
    // do Google estiver ligado de verdade.
    texto: "Leva um minuto. Email e senha, e pronto.",
  },
  {
    numero: "2",
    titulo: "Conectar o Mercado Livre",
    texto:
      "Autoriza pelo fluxo oficial do Mercado Livre. O token fica cifrado — a senha da sua conta nunca passa pelo SellerPulse.",
  },
  {
    numero: "3",
    titulo: "Os últimos 6 meses carregam sozinhos",
    texto: "Pedidos, produtos e compradores entram automaticamente, sem planilha e sem digitar nada.",
  },
] as const;

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
        Como funciona
      </h2>

      <div className="mt-16 grid gap-10 lg:grid-cols-3 lg:gap-8">
        {PASSOS.map((passo, i) => (
          <div key={passo.numero} className="relative">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-lg font-semibold text-accent">
              {passo.numero}
            </div>
            <h3 className="mt-5 text-lg font-semibold text-ink">{passo.titulo}</h3>
            <p className="mt-2 text-muted">{passo.texto}</p>

            {i < PASSOS.length - 1 && (
              <span
                className="pointer-events-none absolute right-[-1.25rem] top-6 hidden text-2xl text-line lg:block"
                aria-hidden
              >
                →
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
