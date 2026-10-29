import type { Metadata } from "next";
import Link from "next/link";

import { Wordmark } from "@/components/brand";
import { CartoesDePlanos } from "@/components/planos/cartoes-de-planos";

export const metadata: Metadata = { title: "Planos · SellerPulse" };

/**
 * Os três planos. É para cá que vai quem não tem plano (o layout do painel
 * redireciona) e quem clica em "Fazer upgrade" num cadeado. Os cartões são os
 * mesmos da seção de preços da vitrine (`components/planos/cartoes-de-planos`).
 *
 * Ainda sem checkout: o botão abre WhatsApp ou e-mail.
 */

export default function PlanosPage() {
  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <div className="mx-auto max-w-5xl">
        <Link href="/" aria-label="Página inicial">
          <Wordmark />
        </Link>

        <h1 className="mt-10 text-3xl font-semibold tracking-tight">Escolha o seu plano</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Conecte a sua conta do Mercado Livre e veja quanto sobra de cada venda. Para contratar,
          fale com a gente; o acesso é liberado assim que o plano estiver ativo.
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
