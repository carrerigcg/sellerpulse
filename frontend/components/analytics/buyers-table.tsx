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
  /**
   * Rótulo curto pro celular. Aqui quem manda na largura da coluna é o
   * cabeçalho, não o dado: "Frequência" ocupa 103px pra mostrar números de
   * um dígito. Encurtar o rótulo estreita a coluna sem esconder nada.
   */
  rotuloCurto?: string;
  /**
   * Largura da coluna no celular, onde a tabela é `table-fixed`. Só as
   * visíveis precisam. Medido com dado real: os pisos são Segmento 96px (a
   * etiqueta "Hibernando" não quebra), Valor 74px ("R$ 12.480" numa linha) e
   * Dias 42px (o cabeçalho). O "#" fica com o que sobra porque é o único
   * elástico — um identificador quebra em duas linhas sem perder nada.
   */
  larguraCelular?: string;
};

const COLUNAS: Coluna[] = [
  { chave: "buyer_id", rotulo: "Comprador", rotuloCurto: "#", larguraCelular: "w-[22%]" },
  {
    chave: "recency_dias",
    rotulo: "Recência (dias)",
    rotuloCurto: "Dias",
    alinhamento: "right",
    larguraCelular: "w-[16%]",
  },
  // Escondida no celular mesmo com rótulo curto: encurtar "Frequência" pra
  // "Pedidos" ainda deixava as colunas em 411px contra os 325 disponíveis.
  // É a candidata certa porque é quase uma constante — na loja conectada
  // hoje, 708 dos 778 compradores têm frequência 1. Quem precisa do número
  // vê no desktop; quem está no celular ganha o Segmento inteiro na tela.
  { chave: "frequency", rotulo: "Frequência", alinhamento: "right", soNoDesktop: true },
  { chave: "monetary", rotulo: "Valor", alinhamento: "right", larguraCelular: "w-[28%]" },
  { chave: "r_score", rotulo: "R", alinhamento: "right", soNoDesktop: true },
  { chave: "f_score", rotulo: "F", alinhamento: "right", soNoDesktop: true },
  { chave: "m_score", rotulo: "M", alinhamento: "right", soNoDesktop: true },
  { chave: "segmento", rotulo: "Segmento", larguraCelular: "w-[34%]" },
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
      {/* `table-fixed` no celular pelo mesmo motivo da tabela ABC: as quatro
          colunas visíveis somam 307px de largura natural contra os 283 do
          cartão, e `break-words` sozinho não resolve — `overflow-wrap` não
          diminui a largura mínima intrínseca que o layout automático usa, só
          quebra o texto depois que a largura já foi imposta. Com as larguras
          fixadas, o "#" quebra em duas linhas e tudo cabe.
          `sm:table-auto` devolve o comportamento original no desktop. */}
      <table className="w-full table-fixed text-left text-sm sm:table-auto">
        <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            {COLUNAS.map((coluna) => (
              <th
                key={coluna.chave}
                className={`px-2 py-2 font-medium sm:w-auto sm:px-3 ${coluna.larguraCelular ?? ""} ${coluna.alinhamento === "right" ? "text-right" : ""} ${coluna.soNoDesktop ? SO_NO_DESKTOP : ""}`}
              >
                {/* `aria-label` com o rótulo por extenso: o texto curto do
                    celular ("#", "Dias") é claro ao lado do dado, mas sozinho
                    num leitor de tela não diria nada. */}
                <button
                  type="button"
                  onClick={() => alternarOrdem(coluna.chave)}
                  aria-label={`Ordenar por ${coluna.rotulo}`}
                  className="inline-flex items-center gap-1 hover:text-accent"
                >
                  {coluna.rotuloCurto ? (
                    <>
                      <span className="sm:hidden">{coluna.rotuloCurto}</span>
                      <span className="hidden sm:inline">{coluna.rotulo}</span>
                    </>
                  ) : (
                    coluna.rotulo
                  )}
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
                {/* A ORDEM E A VISIBILIDADE destas células têm que bater com
                    `COLUNAS` uma a uma. O cabeçalho é gerado do array e o
                    corpo é escrito à mão, então esconder uma coluna só no
                    array desalinha a tabela inteira em silêncio: o dado
                    aparece sob o rótulo do vizinho. Foi o que aconteceu com
                    Frequência. Mexeu em `COLUNAS`, mexa aqui junto. */}
                <td className="break-words px-2 py-2 text-muted sm:px-3">#{linha.buyer_id}</td>
                <td className="tabular px-2 py-2 text-right sm:px-3">{linha.recency_dias}</td>
                <td className={`tabular px-2 py-2 text-right sm:px-3 ${SO_NO_DESKTOP}`}>
                  {linha.frequency}
                </td>
                <td className="tabular px-2 py-2 text-right sm:px-3">
                  {brl.format(linha.monetary)}
                </td>
                <td className={`tabular px-2 py-2 text-right sm:px-3 ${SO_NO_DESKTOP}`}>
                  {linha.r_score}
                </td>
                <td className={`tabular px-2 py-2 text-right sm:px-3 ${SO_NO_DESKTOP}`}>
                  {linha.f_score}
                </td>
                <td className={`tabular px-2 py-2 text-right sm:px-3 ${SO_NO_DESKTOP}`}>
                  {linha.m_score}
                </td>
                <td className="px-2 py-2 sm:px-3">
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
