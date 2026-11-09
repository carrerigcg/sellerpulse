"use client";

import { useState } from "react";

import type { OpcaoDeConta } from "@/lib/contas";
import { abrirConta } from "@/lib/ml";

/**
 * Troca a conta do Mercado Livre aberta no painel, ou abre a soma delas. Só
 * aparece com mais de uma conta que abre (`opcoesDoSeletor`).
 *
 * A escolha vai para um cookie, e o servidor a manda ao backend no cabeçalho
 * `X-Conta`. A página recarrega inteira, e não com `router.refresh()`: o
 * refresh preserva o estado dos Client Components, e a tabela de custos ou a
 * tela de conexão ficariam com o dado da conta anterior enquanto as chamadas
 * já saem para a nova (um "Desconectar" sob o nome de uma conta desconectaria
 * outra).
 *
 * Abrir pede o botão, e não a mudança do select: no Chrome e no Edge do
 * Windows, a seta do teclado no select fechado já muda o valor, e quem usa
 * teclado abriria a conta seguinte sem conseguir chegar à soma.
 */
export function SeletorDeConta({ opcoes, aberta }: { opcoes: OpcaoDeConta[]; aberta: string }) {
  const [trocando, setTrocando] = useState(false);
  const [escolha, setEscolha] = useState(aberta);
  const opcao = opcoes.find((o) => o.valor === escolha);

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor="conta-aberta" className="text-muted">
        Conta do Mercado Livre
      </label>
      <select
        id="conta-aberta"
        value={escolha}
        disabled={trocando}
        onChange={(evento) => setEscolha(evento.target.value)}
        className="min-h-11 w-full min-w-0 rounded-lg border border-line bg-surface px-3 font-medium sm:w-auto sm:max-w-sm"
      >
        {opcoes.map((opcao) => (
          <option key={opcao.valor} value={opcao.valor}>
            {opcao.rotulo}
          </option>
        ))}
      </select>
      {escolha !== aberta && opcao && !trocando && (
        <button
          type="button"
          onClick={() => {
            setTrocando(true);
            abrirConta({ id: opcao.valor, principal: opcao.principal });
            window.location.reload();
          }}
          className="min-h-11 rounded-lg bg-accent px-4 font-medium text-white transition hover:bg-accent-hover"
        >
          Abrir
        </button>
      )}
      {trocando && (
        <span role="status" className="text-muted">
          Abrindo…
        </span>
      )}
    </div>
  );
}
