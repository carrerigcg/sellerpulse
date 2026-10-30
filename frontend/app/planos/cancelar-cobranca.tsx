"use client";

import { useState } from "react";

import { cancelarAssinatura } from "@/lib/ml";

/**
 * Parar a cobrança de quem não chega ao painel, onde fica o "Cancelar": quem ficou
 * inadimplente e quem não aceitou uma versão nova dos Termos. A assinatura continua
 * viva no Asaas: sem este botão, a única saída seria pedir a alguém.
 */
export function CancelarCobranca() {
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [feito, setFeito] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function cancelar() {
    setOcupado(true);
    setErro(null);
    try {
      await cancelarAssinatura();
      setFeito(true);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível cancelar.");
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
      <p className="text-muted">
        A assinatura ainda está ativa no Asaas. Se não pretende voltar, cancele para não receber
        novas cobranças.
      </p>
      {confirmando ? (
        <div className="mt-2 flex flex-wrap gap-2">
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
            onClick={() => setConfirmando(false)}
            className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 font-medium hover:bg-bg"
          >
            Voltar
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirmando(true)}
          className="mt-2 inline-flex min-h-11 items-center rounded-lg border border-line px-3 font-medium text-negative hover:bg-bg"
        >
          Cancelar a cobrança
        </button>
      )}
      {erro && (
        <p role="alert" className="mt-2 rounded-lg bg-negative/10 px-3 py-2 text-negative">
          {erro}
        </p>
      )}
    </div>
  );
}
