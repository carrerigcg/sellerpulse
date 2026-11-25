import Link from "next/link";

import { NumeroAnimado } from "@/components/analytics/numero-animado";
import type { Veredito } from "@/lib/resumo";

/** Classes literais, para o Tailwind enxergar no build. */
const SELO: Record<Veredito["direcao"], string> = {
  mais: "bg-positive/10 text-positive-strong",
  menos: "bg-negative/10 text-negative-strong",
  igual: "bg-surface text-muted",
  "sem-comparacao": "bg-surface text-muted",
};

const SETA: Record<Veredito["direcao"], string> = {
  mais: "▲ ",
  menos: "▼ ",
  igual: "",
  "sem-comparacao": "",
};

/**
 * "O dinheiro": a primeira pergunta de quem vende, se está ganhando.
 *
 * Os cartõezinhos são a conta da sobra: vendas menos comissão, frete e
 * produtos. O que não se sabe aparece como "—" com a nota, nunca como R$ 0
 * (ausência não é zero). A cor do selo nunca vem sozinha: a seta e a frase
 * dizem o sentido.
 */
export function BlocoDinheiro({
  veredito,
  hrefFinanceiro,
}: {
  veredito: Veredito;
  hrefFinanceiro: string;
}) {
  const { destaque } = veredito;

  return (
    <section aria-labelledby="resumo-dinheiro" className="mt-6 rounded-xl border border-line p-5 sm:p-6">
      <h2 id="resumo-dinheiro" className="text-sm font-medium text-muted">
        O dinheiro · últimos 30 dias
      </h2>
      <div className="mt-2 flex flex-wrap items-end gap-x-5 gap-y-3">
        <div>
          {destaque.acima && <p className="font-semibold">{destaque.acima}</p>}
          <p className="tabular text-4xl font-bold tracking-tight">
            <NumeroAnimado valor={destaque.valor} />
          </p>
          <p className="font-semibold">{destaque.abaixo}</p>
        </div>
        <p className={`rounded-lg px-3 py-1 text-sm font-semibold ${SELO[veredito.direcao]}`}>
          <span aria-hidden="true">{SETA[veredito.direcao]}</span>
          {veredito.comparacao}
        </p>
      </div>

      {/* role="list" de propósito: o Safari tira a semântica de lista de um ul sem marcador. */}
      <ul role="list" className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {veredito.partes.map((parte) => (
          <li key={parte.rotulo} className="min-w-0 rounded-lg border border-line bg-surface px-3 py-2.5">
            <p className="text-sm text-muted">{parte.rotulo}</p>
            <p className="tabular mt-0.5 break-words text-lg font-semibold">
              {parte.valor === null ? (
                <>
                  <span aria-hidden="true">—</span>
                  <span className="sr-only">{parte.nota ?? "não informado"}</span>
                </>
              ) : (
                <NumeroAnimado valor={parte.valor} />
              )}
            </p>
            {/* Com valor nulo o sr-only acima já lê a nota; aqui ela só vale para quem vê. */}
            {parte.nota && (
              <p className="text-sm text-muted" aria-hidden={parte.valor === null ? "true" : undefined}>
                {parte.nota}
              </p>
            )}
          </li>
        ))}
      </ul>

      {veredito.maiorPeso && <p className="mt-4 leading-relaxed">{veredito.maiorPeso}</p>}
      {veredito.avisoComparacao && (
        <p className="mt-2 leading-relaxed text-muted">{veredito.avisoComparacao}</p>
      )}
      <p className="mt-2 leading-relaxed text-muted">{veredito.lembrete}</p>
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
