"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { linkDeEmail } from "@/lib/contato";
import { useFocoDeVolta } from "@/lib/foco";
import { cancelarAssinatura } from "@/lib/ml";

// Quem chega aqui decide o texto: o inadimplente pode voltar a pagar; quem
// recusou os Termos precisa saber que o painel segue fechado sem o aceite.
const EXPLICACAO = {
  vencido:
    "A assinatura ainda está ativa no Asaas. Se não pretende voltar, cancele para não receber novas cobranças.",
  termos:
    "Se não quiser aceitar, cancele a cobrança mensal. Sem o aceite, o painel continua indisponível; com o cancelamento, você não é cobrado de novo.",
} as const;

/**
 * Parar a cobrança de quem não chega ao painel, onde fica o "Cancelar": quem ficou
 * inadimplente e quem não aceitou uma versão nova dos Termos. A assinatura continua
 * viva no Asaas: sem este botão, a única saída seria pedir a alguém.
 */
export function CancelarCobranca({ motivo }: { motivo: keyof typeof EXPLICACAO }) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [feito, setFeito] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const refDe = useFocoDeVolta(confirmando ? "cancelar" : null);

  async function cancelar() {
    setOcupado(true);
    setErro(null);
    try {
      await cancelarAssinatura();
      setFeito(true);
      // No aceite, a página do servidor troca o "plano ativo" pelo prazo que
      // sobrou. No vencido, nada muda nela, e a confirmação abaixo fica.
      if (motivo === "termos") router.refresh();
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível cancelar.");
      // Fechar devolve o foco ao botão que abriu (`useFocoDeVolta`).
      setConfirmando(false);
    } finally {
      setOcupado(false);
    }
  }

  if (feito) {
    return (
      <p role="status" className="mt-3 font-medium text-ink">
        Cobrança cancelada. Você não será mais cobrado.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <p className="text-muted">{EXPLICACAO[motivo]}</p>
      {confirmando ? (
        <div role="group" aria-label="Confirmar o cancelamento" className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={ocupado}
            onClick={cancelar}
            className="inline-flex min-h-11 items-center rounded-lg bg-negative px-3 font-medium text-white disabled:opacity-40"
          >
            {ocupado ? "Cancelando…" : "Confirmar o cancelamento"}
          </button>
          <button
            type="button"
            disabled={ocupado}
            autoFocus
            onClick={() => setConfirmando(false)}
            className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 font-medium hover:bg-bg"
          >
            Voltar
          </button>
        </div>
      ) : (
        <button
          ref={refDe("cancelar")}
          type="button"
          onClick={() => setConfirmando(true)}
          className="mt-2 inline-flex min-h-11 items-center rounded-lg border border-line px-3 font-medium text-negative hover:bg-bg"
        >
          Cancelar a cobrança
        </button>
      )}
      {erro && (
        <p role="alert" className="mt-2 rounded-lg bg-negative/10 px-3 py-2 text-negative">
          {erro}{" "}
          <a href={linkDeEmail("Cancelar a cobrança")} className="font-medium underline">
            Fale com a gente
          </a>
          .
        </p>
      )}
    </div>
  );
}
