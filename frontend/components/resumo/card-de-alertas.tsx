import Link from "next/link";
import type { ReactNode } from "react";

import {
  estadoDaMargem,
  fraseDaMargem,
  fraseDoParado,
  fraseSemAlertaDeMargem,
  fraseSemParados,
  linkDoAnuncio,
  MAX_POR_TIPO,
  type Alertas,
} from "@/lib/alertas";

/**
 * Os alertas do Premium, no topo do Resumo. Spec
 * `docs/specs/2026-11-06-premium-alertas-no-painel-design.md`.
 *
 * Sem vermelho no texto: o `negative` em texto corrido não passa do
 * contraste mínimo (ver `ResumoDaLoja`). A palavra "prejuízo" carrega o peso.
 */
export function CardDeAlertas({ alertas, hrefCustos }: { alertas: Alertas; hrefCustos: string }) {
  const margem = estadoDaMargem(alertas);
  const total = alertas.margem_negativa.length + alertas.parados.length;

  return (
    <section aria-labelledby="resumo-alertas" className="mt-6 rounded-xl border border-line p-5 sm:p-6">
      <h2 id="resumo-alertas" className="text-sm font-medium text-muted">
        Alertas{total > 0 && ` · ${total}`}
      </h2>

      <h3 className="mt-3 font-semibold">Produtos com prejuízo</h3>
      {margem === "sem-custo" ? (
        <p className="mt-1 leading-relaxed text-muted">
          {fraseSemAlertaDeMargem(alertas)}{" "}
          <Link href={hrefCustos} className="text-accent underline hover:text-accent-hover">
            Conferir os custos
          </Link>
        </p>
      ) : margem === "nenhum" ? (
        <p className="mt-1 leading-relaxed text-muted">{fraseSemAlertaDeMargem(alertas)}</p>
      ) : (
        <Lista total={alertas.margem_negativa.length}>
          {alertas.margem_negativa.slice(0, MAX_POR_TIPO).map((a) => (
            <li key={a.sku}>
              <Link href={hrefCustos} className="font-medium underline hover:text-accent-hover">
                {a.titulo}
              </Link>
              <p className="text-muted">{fraseDaMargem(a)}</p>
            </li>
          ))}
        </Lista>
      )}

      <h3 className="mt-5 font-semibold">Anúncios parados</h3>
      {alertas.parados.length === 0 ? (
        <p className="mt-1 leading-relaxed text-muted">{fraseSemParados(alertas)}</p>
      ) : (
        <Lista total={alertas.parados.length}>
          {alertas.parados.slice(0, MAX_POR_TIPO).map((a) => {
            const href = linkDoAnuncio(a.sku);
            return (
              <li key={a.sku}>
                {href ? (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium underline hover:text-accent-hover"
                  >
                    {a.titulo}
                    <span className="sr-only"> (abre o anúncio no Mercado Livre)</span>
                  </a>
                ) : (
                  <span className="font-medium">{a.titulo}</span>
                )}
                <p className="text-muted">{fraseDoParado(a)}</p>
              </li>
            );
          })}
        </Lista>
      )}
    </section>
  );
}

function Lista({ total, children }: { total: number; children: ReactNode }) {
  return (
    <>
      <ul className="mt-2 flex flex-col gap-3 leading-relaxed">{children}</ul>
      {total > MAX_POR_TIPO && (
        <p className="mt-2 text-sm text-muted">
          E mais {total - MAX_POR_TIPO}. Os {MAX_POR_TIPO} de cima são os mais graves.
        </p>
      )}
    </>
  );
}
