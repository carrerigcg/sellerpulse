import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Wordmark } from "@/components/brand";
import { ResumoDosTermos } from "@/components/planos/resumo-dos-termos";
import { getAcesso } from "@/lib/api";
import type { NomeDoPlano } from "@/lib/plano";
import { createClient } from "@/lib/supabase/server";

import { FormularioDeAssinatura } from "./formulario";

export const metadata: Metadata = { title: "Assinar · SellerPulse" };

const PLANOS_VALIDOS: NomeDoPlano[] = ["essencial", "exclusive", "premium"];

/**
 * Contratar: escolhe o ciclo, aceita os termos, e vai pagar no Asaas.
 *
 * O aceite vem ANTES do pagamento (decisão 2 da spec de cobrança,
 * `docs/specs/2026-10-29-cobranca-asaas-design.md`). Quem já tem plano vai para
 * "Minha assinatura", onde troca: um segundo checkout criaria uma segunda
 * cobrança em paralelo.
 */
export default async function AssinarPage({ searchParams }: PageProps<"/assinar">) {
  const params = await searchParams;
  const plano = PLANOS_VALIDOS.find((p) => p === params.plano) ?? "exclusive";

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect(`/login?proximo=${encodeURIComponent(`/assinar?plano=${plano}`)}`);

  const acesso = await getAcesso().catch(() => null);
  if (acesso?.plano) redirect("/dashboard/assinatura");

  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center justify-between gap-4">
          <Link href="/" aria-label="Página inicial">
            <Wordmark />
          </Link>
          <Link href="/planos" className="text-sm text-muted underline hover:text-accent">
            Ver os planos
          </Link>
        </div>
        <h1 className="mt-10 text-2xl font-semibold tracking-tight">Assinar o SellerPulse</h1>
        <p className="mt-2 text-muted">
          O pagamento é feito na página do Asaas, nosso parceiro de cobrança. Os dados do seu
          cartão não passam pelo SellerPulse.
        </p>

        {acesso === null ? (
          <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
            Não foi possível carregar a contratação agora. Tente de novo em instantes.
          </p>
        ) : (
          <>
            <ResumoDosTermos versao={acesso.termos.versao} />
            <FormularioDeAssinatura
              planoInicial={plano}
              email={user.email ?? ""}
              versao={acesso.termos.versao}
            />
          </>
        )}
      </div>
    </main>
  );
}
