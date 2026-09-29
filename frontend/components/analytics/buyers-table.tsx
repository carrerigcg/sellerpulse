"use client";

import { useMemo, useState } from "react";

import type { RfmLinha } from "@/lib/api";

import { definicaoSegmento } from "./segmentos";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

type Coluna = {
  chave: keyof RfmLinha;
  rotulo: string;
  alinhamento?: "right";
};

const COLUNAS: Coluna[] = [
  { chave: "buyer_id", rotulo: "Comprador" },
  { chave: "recency_dias", rotulo: "Recência (dias)", alinhamento: "right" },
  { chave: "frequency", rotulo: "Frequência", alinhamento: "right" },
  { chave: "monetary", rotulo: "Valor", alinhamento: "right" },
  { chave: "r_score", rotulo: "R", alinhamento: "right" },
  { chave: "f_score", rotulo: "F", alinhamento: "right" },
  { chave: "m_score", rotulo: "M", alinhamento: "right" },
  { chave: "segmento", rotulo: "Segmento" },
];

/**
 * Tabela de compradores ordenável — clicar num cabeçalho ordena por aquela
 * coluna, clicar de novo inverte. Estado só de ordenação (sem paginação:
 * a base de compradores de um seller não costuma passar de algumas
 * centenas por janela, `overflow-y-auto` já resolve).
 *
 * Compartilhado entre `/dashboard/clientes` e `/demo/clientes` desde o
 * Checkpoint 2 da Sprint 3.
 */
export function BuyersTable({ dados }: { dados: RfmLinha[] }) {
  const [ordem, setOrdem] = useState<{ chave: keyof RfmLinha; direcao: "asc" | "desc" }>({
    chave: "monetary",
    direcao: "desc",
  });

  const ordenados = useMemo(() => {
    const copia = [...dados];
    copia.sort((a, b) => {
      const va = a[ordem.chave];
      const vb = b[ordem.chave];
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return ordem.direcao === "asc" ? cmp : -cmp;
    });
    return copia;
  }, [dados, ordem]);

  function alternarOrdem(chave: keyof RfmLinha) {
    setOrdem((atual) =>
      atual.chave === chave
        ? { chave, direcao: atual.direcao === "asc" ? "desc" : "asc" }
        : { chave, direcao: "desc" },
    );
  }

  return (
    <div className="mt-4 max-h-[28rem] overflow-y-auto rounded-lg border border-line">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            {COLUNAS.map((coluna) => (
              <th
                key={coluna.chave}
                className={`px-3 py-2 font-medium ${coluna.alinhamento === "right" ? "text-right" : ""}`}
              >
                <button
                  type="button"
                  onClick={() => alternarOrdem(coluna.chave)}
                  className="inline-flex items-center gap-1 hover:text-accent"
                >
                  {coluna.rotulo}
                  {ordem.chave === coluna.chave && (
                    <span aria-hidden>{ordem.direcao === "asc" ? "↑" : "↓"}</span>
                  )}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordenados.map((linha) => {
            const def = definicaoSegmento(linha.segmento);
            return (
              <tr key={linha.buyer_id} className="border-t border-line">
                <td className="px-3 py-2 text-muted">#{linha.buyer_id}</td>
                <td className="tabular px-3 py-2 text-right">{linha.recency_dias}</td>
                <td className="tabular px-3 py-2 text-right">{linha.frequency}</td>
                <td className="tabular px-3 py-2 text-right">{brl.format(linha.monetary)}</td>
                <td className="tabular px-3 py-2 text-right">{linha.r_score}</td>
                <td className="tabular px-3 py-2 text-right">{linha.f_score}</td>
                <td className="tabular px-3 py-2 text-right">{linha.m_score}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${def.badge}`}>
                    {def.rotulo}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
