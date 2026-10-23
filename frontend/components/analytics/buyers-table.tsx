"use client";

import { useMemo, useState } from "react";

import type { RfmLinha, SegmentoRfm } from "@/lib/api";

import { ChipDeFiltro } from "./chip-de-filtro";
import { SEGMENTOS, definicaoSegmento, estiloDoMarcador } from "./segmentos";

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
  { chave: "buyer_id", rotulo: "Comprador", rotuloCurto: "#", larguraCelular: "w-[36%]" },
  // Escondida no celular pra que o identificador caiba inteiro. Com ela, as
  // quatro colunas pediam 312px contra os 283 do cartão, e quem pagava a
  // conta era o `#`: os 372 compradores apareciam com o número picado em
  // duas linhas ("#555 / 88495"). Um identificador partido no meio é o mesmo
  // defeito que a coluna de Valor evita ao não quebrar dentro do número.
  // Recência é a candidata certa a sair pelo mesmo motivo que R, F e M: o
  // selo de Segmento já a carrega de forma qualitativa — "Em risco",
  // "Hibernando" e "Novos" são, na origem, afirmações sobre recência.
  {
    chave: "recency_dias",
    rotulo: "Recência (dias)",
    alinhamento: "right",
    soNoDesktop: true,
  },
  // Escondida no celular mesmo com rótulo curto: encurtar "Frequência" pra
  // "Pedidos" ainda deixava as colunas em 411px contra os 325 disponíveis.
  // É a candidata certa porque é quase uma constante — na loja conectada
  // hoje, 708 dos 778 compradores têm frequência 1. Quem precisa do número
  // vê no desktop; quem está no celular ganha o Segmento inteiro na tela.
  { chave: "frequency", rotulo: "Frequência", alinhamento: "right", soNoDesktop: true },
  { chave: "monetary", rotulo: "Valor", alinhamento: "right", larguraCelular: "w-[29%]" },
  { chave: "r_score", rotulo: "R", alinhamento: "right", soNoDesktop: true },
  { chave: "f_score", rotulo: "F", alinhamento: "right", soNoDesktop: true },
  { chave: "m_score", rotulo: "M", alinhamento: "right", soNoDesktop: true },
  { chave: "segmento", rotulo: "Segmento", larguraCelular: "w-[35%]" },
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
 * Tabela de compradores ordenável e filtrável por segmento — clicar num
 * cabeçalho ordena por aquela coluna, clicar de novo inverte. Sem paginação:
 * a base de compradores de um seller não costuma passar de algumas centenas
 * por janela, `overflow-y-auto` já resolve.
 *
 * O filtro existe pelo cartão do Resumo. Ordenada por valor, a lista deixava
 * os clientes em risco espalhados no meio dos outros, e "Ver quais clientes"
 * levava a uma lista onde era preciso procurar quais.
 *
 * Compartilhado entre `/dashboard/clientes` e `/demo/clientes` desde o
 * Checkpoint 2 da Sprint 3.
 */
export function BuyersTable({
  dados,
  filtroInicial = null,
}: {
  dados: RfmLinha[];
  /** Vem do cartão do Resumo: a pessoa chega vendo os clientes de que a frase falava. */
  filtroInicial?: SegmentoRfm | null;
}) {
  const [ordem, setOrdem] = useState<{ chave: keyof RfmLinha; direcao: "asc" | "desc" }>({
    chave: "monetary",
    direcao: "desc",
  });
  const [filtro, setFiltro] = useState<SegmentoRfm | null>(filtroInicial);

  const contagens = useMemo(() => {
    const porSegmento = new Map<SegmentoRfm, number>();
    for (const linha of dados) {
      porSegmento.set(linha.segmento, (porSegmento.get(linha.segmento) ?? 0) + 1);
    }
    return porSegmento;
  }, [dados]);

  const ordenados = useMemo(() => {
    const copia = filtro ? dados.filter((l) => l.segmento === filtro) : [...dados];
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
  }, [dados, ordem, filtro]);

  function alternarOrdem(chave: keyof RfmLinha) {
    setOrdem((atual) =>
      atual.chave === chave
        ? { chave, direcao: atual.direcao === "asc" ? "desc" : "asc" }
        : { chave, direcao: "desc" },
    );
  }

  return (
    <>
      <div role="group" aria-label="Filtrar por segmento" className="mt-4 flex flex-wrap gap-2">
        <ChipDeFiltro ativo={filtro === null} onClick={() => setFiltro(null)}>
          Todos · {dados.length}
        </ChipDeFiltro>
        {/* O segmento ativo aparece mesmo com zero: quem chega por um link
            para um período sem clientes em risco precisa ver que o filtro
            está ligado e vazio, e não uma lista vazia sem explicação. */}
        {SEGMENTOS.filter((s) => (contagens.get(s.chave) ?? 0) > 0 || s.chave === filtro).map(
          (s) => (
            <ChipDeFiltro
              key={s.chave}
              ativo={filtro === s.chave}
              onClick={() => setFiltro(filtro === s.chave ? null : s.chave)}
            >
              <span className="h-2 w-2 shrink-0 rounded-full" style={estiloDoMarcador(s)} aria-hidden />
              {s.rotulo} · {contagens.get(s.chave) ?? 0}
            </ChipDeFiltro>
          ),
        )}
      </div>

      {/* `overflow-x-auto` explícito: `overflow-y-auto` já forçava o eixo X
          pra `auto` por regra da spec, então a rolagem lateral existia por
          efeito colateral. Declarada, ela fica no código em vez de herdada
          por acidente. */}
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
                  <td className={`tabular px-2 py-2 text-right sm:px-3 ${SO_NO_DESKTOP}`}>
                    {linha.recency_dias}
                  </td>
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

      {ordenados.length === 0 && (
        <p className="mt-4 text-xs text-muted">Nenhum comprador neste segmento no período.</p>
      )}
    </>
  );
}
