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
  /**
   * Fora do celular. R, F e M são as notas de 1 a 5 que *produzem* o
   * segmento; o selo da coluna Segmento é a versão legível das três. Numa
   * tela de 375px elas empurravam justamente o Segmento pra fora do campo
   * de visão — some com o resumo e sobra a matéria-prima.
   */
  soNoDesktop?: boolean;
};

const COLUNAS: Coluna[] = [
  { chave: "buyer_id", rotulo: "Comprador" },
  { chave: "recency_dias", rotulo: "Recência (dias)", alinhamento: "right" },
  { chave: "frequency", rotulo: "Frequência", alinhamento: "right" },
  { chave: "monetary", rotulo: "Valor", alinhamento: "right" },
  { chave: "r_score", rotulo: "R", alinhamento: "right", soNoDesktop: true },
  { chave: "f_score", rotulo: "F", alinhamento: "right", soNoDesktop: true },
  { chave: "m_score", rotulo: "M", alinhamento: "right", soNoDesktop: true },
  { chave: "segmento", rotulo: "Segmento" },
];

/**
 * `hidden` é `display: none`, então a coluna escondida sai também da ordem
 * de tabulação: no celular não há botão de ordenar invisível pra receber
 * foco. A ordenação em si não depende de a coluna estar visível — ordenar
 * por `r_score` no desktop e estreitar a janela continua funcionando, só
 * deixa de mostrar a seta. E como a ordem inicial é por `monetary`, que é
 * visível, ninguém chega ao celular com a tabela ordenada por uma coluna
 * que não está vendo.
 */
const SO_NO_DESKTOP = "hidden sm:table-cell";

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
    // `overflow-x-auto` explícito: `overflow-y-auto` já forçava o eixo X pra
    // `auto` por regra da spec, então a rolagem lateral existia por efeito
    // colateral. Declarada, ela fica no código em vez de herdada por acidente.
    <div className="mt-4 max-h-[28rem] overflow-x-auto overflow-y-auto rounded-lg border border-line">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            {COLUNAS.map((coluna) => (
              <th
                key={coluna.chave}
                className={`px-3 py-2 font-medium ${coluna.alinhamento === "right" ? "text-right" : ""} ${coluna.soNoDesktop ? SO_NO_DESKTOP : ""}`}
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
                <td className={`tabular px-3 py-2 text-right ${SO_NO_DESKTOP}`}>
                  {linha.r_score}
                </td>
                <td className={`tabular px-3 py-2 text-right ${SO_NO_DESKTOP}`}>
                  {linha.f_score}
                </td>
                <td className={`tabular px-3 py-2 text-right ${SO_NO_DESKTOP}`}>
                  {linha.m_score}
                </td>
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
