"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Navegação entre as três telas da demonstração pública.
 *
 * Mesmo padrão de `app/dashboard/nav.tsx` (Client Component só por causa do
 * `usePathname`), com um conjunto de rotas menor: a demo não tem "Conectar
 * conta" — não há conta nenhuma pra conectar aqui.
 */

const LINKS = [
  { href: "/demo", rotulo: "Executive" },
  { href: "/demo/produtos", rotulo: "Produtos" },
  { href: "/demo/clientes", rotulo: "Clientes" },
] as const;

/**
 * `className` existe pra que o layout escolha onde a faixa fica (ordem e
 * largura mudam entre celular e desktop) sem que este componente precise
 * saber de layout. O que é dele — rolar de lado em vez de transbordar —
 * fica aqui.
 */
export function DemoNav({ className = "" }: { className?: string }) {
  const pathname = usePathname();

  return (
    // `overflow-x-auto` porque os links não cabem na largura do celular nem
    // sozinhos numa linha; rolar de lado mantém todos alcançáveis. O
    // `min-w-0` permite encolher quando a faixa é um item flex do cabeçalho
    // (tablet), já que o padrão do flex é não encolher abaixo do conteúdo.
    <nav className={`flex min-w-0 items-center gap-1 overflow-x-auto no-scrollbar ${className}`}>
      {LINKS.map((link) => {
        // "/demo" não pode casar por prefixo com as outras rotas (todas
        // começam com "/demo"), então só ele usa igualdade exata.
        const ativa = link.href === "/demo" ? pathname === link.href : pathname.startsWith(link.href);

        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={ativa ? "page" : undefined}
            // `shrink-0`: sem isso o flex espreme os links pra caber na
            // faixa e o texto quebra em duas linhas, em vez de rolar.
            className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              ativa ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
            }`}
          >
            {link.rotulo}
          </Link>
        );
      })}
    </nav>
  );
}
