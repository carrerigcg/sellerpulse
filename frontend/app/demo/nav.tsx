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

export function DemoNav() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1">
      {LINKS.map((link) => {
        // "/demo" não pode casar por prefixo com as outras rotas (todas
        // começam com "/demo"), então só ele usa igualdade exata.
        const ativa = link.href === "/demo" ? pathname === link.href : pathname.startsWith(link.href);

        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={ativa ? "page" : undefined}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
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
