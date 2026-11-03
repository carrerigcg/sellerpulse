"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { linkDeEmail } from "@/lib/contato";
import { desistirDaCompra } from "@/lib/ml";

/**
 * O direito de arrependimento (seção 8 dos Termos): só aparece enquanto o
 * backend diz que o prazo está aberto. `ate` chega pronto do servidor, como
 * texto.
 */
export function Desistir({ ate }: { ate: string }) {
  const router = useRouter();
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function desistir() {
    setOcupado(true);
    setErro(null);
    try {
      await desistirDaCompra();
      // Sem plano, o painel não abre mais: a confirmação mora em /planos.
      router.push("/planos?motivo=desistiu");
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível desistir agora.");
      // Um estorno pendente já deixou a assinatura cancelada: a tela mostra isso.
      router.refresh();
      setOcupado(false);
      setConfirmando(false);
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-line p-5">
      <h2 className="text-sm font-semibold">Desistir da compra</h2>
      <p className="mt-1 text-sm text-muted">
        Você pode desistir até {ate} e receber de volta o valor inteiro, pelo mesmo meio de
        pagamento. O acesso ao painel termina na hora, e os seus dados ficam guardados.
      </p>
      {confirmando ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={ocupado}
            onClick={desistir}
            className="inline-flex min-h-11 items-center rounded-lg bg-negative px-3 text-sm font-medium text-white disabled:opacity-40"
          >
            {ocupado ? "Desistindo…" : "Confirmar e pedir o valor de volta"}
          </button>
          <button
            type="button"
            disabled={ocupado}
            onClick={() => setConfirmando(false)}
            className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface"
          >
            Voltar
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirmando(true)}
          className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium text-negative hover:bg-surface"
        >
          Desistir e receber o valor de volta
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
