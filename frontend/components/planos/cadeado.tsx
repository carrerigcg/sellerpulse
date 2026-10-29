import Link from "next/link";
import type { ReactNode } from "react";

/**
 * O que o plano não cobre, à vista e trancado.
 *
 * Os filhos são uma AMOSTRA desfocada — dados da demonstração, nunca os do
 * vendedor: o que o plano não cobre não sai do servidor (decisão 6 da spec
 * `docs/specs/2026-10-28-planos-e-acesso-design.md`). Sem amostra (a demo
 * pode estar fora do ar), fica só o cartão.
 *
 * A amostra é `aria-hidden` e `inert`: para leitor de tela e teclado, o que
 * existe aqui é o aviso e o botão, não uma tabela de mentira.
 */
export function Cadeado({
  titulo,
  descricao,
  plano = "Exclusive",
  children,
}: {
  titulo: string;
  descricao: string;
  plano?: string;
  children?: ReactNode;
}) {
  return (
    <section className="relative mt-6 overflow-hidden rounded-xl border border-line">
      {children && (
        <div aria-hidden inert className="pointer-events-none select-none p-5 blur-sm">
          {children}
        </div>
      )}
      <div
        className={`${
          children ? "absolute inset-0 bg-bg/60" : ""
        } flex items-center justify-center p-5`}
      >
        <div className="max-w-sm rounded-xl border border-line bg-bg p-5 text-center shadow-sm">
          <IconeCadeado />
          <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-accent">
            Disponível no {plano}
          </p>
          <h2 className="mt-1 text-base font-semibold">{titulo}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted">{descricao}</p>
          <Link
            href="/planos"
            className="mt-4 inline-flex items-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover"
          >
            Fazer upgrade
          </Link>
        </div>
      </div>
    </section>
  );
}

function IconeCadeado() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="mx-auto h-6 w-6 text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

/** Aviso de que o período pedido começa antes do que o plano mostra. */
export function AvisoDeHistorico({ inicio }: { inicio: string }) {
  const [ano, mes, dia] = inicio.split("-");
  return (
    <p className="mt-4 rounded-lg bg-highlight-soft px-3 py-2 text-xs leading-relaxed text-ink">
      No Essencial, o histórico é de 3 meses: os números abaixo começam em {dia}/{mes}/{ano}.{" "}
      <Link href="/planos" className="font-medium text-accent underline hover:text-accent-hover">
        Ver o histórico completo no Exclusive
      </Link>
    </p>
  );
}
