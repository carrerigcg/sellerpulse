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

/**
 * `className` existe pra que o layout escolha onde a faixa fica (ordem e
 * largura mudam entre celular e desktop) sem que este componente precise
 * saber de layout. O que é dele — rolar de lado em vez de transbordar —
 * fica aqui.
 */
export function Nav({ className = "" }: { className?: string }) {
  const pathname = usePathname();

  return (
    // `overflow-x-auto` porque os quatro links somam mais que a largura útil
    // do celular mesmo tendo uma linha só pra eles; rolar de lado mantém
    // "Conectar conta" alcançável em vez de cortado. O `min-w-0` permite
    // encolher quando a faixa é um item flex do cabeçalho (tablet).
    <nav className={`flex min-w-0 items-center gap-1 overflow-x-auto no-scrollbar ${className}`}>
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
