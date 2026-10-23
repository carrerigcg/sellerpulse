import type { CSSProperties } from "react";

import type { SegmentoRfm } from "@/lib/api";

/**
 * Tradução e cor de exibição dos seis segmentos de RFM.
 *
 * `chave` é o rótulo em inglês que vem do backend (`src/segmentation.py`,
 * código congelado da Fase 2) — não muda. `rotulo` e `descricao` são só de
 * exibição.
 *
 * Cor: o design system do SellerPulse tem só quatro matizes reais (laranja
 * de ação, amarelo de realce, verde positivo, vermelho negativo) mais um
 * cinza neutro — não dá pra tirar 6 cores categóricas claramente distintas
 * dali sem inventar hex novo, o que a tarefa proíbe. A saída: usar os
 * quatro matizes + o cinza para os cinco segmentos com sentido semântico
 * parecido com o já usado no resto do dashboard (positivo = bom, negativo =
 * alerta, etc.), e reservar "Outros" — o segmento sem regra, o catch-all —
 * pra um marcador vazado (contorno cinza, sem preenchimento) em vez de uma
 * sexta cor. Isso também segue a régua do amarelo: `--sp-highlight` só
 * aparece como preenchimento (ponto do gráfico, fundo da etiqueta), nunca
 * como cor de texto.
 *
 * Como a paleta é curta, a identidade de cada segmento nunca depende só da
 * cor: toda etiqueta carrega o nome por extenso, e o tooltip do gráfico de
 * dispersão mostra o segmento e os três scores.
 *
 * Movido de `app/dashboard/clientes/segmentos.ts` no Checkpoint 2 da Sprint
 * 3: a demonstração pública (`/demo/clientes`) precisa da mesma tradução, e
 * duplicar este arquivo por tela violaria a mesma regra de "não duplicar
 * gráfico" que motivou extrair os componentes visuais.
 */
export type DefinicaoSegmento = {
  chave: SegmentoRfm;
  /**
   * Valor de `?segmento=` em Clientes (`lib/segmento-da-url.ts`). Em português
   * e sem espaço, como o `?diagnostico=` de Produtos: a chave em inglês
   * chegaria como "At+Risk" ou "At%20Risk" conforme quem montasse o link.
   */
  parametro: string;
  rotulo: string;
  descricao: string;
  /** Cor de preenchimento do ponto no gráfico de dispersão. */
  corGrafico: string;
  /** Só "Outros": contorno do marcador vazado, em vez de preenchimento. */
  contornoGrafico?: string;
  /** Classes Tailwind da etiqueta usada na tabela e na faixa de segmentos. */
  badge: string;
};

export const SEGMENTOS: DefinicaoSegmento[] = [
  {
    chave: "Champions",
    parametro: "campeoes",
    rotulo: "Campeões",
    descricao:
      "Compram com frequência, gastam bem e compraram recentemente — a base mais valiosa.",
    corGrafico: "var(--sp-positive)",
    badge: "bg-positive/10 text-positive",
  },
  {
    chave: "Loyal",
    parametro: "fieis",
    rotulo: "Fiéis",
    descricao: "Compram com frequência e gastam bem, mesmo sem ter comprado há pouco tempo.",
    corGrafico: "var(--sp-accent)",
    badge: "bg-accent/10 text-accent",
  },
  {
    chave: "At Risk",
    parametro: "em-risco",
    rotulo: "Em risco",
    descricao: "Já foram bons compradores e estão sumindo — a hora de tentar reengajar é agora.",
    corGrafico: "var(--sp-negative)",
    badge: "bg-negative/10 text-negative",
  },
  {
    chave: "New",
    parametro: "novos",
    rotulo: "Novos",
    descricao: "Compraram recentemente, ainda não deu tempo de repetir a compra.",
    corGrafico: "var(--sp-highlight)",
    badge: "bg-highlight/25",
  },
  {
    chave: "Hibernating",
    parametro: "hibernando",
    rotulo: "Hibernando",
    descricao: "Pouca recência, frequência e valor juntos — provavelmente já foram embora.",
    corGrafico: "var(--sp-muted)",
    badge: "bg-muted/10 text-muted",
  },
  {
    chave: "Others",
    parametro: "outros",
    rotulo: "Outros",
    descricao: "Não se encaixam claramente em nenhum dos padrões acima.",
    corGrafico: "var(--sp-bg)",
    contornoGrafico: "var(--sp-muted)",
    badge: "border border-line text-muted",
  },
];

/** O marcador do segmento fora do gráfico (legenda e chips), com "Outros" vazado. */
export function estiloDoMarcador(def: DefinicaoSegmento): CSSProperties {
  return {
    backgroundColor: def.contornoGrafico ? "transparent" : def.corGrafico,
    border: def.contornoGrafico ? `1.5px solid ${def.contornoGrafico}` : undefined,
  };
}

export function definicaoSegmento(chave: string): DefinicaoSegmento {
  return SEGMENTOS.find((s) => s.chave === chave) ?? SEGMENTOS[SEGMENTOS.length - 1];
}
