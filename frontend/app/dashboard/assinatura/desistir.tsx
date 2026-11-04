"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { linkDeEmail } from "@/lib/contato";
import { useFocoDeVolta } from "@/lib/foco";
import { desistirDaCompra } from "@/lib/ml";

/**
 * O direito de arrependimento (seção 8 dos Termos): só aparece enquanto o
 * backend diz que o prazo está aberto. `ate` chega pronto do servidor, como
 * texto. Com `jaDevolvido`, o dinheiro já voltou (estorno interrompido ou
 * feito à mão) e a tela não promete devolver de novo: só encerra o acesso.
 */
export function Desistir({ ate, jaDevolvido }: { ate: string; jaDevolvido: boolean }) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const refDe = useFocoDeVolta(confirmando ? "desistir" : null);

  async function desistir() {
    setOcupado(true);
    setErro(null);
    try {
      await desistirDaCompra();
      // Sem plano, o painel não abre mais: a confirmação mora em /planos.
      router.push("/planos?motivo=desistiu");
    } catch (falha) {
      // Sem refresh: recarregar pergunta ao Asaas de novo e, se ele estiver fora,
      // esta seção sai da tela levando junto o erro. A mensagem do estorno
      // pendente já diz que a assinatura foi cancelada.
      setErro(falha instanceof Error ? falha.message : "Não foi possível desistir agora.");
      setOcupado(false);
      setConfirmando(false);
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-line p-5">
      <h2 className="text-sm font-semibold">Desistir da compra</h2>
      <p className="mt-1 text-sm text-muted">
        {jaDevolvido
          ? "O valor desta assinatura já foi devolvido. Falta encerrar o acesso ao painel, que termina na hora; os seus dados ficam guardados."
          : `Você pode desistir até ${ate} e receber de volta o valor inteiro, pelo mesmo meio de pagamento. O acesso ao painel termina na hora, e os seus dados ficam guardados.`}
      </p>
      {confirmando ? (
        <div role="group" aria-label="Confirmar a desistência" className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={ocupado}
            onClick={desistir}
            className="inline-flex min-h-11 items-center rounded-lg bg-negative px-3 text-sm font-medium text-white disabled:opacity-40"
          >
            {ocupado
              ? "Desistindo…"
              : jaDevolvido
                ? "Confirmar e encerrar o acesso"
                : "Confirmar e pedir o valor de volta"}
          </button>
          <button
            type="button"
            disabled={ocupado}
            autoFocus
            onClick={() => setConfirmando(false)}
            className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface"
          >
            Voltar
          </button>
        </div>
      ) : (
        <button
          ref={refDe("desistir")}
          type="button"
          onClick={() => setConfirmando(true)}
          className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium text-negative hover:bg-surface"
        >
          {jaDevolvido ? "Encerrar o acesso" : "Desistir e receber o valor de volta"}
        </button>
      )}
      {erro && (
        <p role="alert" className="mt-3 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}{" "}
          <a href={linkDeEmail("Desistir da compra")} className="font-medium underline">
            Fale com a gente
          </a>
          .
        </p>
      )}
    </section>
  );
}
