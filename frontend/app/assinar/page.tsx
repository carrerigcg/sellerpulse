import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Wordmark } from "@/components/brand";
import { ResumoDosTermos } from "@/components/planos/resumo-dos-termos";
import { getAcesso } from "@/lib/api";
import { WHATSAPP_DE_CONTATO, linkDeWhatsapp } from "@/lib/contato";
import { NOMES_DOS_PLANOS, type NomeDoPlano } from "@/lib/plano";
import { createClient } from "@/lib/supabase/server";
import { AVISO_DE_VENDAS_FECHADAS, mensagemParaSaberDaAbertura } from "@/lib/vendas";

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
          O pagamento é feito na página do Asaas, nosso parceiro de cobrança. Os seus dados de
          cobrança e do cartão não passam pelo SellerPulse.
        </p>

        {acesso === null ? (
          <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
            Não foi possível carregar a contratação agora. Tente de novo em instantes.
          </p>
        ) : !acesso.vendas_abertas ? (
          <div className="mt-8 rounded-xl border border-line bg-surface p-5 text-sm">
            <p className="font-semibold">{AVISO_DE_VENDAS_FECHADAS}</p>
            <p className="mt-1 text-muted">
              Enquanto isso, você pode ver a demonstração ou falar com a gente.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link
                href="/demo"
                className="rounded-lg bg-accent px-4 py-2 font-medium text-white transition hover:bg-accent-hover"
              >
                Ver a demonstração
              </Link>
              {WHATSAPP_DE_CONTATO && (
                <a
                  href={linkDeWhatsapp(
                    WHATSAPP_DE_CONTATO,
                    mensagemParaSaberDaAbertura(NOMES_DOS_PLANOS[plano]),
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-line px-4 py-2 font-medium transition hover:bg-bg"
                >
                  Falar no WhatsApp
                </a>
              )}
            </div>
          </div>
        ) : (
          <>
            <ResumoDosTermos versao={acesso.termos.versao} />
            <FormularioDeAssinatura
              planoInicial={plano}
              versao={acesso.termos.versao}
            />
          </>
        )}
      </div>
    </main>
  );
}
