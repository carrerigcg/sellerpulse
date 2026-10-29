"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { cancelarAssinatura, trocarPlano } from "@/lib/ml";
import { NOMES_DOS_PLANOS, type NomeDoPlano } from "@/lib/plano";
import { PRECOS_MENSAIS, formatarPreco } from "@/lib/precos";

const PLANOS: NomeDoPlano[] = ["essencial", "exclusive", "premium"];

/**
 * Trocar e cancelar. Só a string do plano atravessa a fronteira do servidor.
 *
 * As regras (upgrade na hora, downgrade no próximo ciclo, cancelamento até o
 * fim do período pago) são do backend; aqui só se diz à pessoa o que vai
 * acontecer ANTES de ela clicar.
 */
export function AcoesDaAssinatura({ plano }: { plano: NomeDoPlano }) {
  const router = useRouter();
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [confirmandoCancelamento, setConfirmandoCancelamento] = useState(false);

  async function executa(acao: () => Promise<void>) {
    setOcupado(true);
    setErro(null);
    try {
      await acao();
      router.refresh();
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível concluir agora.");
    } finally {
      setOcupado(false);
      setConfirmandoCancelamento(false);
    }
  }

  return (
    <>
      <section className="mt-6 rounded-xl border border-line p-5">
        <h2 className="text-sm font-semibold">Trocar de plano</h2>
        <ul className="mt-3 space-y-3">
          {PLANOS.filter((p) => p !== plano).map((p) => {
            const upgrade = PRECOS_MENSAIS[p] > PRECOS_MENSAIS[plano];
            return (
              <li key={p} className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <span>
                  <span className="font-medium">{NOMES_DOS_PLANOS[p]}</span>{" "}
                  <span className="text-muted">{formatarPreco(PRECOS_MENSAIS[p])}/mês</span>
                  <span className="block text-xs text-muted">
                    {upgrade
                      ? "Libera na hora. O valor novo vale a partir da próxima cobrança."
                      : "Vale a partir da próxima cobrança. Até lá, você continua com o plano atual."}
                  </span>
                </span>
                <button
                  type="button"
                  disabled={ocupado}
                  onClick={() => executa(() => trocarPlano(p))}
                  className={`inline-flex min-h-11 items-center rounded-lg px-3 text-sm font-medium transition disabled:opacity-40 ${
                    upgrade
                      ? "bg-accent text-white hover:bg-accent-hover"
                      : "border border-line hover:bg-surface"
                  }`}
                >
                  {upgrade ? `Mudar para o ${NOMES_DOS_PLANOS[p]}` : `Passar para o ${NOMES_DOS_PLANOS[p]}`}
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="mt-6 rounded-xl border border-line p-5">
        <h2 className="text-sm font-semibold">Cancelar</h2>
        <p className="mt-1 text-sm text-muted">
          A cobrança para de renovar e o acesso continua até o fim do período já pago. Os seus
          dados ficam guardados.
        </p>
        {confirmandoCancelamento ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={ocupado}
              onClick={() => executa(cancelarAssinatura)}
              className="inline-flex min-h-11 items-center rounded-lg bg-negative px-3 text-sm font-medium text-white disabled:opacity-40"
            >
              {ocupado ? "Cancelando…" : "Confirmar o cancelamento"}
            </button>
            <button
              type="button"
              disabled={ocupado}
              onClick={() => setConfirmandoCancelamento(false)}
              className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface"
            >
              Manter a assinatura
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmandoCancelamento(true)}
            className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium text-negative hover:bg-surface"
          >
            Cancelar a assinatura
          </button>
        )}
      </section>

      {erro && (
        <p role="alert" className="mt-4 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}
        </p>
      )}
    </>
  );
}
