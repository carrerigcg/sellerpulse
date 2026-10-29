import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Wordmark } from "@/components/brand";
import { getAcesso } from "@/lib/api";
import { NOMES_DOS_PLANOS } from "@/lib/plano";

import { FormularioDeAceite } from "./formulario";

export const metadata: Metadata = { title: "Termos de Uso · SellerPulse" };

/**
 * O aceite dos Termos de Uso: o "contrato assinado" da decisão 2 da spec.
 *
 * Aparece para quem tem plano e ainda não aceitou a versão vigente. Quem não
 * tem plano vai para /planos (não há contrato a aceitar); quem já aceitou, para
 * o painel. O backend grava a prova (versão, data, IP, navegador) e recusa o
 * painel sem ela.
 *
 * Os termos ainda são rascunho, à espera da revisão jurídica. A versão vigente
 * no backend diz isso no nome, e a versão final pede aceite de novo.
 */
export default async function AceitePage() {
  const acesso = await getAcesso().catch(() => null);
  if (!acesso) redirect("/login");
  if (acesso.plano === null) redirect("/planos");
  if (acesso.termos.aceito) redirect("/dashboard");

  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <div className="mx-auto max-w-2xl">
        <Wordmark />
        <h1 className="mt-10 text-2xl font-semibold tracking-tight">
          Seu plano {NOMES_DOS_PLANOS[acesso.plano]} está ativo
        </h1>
        <p className="mt-2 text-muted">
          Antes de conectar a sua conta do Mercado Livre, leia e aceite os Termos de Uso e a
          Política de Privacidade.
        </p>

        <section className="mt-6 space-y-3 rounded-xl border border-line bg-surface p-5 text-sm leading-relaxed">
          <h2 className="font-semibold">O essencial dos termos</h2>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              O SellerPulse lê, com a sua autorização, os pedidos, anúncios e envios da sua conta do
              Mercado Livre, e só para calcular as análises do painel. Nunca altera nada na sua
              conta.
            </li>
            <li>
              Os dados dos seus compradores são tratados em seu nome. Não guardamos nome, e-mail,
              telefone, endereço ou CPF de comprador, nem dados de cartão.
            </li>
            <li>
              Os números dependem do que o Mercado Livre entrega e do custo que você informa. O
              custo dos produtos só entra na conta quando você o informa.
            </li>
            <li>
              Você pode desconectar a conta do Mercado Livre quando quiser, e pedir a exclusão dos
              seus dados.
            </li>
          </ul>
          <p className="text-xs text-muted">
            Versão {acesso.termos.versao}. O texto completo está em revisão e será publicado antes
            do lançamento; quando isso acontecer, pediremos o seu aceite de novo.
          </p>
        </section>

        <FormularioDeAceite versao={acesso.termos.versao} />
      </div>
    </main>
  );
}
