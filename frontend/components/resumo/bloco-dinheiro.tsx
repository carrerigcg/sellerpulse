import Link from "next/link";

import type { Veredito } from "@/lib/resumo";

/**
 * "O dinheiro" — a primeira pergunta de quem vende: estou ganhando?
 *
 * A comparação vai em `text-xl font-bold` por contraste, não por ênfase. O
 * verde de `positive` sobre branco dá 3,30:1 (medido), e só passa como texto
 * grande — 24px, ou 18,66px em negrito de verdade (700; semibold não conta).
 * A cor nunca vem sozinha: a frase já diz "a mais" ou "a menos".
 */
export function BlocoDinheiro({
  veredito,
  hrefFinanceiro,
}: {
  veredito: Veredito;
  hrefFinanceiro: string;
}) {
  const corDaComparacao =
    veredito.direcao === "menos"
      ? "text-negative"
      : veredito.direcao === "mais"
        ? "text-positive"
        : "text-muted";

  return (
    <section aria-labelledby="resumo-dinheiro" className="mt-6 rounded-xl border border-line p-5 sm:p-6">
      <h2 id="resumo-dinheiro" className="text-sm font-medium text-muted">
        O dinheiro
      </h2>
      <p className="mt-2 text-2xl font-semibold leading-snug tracking-tight">{veredito.sobra}</p>
      <p className={`mt-1 text-xl font-bold ${corDaComparacao}`}>{veredito.comparacao}</p>
      <p className="mt-4 leading-relaxed text-muted">{veredito.explicacao}</p>
      {veredito.maiorPeso && <p className="mt-3 leading-relaxed">{veredito.maiorPeso}</p>}
      {veredito.avisoComparacao && (
        <p className="mt-2 leading-relaxed text-muted">{veredito.avisoComparacao}</p>
      )}
      {veredito.avisoCobertura && (
        <p className="mt-4 rounded-lg bg-highlight-soft px-4 py-3 leading-relaxed text-ink">
          {veredito.avisoCobertura}
        </p>
      )}
      <Link
        href={hrefFinanceiro}
        className="mt-4 inline-flex min-h-11 items-center font-medium text-accent underline-offset-4 hover:underline"
      >
        Ver o financeiro completo →
      </Link>
    </section>
  );
}
