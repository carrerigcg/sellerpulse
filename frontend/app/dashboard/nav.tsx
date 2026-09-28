"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Navegação entre as telas do dashboard, com a ativa marcada.
 *
 * Client Component só por causa do `usePathname` — precisa saber em que
 * rota está pra destacar o link certo, e isso não dá pra ler num Server
 * Component sem passar a URL manualmente por todo layout.
 */

const LINKS = [
  { href: "/dashboard", rotulo: "Executive" },
  { href: "/dashboard/produtos", rotulo: "Produtos" },
  { href: "/dashboard/clientes", rotulo: "Clientes" },
  { href: "/dashboard/conectar", rotulo: "Conectar conta" },
] as const;

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1">
      {LINKS.map((link) => {
        // "/dashboard" não pode casar por prefixo com as outras rotas
        // (todas começam com "/dashboard"), então só ele usa igualdade
        // exata — as demais casam por prefixo pra continuar marcadas em
        // eventuais sub-rotas futuras.
        const ativa =
          link.href === "/dashboard" ? pathname === link.href : pathname.startsWith(link.href);

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
