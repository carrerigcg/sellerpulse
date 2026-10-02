import { redirect } from "next/navigation";

import { Wordmark } from "@/components/brand";
import { createClient } from "@/lib/supabase/server";

import { Nav } from "./nav";
import { BotaoSair } from "./sair";

export default async function DashboardLayout({
  children,
}: LayoutProps<"/dashboard">) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // O proxy já protege a rota; isto é defesa em profundidade para o caso de
  // o matcher mudar e alguém esquecer desta página.
  if (!user) redirect("/login");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line">
        {/* Mesma quebra em duas linhas de `demo/layout.tsx`, e aqui o aperto é
            pior: são quatro links (com "Conectar conta") em vez de três. No
            celular a navegação ganha uma faixa própria embaixo (`order-3
            w-full`) e o botão de sair sobe pro lado da marca; o `order`
            devolve a ordem original a partir de `sm`, deixando o desktop
            exatamente como estava. */}
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-2.5 sm:h-14 sm:flex-nowrap sm:py-0">
          <Wordmark className="order-1 text-base" />
          <div className="order-2 ml-auto flex items-center gap-4 sm:order-3">
            <span className="hidden text-sm text-muted sm:inline">
              {user.email}
            </span>
            <BotaoSair />
          </div>
          <Nav className="order-3 w-full sm:order-2 sm:w-auto" />
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
