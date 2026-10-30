import type { Metadata } from "next";
import Link from "next/link";

import { Wordmark } from "@/components/brand";
import { CartoesDePlanos } from "@/components/planos/cartoes-de-planos";
import { getAcesso } from "@/lib/api";
import { linkDeEmail } from "@/lib/contato";
import { vitrineComVendasAbertas } from "@/lib/vendas";

import { CancelarCobranca } from "./cancelar-cobranca";

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
  const motivo = (await searchParams).motivo;
  const venceu = motivo === "vencido";
  const encerrou = motivo === "encerrado";
  const vendasAbertas = vitrineComVendasAbertas();
  const comoVoltar = vendasAbertas
    ? "assine de novo e tudo volta como estava."
    : "quando as vendas abrirem, é só assinar de novo e tudo volta como estava.";
  // Só nesse caso consulta a conta: a página também é pública, e vencido é
  // quem pode ter uma cobrança ainda viva no Asaas.
  const cobrancaViva =
    venceu && (await getAcesso().catch(() => null))?.assinatura?.recorrente === true;
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
              mostrar só a demonstração. Os seus dados continuam guardados: {comoVoltar} Se você
              foi cobrado, fale com a gente pelo{" "}
              <a href={linkDeEmail("Meu plano venceu")} className="font-medium text-accent underline">
                e-mail
              </a>
              .
            </p>
            {cobrancaViva && <CancelarCobranca />}
          </div>
        )}

        {encerrou && (
          <div
            role="status"
            className="mt-8 rounded-xl border border-line bg-surface px-4 py-3 text-sm leading-relaxed"
          >
            <p className="font-semibold">O seu plano terminou.</p>
            <p className="mt-1 text-muted">
              O painel voltou a mostrar só a demonstração. Os seus dados continuam guardados:{" "}
              {comoVoltar}
            </p>
          </div>
        )}

        <h1 className="mt-10 text-3xl font-semibold tracking-tight">
          {vendasAbertas ? "Escolha o seu plano" : "Os planos do SellerPulse"}
        </h1>
        <p className="mt-2 max-w-2xl text-muted">
          {vendasAbertas
            ? "Conecte a sua conta do Mercado Livre e veja quanto sobra de cada venda. O pagamento é feito no Asaas, e o painel libera assim que ele confirmar."
            : "Conecte a sua conta do Mercado Livre e veja quanto sobra de cada venda."}
        </p>
        {/* O convite de upgrade do painel traz o assinante para cá. Com as vendas
            fechadas, os cartões não oferecem nada a ele, e a troca continua na
            assinatura. */}
        {!vendasAbertas && (
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Já é assinante? Mude de plano em{" "}
            <Link
              href="/dashboard/assinatura"
              className="font-medium text-accent underline hover:text-accent-hover"
            >
              Minha assinatura
            </Link>
            .
          </p>
        )}

        <div className="mt-10">
          <CartoesDePlanos />
        </div>

        <p className="mt-10 text-sm text-muted">
          Quer ver como funciona?{" "}
          <Link href="/demo" className="font-medium text-accent underline hover:text-accent-hover">
            Abra a demonstração
          </Link>
          , com uma loja de exemplo e todas as telas.
        </p>
      </div>
    </main>
  );
}
