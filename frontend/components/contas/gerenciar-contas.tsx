"use client";

import { useEffect, useState } from "react";

import { fraseDasContas, nomeDaConta, podeAdicionarConta, type Contas } from "@/lib/contas";
import { abrirConta, contasDoLogin, iniciarContaNova, removerConta } from "@/lib/ml";

/**
 * As contas do Mercado Livre do login, na tela de conexão: adicionar outra
 * (Premium, até 3) e remover uma extra. Spec
 * `docs/specs/2026-11-06-premium-varias-contas-design.md`.
 *
 * Só aparece para quem tem um plano de várias contas, ou ainda guarda uma
 * conta extra de quando tinha (decisão 2.1: os dados ficam, e é aqui que se
 * apaga).
 */
export function GerenciarContas() {
  const [contas, setContas] = useState<Contas | null>(null);

  useEffect(() => {
    async function carregar() {
      try {
        setContas(await contasDoLogin());
      } catch {
        // A seção é um extra da tela: sem ela, conectar continua funcionando.
        setContas(null);
      }
    }
    void carregar();
  }, []);

  if (!contas || (contas.max_contas < 2 && contas.contas.length < 2)) return null;
  return <PainelDeContas contas={contas} />;
}

export function PainelDeContas({ contas }: { contas: Contas }) {
  const [erro, setErro] = useState<string | null>(null);
  const [adicionando, setAdicionando] = useState(false);
  const [confirmando, setConfirmando] = useState<string | null>(null);
  const [removendo, setRemovendo] = useState(false);

  async function adicionar() {
    setAdicionando(true);
    setErro(null);
    try {
      window.location.href = await iniciarContaNova();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível iniciar a conexão.");
      setAdicionando(false);
    }
  }

  async function remover(id: string) {
    setRemovendo(true);
    setErro(null);
    try {
      await removerConta(id);
      // A conta removida estava aberta: sem apagar a escolha, o painel
      // pediria uma conta que não existe mais.
      if (contas.conta_aberta === id) abrirConta({ id: "", principal: true });
      window.location.reload();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível remover a conta.");
      setRemovendo(false);
    }
  }

  return (
    <section className="mt-8 rounded-xl border border-line p-5" aria-labelledby="contas-do-login">
      <h2 id="contas-do-login" className="text-sm font-semibold">
        Contas do Mercado Livre neste login
      </h2>
      <p className="mt-1 text-xs text-muted">{fraseDasContas(contas)}</p>

      {erro && (
        <p className="mt-3 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">{erro}</p>
      )}

      <ul className="mt-4 flex flex-col gap-3 text-sm">
        {contas.contas.map((conta) => (
          <li key={conta.id} className="flex flex-wrap items-center justify-between gap-2">
            <span className="min-w-0 [overflow-wrap:anywhere]">
              <span className="font-medium">{nomeDaConta(conta)}</span>
              {!conta.ativa && !conta.principal && (
                <span className="text-muted"> · não abre no seu plano atual</span>
              )}
            </span>
            {!conta.principal &&
              (confirmando === conta.id ? (
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-muted">Apaga os pedidos e custos desta conta.</span>
                  <button
                    type="button"
                    onClick={() => void remover(conta.id)}
                    disabled={removendo}
                    className="min-h-11 rounded-lg border border-line px-3 font-medium transition hover:bg-surface disabled:opacity-50"
                  >
                    {removendo ? "Removendo…" : "Remover de vez"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmando(null)}
                    disabled={removendo}
                    className="min-h-11 rounded-lg px-3 text-muted transition hover:bg-surface"
                  >
                    Manter
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmando(conta.id)}
                  className="min-h-11 rounded-lg border border-line px-3 font-medium transition hover:bg-surface"
                >
                  Remover
                </button>
              ))}
          </li>
        ))}
      </ul>

      {podeAdicionarConta(contas) && (
        <div className="mt-5 border-t border-line pt-4">
          <p className="text-xs text-muted">
            O Mercado Livre conecta a conta que está logada no navegador. Para adicionar outra,
            saia da conta atual no site do Mercado Livre antes.
          </p>
          <button
            type="button"
            onClick={() => void adicionar()}
            disabled={adicionando}
            className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          >
            {adicionando ? "Redirecionando…" : "Adicionar outra conta"}
          </button>
        </div>
      )}
    </section>
  );
}
