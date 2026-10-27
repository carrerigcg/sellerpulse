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
    "Ainda não calculado: a coluna sai vazia, e não com zero. O pedido do " +
    "Mercado Livre não traz o frete que o vendedor paga — ele só existe na " +
    "consulta de cada envio, que o SellerPulse ainda não faz. Por isso a " +
    "margem desta planilha ainda não desconta frete.",
  margem_contribuicao:
    "Receita bruta menos comissão menos o custo dos produtos que você " +
    "informou. O custo só entra quando informado — chutar um percentual daria " +
    "um número que parece lucro e não é —, e o frete ainda não entra. Por " +
    "isso a coluna se chama margem de contribuição, e não lucro.",
  custo_produtos:
    "O custo dos produtos vendidos no dia: quantidade vezes o custo unitário " +
    "que você informou, valendo a vigência da data do pedido. Só entra o que " +
    "você informou — o SellerPulse nunca estima esse valor. Informar o custo " +
    "hoje não muda a margem de ontem.",
  receita_sem_custo:
    "Quanto da receita do dia veio de produto sem custo informado. É a coluna " +
    "que mede o quanto a margem ao lado está incompleta: zero aqui significa " +
    "que a margem já considera o custo de tudo que foi vendido naquele dia.",
};

/** `backend/analytics/segmentation_pg.py`, `abc_pareto` (regra 80/15/5). */
export const GLOSSARIO_ABC: Glossario<AbcLinha> = {
  classe:
    "A, B ou C pela regra 80/15/5, lida na coluna de porcentagem acumulada: " +
    "A enquanto a acumulada for de até 80%, B até 95%, C daí em diante. O " +
    "produto que empurra a acumulada para além dos 80% já entra em B — a " +
    "fronteira fica logo antes dele, não nele. As classes saem do período " +
    "que você escolheu, então mudar o período pode mudar a classe de um " +
    "produto.",
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
  custo_produtos:
    "O custo informado para este produto, somado nas vendas do período. Zero " +
    "aqui pode significar duas coisas: custo informado como zero, ou custo " +
    "não informado. A coluna seguinte desempata.",
  receita_sem_custo:
    "Quanto da receita deste produto veio de venda sem custo informado. " +
    "Igual à receita significa que este produto não tem custo cadastrado; " +
    "zero significa que tem.",
  unidades: "Quantas unidades deste produto foram vendidas no período.",
  unidades_com_visita:
    "As unidades vendidas em dias com visita colhida. O Mercado Livre só " +
    "entrega os últimos 150 dias de visitas, então venda mais antiga que " +
    "isso não tem visita para comparar e fica de fora da conversão. É igual " +
    "às unidades sempre que o período começa depois do início da colheita.",
  visitas:
    "Quantas vezes o anúncio foi visto no período. Vazio significa que o " +
    "Mercado Livre ainda não entregou visitas deste anúncio — diferente de " +
    "zero, que significa que entregou e ninguém visitou. As visitas dos " +
    "últimos dois dias chegam incompletas: o Mercado Livre leva cerca de 48 " +
    "horas para consolidar.",
  conversao:
    "Unidades com visita medida divididas pelas visitas, em porcentagem. É a coluna " +
    "que separa dois problemas diferentes: produto com muita visita e pouca " +
    "venda é problema do anúncio — preço, foto, título; produto com pouca " +
    "visita é problema de tráfego. Um pedido com três unidades do mesmo " +
    "item conta como três aqui, embora tenha sido uma visita só — por isso " +
    "a tela chama de conversão por unidades, e não por pedido.",
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
    "Quantas compras pagas esse comprador fez no período. Conta compras, não " +
    "produtos nem pedidos: um carrinho com cinco produtos, que o Mercado Livre " +
    "divide em vários pedidos, conta 1.",
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
