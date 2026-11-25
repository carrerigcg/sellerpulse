import Link from "next/link";
import type { ReactNode } from "react";

import {
  estadoDoPrejuizo,
  estadoDosParados,
  fraseDaReferencia,
  fraseSemAlertaDeMargem,
  fraseSemParados,
  linkDoAnuncio,
  MAX_POR_TIPO,
  partesDaMargem,
  partesDoParado,
  type Alertas,
  type EstadoDaCaixa,
} from "@/lib/alertas";

type Tom = "negativo" | "laranja";

/**
 * Classes literais por tom e estado. A cor forte fica na borda, no fundo e no
 * contador; o texto vai em `ink` ou no tom escuro (`*-strong`,
 * `accent-hover`), porque a cor forte como texto pequeno não passa do
 * contraste mínimo.
 */
const CAIXA: Record<Tom, Record<EstadoDaCaixa, string>> = {
  negativo: {
    alerta: "border-t-negative bg-negative/5",
    "tudo-certo": "border-t-positive bg-positive/5",
    "nao-medido": "border-t-line bg-surface",
  },
  laranja: {
    alerta: "border-t-accent bg-accent-soft",
    "tudo-certo": "border-t-positive bg-positive/5",
    "nao-medido": "border-t-line bg-surface",
  },
};
const CONTADOR: Record<Tom, string> = { negativo: "bg-negative", laranja: "bg-accent" };
// `text-muted` (#64748b) fica em 4,40 a 4,49:1 sobre os fundos tingidos, abaixo do 4,5
// mínimo; dentro das caixas o texto secundário usa `slate-600`, que passa folgado.
const DESTAQUE: Record<Tom, string> = { negativo: "text-negative-strong", laranja: "text-accent-hover" };

/**
 * Os alertas do Premium, no Resumo, logo depois do dinheiro. Specs
 * `2026-11-06-premium-alertas-no-painel` (o quê) e
 * `2026-11-25-resumo-com-cartoes` (o desenho).
 */
export function CardDeAlertas({ alertas, hrefCustos }: { alertas: Alertas; hrefCustos: string }) {
  const total = alertas.margem_negativa.length + alertas.parados.length;
  const prejuizo = estadoDoPrejuizo(alertas);
  const parados = estadoDosParados(alertas);
  const referencia = fraseDaReferencia(alertas);

  return (
    <section aria-labelledby="resumo-alertas" className="mt-8">
      <h2 id="resumo-alertas" className="text-lg font-semibold">
        Alertas{total > 0 && ` · ${total}`}
      </h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Caixa tom="negativo" estado={prejuizo} titulo="Produtos com prejuízo" total={alertas.margem_negativa.length}>
          {prejuizo === "alerta" ? (
            <>
              <Lista total={alertas.margem_negativa.length}>
                {alertas.margem_negativa.slice(0, MAX_POR_TIPO).map((a) => {
                  const p = partesDaMargem(a);
                  return (
                    <li key={a.sku} className="min-w-0">
                      <p className="break-words font-medium">{a.titulo}</p>
                      <p className={`tabular text-lg font-bold ${DESTAQUE.negativo}`}>
                        <span className="sr-only">Prejuízo de </span>
                        <span aria-hidden="true">−</span>
                        {p.prejuizo}
                      </p>
                      <p className="text-sm text-slate-600">{p.contexto}</p>
                    </li>
                  );
                })}
              </Lista>
              <BotaoDeCustos href={hrefCustos}>Conferir custos</BotaoDeCustos>
            </>
          ) : (
            <>
              <p className="leading-relaxed">{fraseSemAlertaDeMargem(alertas)}</p>
              {prejuizo === "nao-medido" && <BotaoDeCustos href={hrefCustos}>Informar custos</BotaoDeCustos>}
            </>
          )}
        </Caixa>

        <Caixa tom="laranja" estado={parados} titulo="Anúncios parados" total={alertas.parados.length}>
          {parados === "alerta" ? (
            <Lista total={alertas.parados.length}>
              {alertas.parados.slice(0, MAX_POR_TIPO).map((a) => {
                const p = partesDoParado(a);
                const href = linkDoAnuncio(a.sku);
                return (
                  <li key={a.sku} className="min-w-0">
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="break-words font-medium underline hover:text-accent-hover"
                      >
                        {a.titulo}
                        <span className="sr-only"> (abre o anúncio no Mercado Livre)</span>
                      </a>
                    ) : (
                      <p className="break-words font-medium">{a.titulo}</p>
                    )}
                    <p className={`tabular text-lg font-bold ${DESTAQUE.laranja}`}>{p.dias}</p>
                    <p className="text-sm text-slate-600">{p.contexto}</p>
                  </li>
                );
              })}
            </Lista>
          ) : (
            <p className="leading-relaxed">{fraseSemParados(alertas)}</p>
          )}
          {parados === "alerta" && referencia && <p className="mt-3 text-sm text-slate-600">{referencia}</p>}
        </Caixa>
      </div>
    </section>
  );
}

function Caixa({
  tom,
  estado,
  titulo,
  total,
  children,
}: {
  tom: Tom;
  estado: EstadoDaCaixa;
  titulo: string;
  total: number;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-xl border border-line border-t-4 p-4 sm:p-5 ${CAIXA[tom][estado]}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{titulo}</h3>
        {estado === "alerta" && (
          <span className={`shrink-0 whitespace-nowrap tabular rounded-full px-2.5 py-0.5 text-sm font-bold text-white ${CONTADOR[tom]}`}>
            <span className="sr-only">Quantidade: </span>
            {total}
          </span>
        )}
        {estado === "tudo-certo" && (
          <span className="shrink-0 whitespace-nowrap rounded-full bg-positive/10 px-2.5 py-0.5 text-sm font-bold text-positive-strong">
            ✓ tudo certo
          </span>
        )}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Lista({ total, children }: { total: number; children: ReactNode }) {
  return (
    <>
      {/* role="list": o Safari tira a semântica de lista quando o estilo é "none". */}
      <ul role="list" className="flex flex-col gap-3 leading-snug">
        {children}
      </ul>
      {total > MAX_POR_TIPO && (
        <p className="mt-3 text-sm text-slate-600">
          E mais {total - MAX_POR_TIPO}. Os {MAX_POR_TIPO} de cima são os mais graves.
        </p>
      )}
    </>
  );
}

function BotaoDeCustos({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="mt-4 inline-flex min-h-11 items-center rounded-lg border border-line bg-white px-4 font-medium text-ink transition hover:bg-surface"
    >
      {children}
    </Link>
  );
}
