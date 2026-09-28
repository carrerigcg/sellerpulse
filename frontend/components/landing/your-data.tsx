/**
 * Seção 6 — seus dados. Sem CTA (ver tabela da spec): é uma seção de
 * confiança, não de conversão — vem logo antes da faixa final de propósito,
 * pra quem chegou até aqui e ainda está com o pé atrás sobre dar acesso à
 * conta do Mercado Livre.
 */

const ITENS = [
  {
    titulo: "Token cifrado",
    texto: "A credencial de acesso ao Mercado Livre fica cifrada em repouso, nunca em texto puro.",
    icone: IconeCadeado,
  },
  {
    titulo: "Isolamento por conta",
    texto: "Cada vendedor enxerga só os próprios dados — garantido no banco, não só na tela.",
    icone: IconeCamadas,
  },
  {
    titulo: "Desconectar quando quiser",
    texto: "Revogar o acesso é uma ação sua, não um chamado de suporte.",
    icone: IconeDesconectar,
  },
] as const;

export function YourData() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
        Seus dados
      </h2>

      <div className="mt-16 grid gap-10 sm:grid-cols-3">
        {ITENS.map(({ titulo, texto, icone: Icone }) => (
          <div key={titulo}>
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-surface text-ink">
              <Icone />
            </div>
            <h3 className="mt-5 text-lg font-semibold text-ink">{titulo}</h3>
            <p className="mt-2 text-muted">{texto}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function IconeCadeado() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M8 11V7a4 4 0 0 1 8 0v4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <circle cx="12" cy="16" r="1.5" fill="currentColor" />
    </svg>
  );
}

function IconeCamadas() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3 3 8l9 5 9-5-9-5Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path
        d="m3 13 9 5 9-5M3 8v5m18-5v5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconeDesconectar() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 7 6.5 4.5a2 2 0 0 0-3 2.7L5 9m10 6 2.5 2.5a2 2 0 0 0 3-2.7L19 13"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <path
        d="m14.5 4.5-2 2M16 8l-8 8M9.5 19.5l2-2"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}
