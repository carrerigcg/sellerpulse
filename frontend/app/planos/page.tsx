import type { Metadata } from "next";
import Link from "next/link";

import { Wordmark } from "@/components/brand";
import { CartoesDePlanos } from "@/components/planos/cartoes-de-planos";
import { linkDeEmail } from "@/lib/contato";

export const metadata: Metadata = { title: "Planos · SellerPulse" };

/**
 * Os três planos. É para cá que vai quem não tem plano (o layout do painel
 * redireciona) e quem clica em "Fazer upgrade" num cadeado. Os cartões são os
 * mesmos da seção de preços da vitrine (`components/planos/cartoes-de-planos`).
 *
 * "Assinar" leva à contratação (`/assinar`), que termina no checkout do Asaas.
 */

export default async function PlanosPage({ searchParams }: PageProps<"/planos">) {
  // O layout do painel manda para cá quem teve plano e ele venceu. Sem este
  // aviso, a pessoa cai numa vitrine sem saber por que saiu do painel.
  const venceu = (await searchParams).motivo === "vencido";
  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <div className="mx-auto max-w-5xl">
        <Link href="/" aria-label="Página inicial">
          <Wordmark />
        </Link>

        {venceu && (
          <div
            role="status"
            className="mt-8 rounded-xl border border-line bg-surface px-4 py-3 text-sm leading-relaxed"
          >
            <p className="font-semibold">O seu plano venceu.</p>
            <p className="mt-1 text-muted">
              O pagamento não foi confirmado até o fim da tolerância, então o painel voltou a
              mostrar só a demonstração. Os seus dados continuam guardados: assine de novo e
              tudo volta como estava. Se você foi cobrado, fale com a gente pelo{" "}
              <a href={linkDeEmail("Meu plano venceu")} className="font-medium text-accent underline">
                e-mail
              </a>
              .
            </p>
          </div>
        )}

        <h1 className="mt-10 text-3xl font-semibold tracking-tight">Escolha o seu plano</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Conecte a sua conta do Mercado Livre e veja quanto sobra de cada venda. O pagamento é
          feito no Asaas, e o painel libera assim que ele confirmar.
        </p>

        <div className="mt-10">
          <CartoesDePlanos />
        </div>

        <p className="mt-10 text-sm text-muted">
          Quer ver antes de contratar?{" "}
          <Link href="/demo" className="font-medium text-accent underline hover:text-accent-hover">
            Abra a demonstração
          </Link>
          , com uma loja de exemplo e todas as telas.
        </p>
      </div>
    </main>
  );
}
