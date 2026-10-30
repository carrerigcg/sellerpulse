"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Wordmark } from "@/components/brand";
import { RegistroDeAcesso } from "@/components/registro-de-acesso";
import { WHATSAPP_DE_CONTATO, linkDeEmail, linkDeWhatsapp } from "@/lib/contato";
import { temPlanoAtivo } from "@/lib/ml";

/**
 * A volta do Asaas. O plano NÃO é liberado aqui: quem libera é o webhook,
 * quando o Asaas confirma o pagamento (`successUrl` não é prova de nada — a
 * própria documentação do Asaas diz para não confiar nele). Esta página só
 * espera o plano aparecer e leva ao painel.
 *
 * Fora do /dashboard de propósito: sem plano ainda, o layout do painel
 * mandaria a pessoa de volta para /planos no meio da espera.
 */
const INTERVALO_MS = 3000;
// Dois minutos. Passou disso, o mais provável é a fila de webhooks atrasada;
// a pessoa recebe um caminho em vez de uma roda girando para sempre.
const TENTATIVAS = 40;

export default function RetornoDoPagamento() {
  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <RegistroDeAcesso />
      <div className="mx-auto max-w-xl">
        <Wordmark />
        <Suspense>
          <Conteudo />
        </Suspense>
      </div>
    </main>
  );
}

function Conteudo() {
  const situacao = useSearchParams().get("checkout");
  const router = useRouter();
  const [esgotou, setEsgotou] = useState(false);
  const esperando = situacao === "ok";

  useEffect(() => {
    if (!esperando) return;
    let tentativas = 0;
    let ativo = true;
    async function confere() {
      if (!ativo) return;
      tentativas += 1;
      if (await temPlanoAtivo().catch(() => false)) {
        router.push("/dashboard");
        router.refresh();
        return;
      }
      if (tentativas >= TENTATIVAS) {
        setEsgotou(true);
        return;
      }
      setTimeout(confere, INTERVALO_MS);
    }
    void confere();
    return () => {
      ativo = false;
    };
  }, [esperando, router]);

  if (!esperando) {
    return (
      <section className="mt-10">
        <h1 className="text-2xl font-semibold tracking-tight">
          {situacao === "expirado" ? "O pagamento expirou" : "O pagamento não foi concluído"}
        </h1>
        <p className="mt-2 text-muted">Nada foi cobrado. Você pode tentar de novo quando quiser.</p>
        <Link
          href="/planos"
          className="mt-6 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          Voltar aos planos
        </Link>
      </section>
    );
  }

  return (
    <section className="mt-10" aria-live="polite">
      <h1 className="text-2xl font-semibold tracking-tight">
        {esgotou ? "Ainda confirmando a sua assinatura" : "Confirmando a sua assinatura…"}
      </h1>
      <p className="mt-2 text-muted">
        {esgotou
          ? "O Asaas ainda não nos avisou. Isso costuma levar poucos minutos; tente abrir o painel daqui a pouco."
          : "Assim que o Asaas confirmar, o seu painel abre sozinho. Costuma levar alguns segundos."}
      </p>
      {esgotou && (
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex rounded-lg border border-line px-4 py-2 text-sm font-medium hover:bg-surface"
          >
            Abrir o painel
          </Link>
          <a
            href={
              WHATSAPP_DE_CONTATO
                ? linkDeWhatsapp(WHATSAPP_DE_CONTATO, "Assinei o SellerPulse e o painel não abriu.")
                : linkDeEmail("Assinei e o painel não abriu")
            }
            className="text-sm text-muted underline hover:text-accent"
          >
            Falar com a gente
          </a>
        </div>
      )}
    </section>
  );
}
