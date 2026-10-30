"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { cancelarAssinatura, trocarPlano } from "@/lib/ml";
import { NOMES_DOS_PLANOS, PLANOS_A_VENDA, type NomeDoPlano } from "@/lib/plano";
import { PRECOS_MENSAIS, formatarPreco } from "@/lib/precos";

/**
 * Trocar e cancelar. Só strings atravessam a fronteira do servidor.
 *
 * As regras (upgrade na hora, downgrade no próximo ciclo, cancelamento até o
 * fim do período pago) são do backend; aqui se diz à pessoa o que vai
 * acontecer, e se pede confirmação ANTES de mexer no que será cobrado.
 */
export function AcoesDaAssinatura({
  plano,
  proximoPlano,
}: {
  plano: NomeDoPlano;
  proximoPlano: NomeDoPlano | null;
}) {
  const router = useRouter();
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  // O que está esperando confirmação: um plano, ou o cancelamento.
  const [confirmando, setConfirmando] = useState<NomeDoPlano | "cancelar" | null>(null);

  const opcoes = PLANOS_A_VENDA.filter((p) => p !== plano && p !== proximoPlano);

  async function executa(acao: () => Promise<void>, feito: string) {
    setOcupado(true);
    setErro(null);
    setAviso(null);
    try {
      await acao();
      setAviso(feito);
      router.refresh();
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível concluir agora.");
    } finally {
      setOcupado(false);
      setConfirmando(null);
    }
  }

  return (
    <>
      {proximoPlano && (
        <section className="mt-6 rounded-xl border border-line bg-surface p-5 text-sm">
          <p>
            A troca para o <strong>{NOMES_DOS_PLANOS[proximoPlano]}</strong> vale na próxima
            cobrança. Mudou de ideia?
          </p>
          <button
            type="button"
            disabled={ocupado}
            onClick={() =>
              executa(() => trocarPlano(plano), `Você continua no ${NOMES_DOS_PLANOS[plano]}.`)
            }
            className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-line bg-bg px-3 text-sm font-medium hover:bg-surface disabled:opacity-40"
          >
            Manter o {NOMES_DOS_PLANOS[plano]}
          </button>
        </section>
      )}

      {/* Exclusive com downgrade agendado: não sobra plano, e "Manter" já está acima. */}
      {opcoes.length > 0 && (
      <section className="mt-6 rounded-xl border border-line p-5">
        <h2 className="text-sm font-semibold">Trocar de plano</h2>
        <ul className="mt-3 space-y-4">
          {opcoes.map((p) => {
            const upgrade = PRECOS_MENSAIS[p] > PRECOS_MENSAIS[plano];
            const efeito = upgrade
              ? `Libera na hora. A partir da próxima cobrança, ${formatarPreco(PRECOS_MENSAIS[p])} por mês.`
              : `Vale a partir da próxima cobrança, de ${formatarPreco(PRECOS_MENSAIS[p])}. Até lá, você continua no ${NOMES_DOS_PLANOS[plano]}.`;
            return (
              <li key={p} className="text-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>
                    <span className="font-medium">{NOMES_DOS_PLANOS[p]}</span>{" "}
                    <span className="text-muted">{formatarPreco(PRECOS_MENSAIS[p])}/mês</span>
                    <span className="block text-xs text-muted">{efeito}</span>
                  </span>
                  {confirmando !== p && (
                    <button
                      type="button"
                      disabled={ocupado}
                      onClick={() => setConfirmando(p)}
                      className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium transition hover:bg-surface disabled:opacity-40"
                    >
                      {upgrade ? "Mudar" : "Passar"} para o {NOMES_DOS_PLANOS[p]}
                    </button>
                  )}
                </div>
                {confirmando === p && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={ocupado}
                      onClick={() =>
                        executa(
                          () => trocarPlano(p),
                          upgrade
                            ? `Pronto: você está no ${NOMES_DOS_PLANOS[p]}.`
                            : `Agendado: você passa para o ${NOMES_DOS_PLANOS[p]} na próxima cobrança.`,
                        )
                      }
                      className="inline-flex min-h-11 items-center rounded-lg bg-accent px-3 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40"
                    >
                      {ocupado ? "Trocando…" : "Confirmar a troca"}
                    </button>
                    <button
                      type="button"
                      disabled={ocupado}
                      onClick={() => setConfirmando(null)}
                      className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface"
                    >
                      Voltar
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>
      )}

      <section className="mt-6 rounded-xl border border-line p-5">
        <h2 className="text-sm font-semibold">Cancelar</h2>
        <p className="mt-1 text-sm text-muted">
          A cobrança para de renovar e o acesso continua até o fim do período já pago. Os seus
          dados ficam guardados.
        </p>
        {confirmando === "cancelar" ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={ocupado}
              onClick={() => executa(cancelarAssinatura, "Assinatura cancelada.")}
              className="inline-flex min-h-11 items-center rounded-lg bg-negative px-3 text-sm font-medium text-white disabled:opacity-40"
            >
              {ocupado ? "Cancelando…" : "Confirmar o cancelamento"}
            </button>
            <button
              type="button"
              disabled={ocupado}
              onClick={() => setConfirmando(null)}
              className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface"
            >
              Manter a assinatura
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmando("cancelar")}
            className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium text-negative hover:bg-surface"
          >
            Cancelar a assinatura
          </button>
        )}
      </section>

      {aviso && (
        <p role="status" className="mt-4 rounded-lg border border-positive/40 bg-positive/10 px-3 py-2 text-sm text-ink">
          {aviso}
        </p>
      )}
      {erro && (
        <p role="alert" className="mt-4 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}
        </p>
      )}
    </>
  );
}
