"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { aceitarTermos } from "@/lib/ml";

/**
 * A caixa e o botão. Só a `versao` (string) atravessa a fronteira do servidor:
 * é a versão que a página MOSTROU, e o backend recusa se ela não for a vigente.
 */
export function FormularioDeAceite({ versao }: { versao: string }) {
  const router = useRouter();
  const [marcado, setMarcado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aceitar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      await aceitarTermos(versao);
      router.push("/dashboard");
      router.refresh();
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível registrar o aceite.");
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={aceitar} className="mt-6">
      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={marcado}
          onChange={(e) => setMarcado(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-accent"
        />
        <span>
          Li e aceito os{" "}
          <a href="/termos" target="_blank" className="font-medium text-accent underline">
            Termos de Uso
          </a>{" "}
          e a{" "}
          <a href="/privacidade" target="_blank" className="font-medium text-accent underline">
            Política de Privacidade
          </a>{" "}
          do SellerPulse.
        </span>
      </label>
      {erro && (
        <p role="alert" className="mt-3 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}
        </p>
      )}
      <button
        type="submit"
        disabled={!marcado || enviando}
        className="mt-5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        {enviando ? "Registrando…" : "Aceitar e continuar"}
      </button>
    </form>
  );
}
