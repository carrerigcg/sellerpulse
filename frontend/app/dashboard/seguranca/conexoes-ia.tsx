"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { dataDaAutorizacao, ENDERECO_DO_MCP, nomeDoCliente } from "@/lib/conexoes-ia";
import { createClient } from "@/lib/supabase/client";

type Conexao = { clienteId: string; nome: string; desde: string };
type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; conexoes: Conexao[] };

const BOTAO =
  "inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface disabled:opacity-40";

/**
 * Conexões de IA: o que o vendedor autorizou a ler a loja, e o botão de cortar.
 *
 * Para todos os planos: quem saiu do Premium também precisa poder desconectar
 * (spec 2026-11-09-premium-mcp-conta-real, decisão 13). Desconectar apaga a
 * sessão do cliente no Supabase, e o backend recusa a chamada seguinte.
 */
export function ConexoesDeIa() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [desligando, setDesligando] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const titulo = useRef<HTMLHeadingElement>(null);

  const carrega = useCallback(async () => {
    const { data, error } = await createClient().auth.oauth.listGrants();
    if (error || !data) {
      setEstado({ tipo: "erro" });
      return;
    }
    setEstado({
      tipo: "pronto",
      conexoes: data.map((g) => ({
        clienteId: g.client.id,
        nome: nomeDoCliente(g.client.name),
        desde: dataDaAutorizacao(g.granted_at),
      })),
    });
  }, []);

  useEffect(() => {
    // Carga inicial: o setState acontece depois do await, fora do efeito.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carrega();
  }, [carrega]);

  async function desconecta(conexao: Conexao) {
    setAviso(null);
    setDesligando(conexao.clienteId);
    const { error } = await createClient().auth.oauth.revokeGrant({
      clientId: conexao.clienteId,
    });
    setDesligando(null);
    if (error) {
      setAviso(`Não foi possível desconectar ${conexao.nome}. Tente de novo.`);
      return;
    }
    setAviso(`${conexao.nome} foi desconectado.`);
    await carrega();
    requestAnimationFrame(() => titulo.current?.focus());
  }

  return (
    <section className="mt-6 rounded-xl border border-line p-5" aria-labelledby="titulo-conexoes-ia">
      <h2
        id="titulo-conexoes-ia"
        ref={titulo}
        tabIndex={-1}
        className="text-sm font-semibold outline-none"
      >
        Conexões de IA
      </h2>
      <p className="mt-1 text-sm text-muted">
        Os assistentes de IA que você autorizou a ler os números da sua loja. Desconectar corta
        o acesso na hora.
      </p>
      <p role="status" className="mt-2 text-sm">
        {aviso}
      </p>

      {estado.tipo === "carregando" && <p className="mt-3 text-sm text-muted">Carregando…</p>}
      {estado.tipo === "erro" && (
        <p className="mt-3 text-sm text-negative">
          Não foi possível carregar as conexões agora. Recarregue a página.
        </p>
      )}
      {estado.tipo === "pronto" && estado.conexoes.length === 0 && (
        <p className="mt-3 text-sm">
          Nenhuma conexão. No plano Premium, adicione o SellerPulse como conector no Claude com
          o endereço{" "}
          <code className="break-all rounded bg-surface px-1 py-0.5 text-xs">{ENDERECO_DO_MCP}</code>
          .
        </p>
      )}
      {estado.tipo === "pronto" && estado.conexoes.length > 0 && (
        <ul className="mt-3 divide-y divide-line">
          {estado.conexoes.map((c) => (
            <li
              key={c.clienteId}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div>
                <p className="text-sm font-medium">{c.nome}</p>
                <p className="text-xs text-muted">Autorizado em {c.desde}</p>
              </div>
              <button
                type="button"
                disabled={desligando !== null}
                onClick={() => desconecta(c)}
                className={`${BOTAO} text-negative`}
              >
                {desligando === c.clienteId ? "Desconectando…" : "Desconectar"}
                <span className="sr-only"> {c.nome}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
