/**
 * O que cada coluna do CSV é, e como é calculada.
 *
 * Duas decisões sobre o conteúdo:
 *
 * 1. Cada verbete diz o que a coluna É e de onde o número sai. Nada sobre o
 *    que fazer com ele. "Margem abaixo de 15% é ruim" seria palpite sobre um
 *    negócio que não conhecemos, e cada vendedor tem margem-alvo diferente.
 *    É a mesma intenção já travada para os relatórios: guia educativo, regra
 *    genérica, sem opinião de negócio.
 *
 * 2. As definições foram conferidas na fonte, não escritas de memória. As
 *    referências de arquivo em cada bloco são onde a conta mora de verdade.
 *
 * O tipo `Record<keyof T & string, string>` é o que mantém isto honesto: o
 * TypeScript recusa a compilação se uma coluna nova entrar em
 * `colunas-export.ts` sem ganhar verbete aqui, e também se um verbete falar
 * de uma coluna que não existe mais. O texto não pode silenciosamente
 * descrever um arquivo diferente do que o botão gera.
 */

import type { AbcLinha, FluxoDia, RfmLinha } from "./api";

export type Glossario<T> = Record<keyof T & string, string>;

/** `backend/analytics/metrics_pg.py`, `_FLUXO_QUERY` e linha 180. */
export const GLOSSARIO_FLUXO: Glossario<FluxoDia> = {
  date:
    "O dia em que o pedido foi fechado, no fuso de São Paulo — e não em UTC, " +
    "para que o dia da planilha seja o mesmo dia em que você conta a venda. " +
    "Há uma linha por dia com pedido pago: dia sem venda não aparece no " +
    "arquivo, em vez de aparecer com zero.",
  receita_bruta:
    "A soma do valor total dos pedidos pagos no dia, antes de qualquer " +
    "desconto. É o que entrou, não o que sobrou.",
  taxas_ml:
    "A soma da comissão que o Mercado Livre retém sobre esses pedidos.",
  frete:
    "A soma do custo de envio registrado nesses pedidos.",
  margem_contribuicao:
    "Receita bruta menos comissão menos frete. Não desconta o custo do " +
    "produto: o SellerPulse não conhece esse custo até você informar, e " +
    "chutar um percentual daria um número que parece lucro e não é. Por isso " +
    "a coluna se chama margem de contribuição, e não lucro.",
};

/** `backend/analytics/segmentation_pg.py`, `abc_pareto` (regra 80/15/5). */
export const GLOSSARIO_ABC: Glossario<AbcLinha> = {
  classe:
    "A, B ou C pela regra 80/15/5 sobre a receita acumulada: A até 80%, B " +
    "até 95%, C o resto. O produto que cruza a fronteira fica na classe de " +
    "cima. As classes são calculadas sobre o período inteiro que você " +
    "escolheu, então mudar o período pode mudar a classe de um produto.",
  sku:
    "O identificador do anúncio no Mercado Livre. Quando o anúncio foi " +
    "apagado, a venda continua no arquivo — a receita é real — e este campo " +
    "é o que sobrou para identificá-lo.",
  titulo: "O título do anúncio como estava no Mercado Livre.",
  receita: "Quanto esse produto faturou no período.",
  receita_pct:
    "Quanto esse produto representa da receita total do período, em " +
    "porcentagem. A soma da coluna dá 100.",
  receita_acumulada_pct:
    "A soma das porcentagens desde o produto de maior receita até este, na " +
    "ordem do arquivo. É esta coluna que define a classe: é a curva de " +
    "Pareto escrita em números.",
};

/** `src/segmentation.py`, `rfm_scores` e `_RFM_SEGMENT_RULES`. */
export const GLOSSARIO_RFM: Glossario<RfmLinha> = {
  buyer_id:
    "O identificador do comprador no Mercado Livre. Não há nome nem e-mail " +
    "aqui: o SellerPulse não recebe esses dados.",
  segmento:
    "O rótulo que sai da combinação dos três scores, por regras em ordem — a " +
    "primeira que casa vence. Champions: R, F e M todos 4 ou mais. Loyal: F " +
    "4 ou mais e M 3 ou mais. At Risk: R 2 ou menos, com F ou M em 3 ou " +
    "mais. New: R 4 ou mais e F 2 ou menos. Hibernating: R, F e M todos 2 ou " +
    "menos. Quem não casa com nenhuma fica em Others. Os rótulos estão em " +
    "inglês porque são os nomes consagrados da técnica.",
  recency_dias:
    "Quantos dias se passaram entre a última compra desse comprador e o fim " +
    "da janela que você escolheu — não até hoje. Com o período terminando em " +
    "12/10, recência 3 significa última compra em 09/10. E porque o fim da " +
    "janela é exclusivo, quem comprou no último dia incluído aparece com 1, " +
    "não com 0.",
  frequency:
    "Quantos pedidos pagos esse comprador fez no período. Conta pedidos, não " +
    "produtos: um pedido com cinco itens conta 1.",
  monetary: "Quanto esse comprador gastou no período, somando os pedidos pagos.",
  r_score:
    "A recência convertida em nota de 1 a 5, onde 5 é quem comprou mais " +
    "recentemente. A escala é invertida de propósito: menos dias é melhor.",
  f_score: "A frequência convertida em nota de 1 a 5, onde 5 é quem mais comprou.",
  m_score: "O valor gasto convertido em nota de 1 a 5, onde 5 é quem mais gastou.",
};

/**
 * Nota que vale para os três scores, e que não cabe repetida em cada verbete.
 *
 * É a armadilha que zerou os cartões de Clientes na demonstração em
 * 2026-10-12: com poucos compradores distintos, o topo da escala não chega a
 * 5, e os segmentos que exigem 4 ficam impossíveis por construção.
 */
export const NOTA_SOBRE_SCORES =
  "Os três scores são quintis calculados sobre os valores distintos que " +
  "aparecem no período, não sobre uma régua fixa: a nota é sempre relativa à " +
  "sua própria base. Quando há menos de cinco valores distintos, a escala " +
  "encurta e o topo não chega a 5 — num período com poucos compradores, " +
  "ninguém recebe nota máxima.";
