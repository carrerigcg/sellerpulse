"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { nomeDaConta, type ContaML } from "@/lib/contas";
import { abrirConta } from "@/lib/ml";

/**
 * Troca a conta do Mercado Livre aberta no painel. Só aparece com mais de
 * uma conta que abre (`contasDoSeletor`).
 *
 * A escolha vai para um cookie e a página é renderizada de novo: todos os
 * números vêm do servidor, e é lá que o cookie vira o cabeçalho `X-Conta`.
 */
export function SeletorDeConta({ contas, aberta }: { contas: ContaML[]; aberta: string }) {
  const router = useRouter();
  const [trocando, startTransition] = useTransition();

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor="conta-aberta" className="text-muted">
        Conta do Mercado Livre
      </label>
      <select
        id="conta-aberta"
        value={aberta}
        disabled={trocando}
        onChange={(evento) => {
          const conta = contas.find((c) => c.id === evento.target.value);
          if (!conta) return;
          abrirConta(conta);
          startTransition(() => router.refresh());
        }}
        className="w-full min-w-0 rounded-lg border border-line bg-surface px-3 py-2 font-medium sm:w-auto sm:max-w-sm"
      >
        {contas.map((conta) => (
          <option key={conta.id} value={conta.id}>
            {nomeDaConta(conta)}
          </option>
        ))}
      </select>
      {trocando && <span className="text-muted">Carregando…</span>}
    </div>
  );
}
