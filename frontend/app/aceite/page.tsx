import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Wordmark } from "@/components/brand";
import { getAcesso } from "@/lib/api";
import { ResumoDosTermos } from "@/components/planos/resumo-dos-termos";
import { RegistroDeAcesso } from "@/components/registro-de-acesso";
import { NOMES_DOS_PLANOS, destinoSemAcesso, ultimoDia } from "@/lib/plano";

import { CancelarCobranca } from "../planos/cancelar-cobranca";
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
 * O texto completo está em `/termos` e `/privacidade`. Uma versão nova no backend
 * (`VERSAO_DOS_TERMOS`) pede aceite de novo.
 */
export default async function AceitePage() {
  const acesso = await getAcesso().catch(() => null);
  if (!acesso) redirect("/login");
  // Com o motivo: quem cancela dentro da tolerância de atraso perde o plano no
  // ato, e cair em /planos sem explicação pareceria falha do cancelamento.
  if (acesso.plano === null) redirect(destinoSemAcesso(acesso) ?? "/planos");
  if (acesso.termos.aceito) redirect("/dashboard");

  const nome = NOMES_DOS_PLANOS[acesso.plano];
  const cancelada = acesso.assinatura?.cancelada === true;
  const valeAte = acesso.assinatura?.acesso_ate ? ultimoDia(acesso.assinatura.acesso_ate) : null;

  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-ink sm:px-6">
      <RegistroDeAcesso />
      <div className="mx-auto max-w-2xl">
        <Wordmark />
        {cancelada ? (
          <>
            <h1 className="mt-10 text-2xl font-semibold tracking-tight">
              A cobrança do plano {nome} está cancelada
            </h1>
            <p className="mt-2 text-muted">
              Você não será mais cobrado. Se aceitar os Termos de Uso e a Política de Privacidade,
              pode usar o painel {valeAte ? `até ${valeAte}` : "até o fim do período já pago"}.
            </p>
          </>
        ) : (
          <>
            <h1 className="mt-10 text-2xl font-semibold tracking-tight">
              Seu plano {nome} está ativo
            </h1>
            <p className="mt-2 text-muted">
              Para usar o painel, leia e aceite os Termos de Uso e a Política de Privacidade.
            </p>
          </>
        )}

        <ResumoDosTermos versao={acesso.termos.versao} />

        <FormularioDeAceite versao={acesso.termos.versao} />

        {/* Os Termos prometem esta saída a quem não aceitar: aqui a pessoa ainda
            não chega à "Minha assinatura", e a cobrança continuaria. */}
        {acesso.assinatura?.recorrente && (
          <section className="mt-8 border-t border-line pt-6 text-sm">
            <h2 className="font-semibold">Não quer aceitar?</h2>
            <CancelarCobranca motivo="termos" />
          </section>
        )}
        {/* No mesmo lugar do botão: o refresh troca a seção, e quem estava olhando
            para ela precisa ver aqui que o cancelamento deu certo. */}
        {cancelada && (
          <section className="mt-8 border-t border-line pt-6 text-sm">
            <h2 className="font-semibold">Não quer aceitar?</h2>
            <p role="status" className="mt-3 font-medium text-ink">
              Cobrança cancelada. Você não será mais cobrado.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}
