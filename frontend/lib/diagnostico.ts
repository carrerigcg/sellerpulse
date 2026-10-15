/**
 * Diagnóstico de anúncio a partir de visitas e conversão.
 *
 * Transforma dois números num 2×2 acionável:
 *
 *                       | conversão abaixo | conversão acima
 *   visitas acima       | visto e rejeitado| campeão
 *   visitas abaixo      | cauda            | converte, falta ser visto
 *
 * As réguas são as medianas da PRÓPRIA LOJA, nunca constantes. Taxa saudável
 * de conversão varia por categoria, então "abaixo de 1% é ruim" seria chute —
 * e este projeto já removeu um percentual de custo chutado por exatamente
 * isso: número inventado some dentro de uma conta e vira verdade.
 *
 * Função pura, separada do componente, porque o modo de falha aqui é
 * silencioso. Um quadrante trocado não derruba nada: mostra um rótulo errado,
 * com toda a confiança, e o vendedor mexe no produto errado.
 */

export type Diagnostico =
  | "visto-e-rejeitado"
  | "converte-falta-ser-visto"
  | "campeao"
  | "cauda"
  | "poucas-visitas"
  | "sem-visita"
  | "sem-referencia";

export type LinhaDeFunil = {
  unidades: number;
  /** `null` = nunca colhido. Diferente de `0`, que é colhido e deu zero. */
  visitas: number | null;
  /** Porcentagem (4.8 = 4,8%). `null` sem visita para dividir. */
  conversao: number | null;
};

export type Referencia = {
  /** Mediana da conversão da loja, em porcentagem. */
  medianaConversao: number;
  /** Mediana das visitas por produto. */
  medianaVisitas: number;
  /** Quantos produtos sustentam essas medianas. */
  diagnosticaveis: number;
  /** `false` quando há poucos produtos para a mediana significar algo. */
  confiavel: boolean;
};

/**
 * Mínimo de produtos para a mediana ser uma régua.
 *
 * Com menos que isso a mediana é praticamente o valor de um produto, e o
 * quadrante vira sorteio. É guarda de EXIBIÇÃO, não regra de negócio — daí o
 * número redondo. O que ela protege é o leitor de uma conclusão que não
 * existe.
 */
export const MIN_PRODUTOS_PARA_REFERENCIA = 5;

function mediana(valores: readonly number[]): number {
  if (valores.length === 0) return 0;
  const ordenado = [...valores].sort((a, b) => a - b);
  const meio = Math.floor(ordenado.length / 2);
  return ordenado.length % 2 === 0
    ? (ordenado[meio - 1] + ordenado[meio]) / 2
    : ordenado[meio];
}

/**
 * Quantas vendas o produto precisaria ter como expectativa para ser avaliado.
 *
 * DOIS, e não um, e a diferença não é calibragem — é um defeito lógico.
 *
 * Nesta população todo produto vendeu ao menos uma vez (a lista sai de
 * `order_items`), então a conversão MÍNIMA possível é `1/visitas`. Com o
 * limiar em uma venda esperada, o produto na fronteira converte praticamente
 * na mediana — a faixa que sobra para ele ficar ABAIXO dela é de frações de
 * ponto percentual, e na prática ninguém cai nela.
 *
 * (Não é zero matemático: o arredondamento das visitas deixa uma folga de
 * ~0,1 ponto. É estreita o bastante para o quadrante "cauda" ficar vazio no
 * dado real, que é o que importa.)
 *
 * Medido na loja real em 2026-10-15, com 431 produtos:
 *
 *   esperadas  diagnosticáveis  rejeitado  campeão  falta-ser-visto  cauda
 *       1           229            94        39          96            0
 *       2            91            36        13          33            9
 *
 * A mediana de conversão caiu de 9,09% para 4,84% na mesma mudança: os 9%
 * eram inflação de amostra pequena, não a conversão da loja.
 *
 * Três seria ainda mais seguro e diagnosticaria só 59 dos 431. Dois é onde os
 * quatro quadrantes existem e ainda sobra catálogo para olhar.
 */
export const VENDAS_ESPERADAS_MINIMAS = 2;

/**
 * Um produto tem visita suficiente para a conversão dele significar algo?
 *
 * A regra: na conversão típica da loja, ele deveria ter tido ao menos
 * `VENDAS_ESPERADAS_MINIMAS` vendas. Com 8 visitas e mediana de 4,8%, o
 * esperado eram 0,4 vendas — não dá para concluir nada a partir disso.
 *
 * Sem esta trava, um item com 3 visitas e 1 venda marca 33% e lidera qualquer
 * ordenação por conversão. O dado real da loja medida já tem casos assim.
 */
function temAmostraSuficiente(visitas: number, medianaConversao: number): boolean {
  return visitas * (medianaConversao / 100) >= VENDAS_ESPERADAS_MINIMAS;
}

/** Produtos que têm visita medida e conversão calculável. */
function comMedicao(linhas: readonly LinhaDeFunil[]): LinhaDeFunil[] {
  return linhas.filter(
    (l) => l.visitas !== null && l.visitas > 0 && l.conversao !== null && Number.isFinite(l.conversao),
  );
}

/**
 * Calcula as medianas que servem de régua.
 *
 * Duas passagens de propósito. A primeira mediana sai de todo produto com
 * visita; ela é usada só para decidir quem tem amostra suficiente. A segunda
 * — a que vale — sai apenas desses.
 *
 * Sem isso, uma loja cujos produtos quase todos têm 2 ou 3 visitas teria a
 * régua definida por conversões de amostra mínima (33%, 50%), e os produtos
 * de verdade apareceriam todos "abaixo da mediana".
 */
export function calculaReferencia(linhas: readonly LinhaDeFunil[]): Referencia {
  const medidos = comMedicao(linhas);
  if (medidos.length === 0) {
    return { medianaConversao: 0, medianaVisitas: 0, diagnosticaveis: 0, confiavel: false };
  }

  const provisoria = mediana(medidos.map((l) => l.conversao as number));
  const confiaveis = medidos.filter((l) =>
    temAmostraSuficiente(l.visitas as number, provisoria),
  );

  const base = confiaveis.length > 0 ? confiaveis : medidos;
  return {
    medianaConversao: mediana(base.map((l) => l.conversao as number)),
    medianaVisitas: mediana(base.map((l) => l.visitas as number)),
    diagnosticaveis: confiaveis.length,
    confiavel: confiaveis.length >= MIN_PRODUTOS_PARA_REFERENCIA,
  };
}

/**
 * Classifica um produto. A ordem das travas importa.
 *
 * Empate na mediana conta como ACIMA, nos dois eixos. É arbitrário, e o que
 * importa é ser consistente: sem uma regra fixa, um produto exatamente na
 * mediana trocaria de quadrante conforme a implementação da comparação.
 */
export function diagnostica(linha: LinhaDeFunil, ref: Referencia): Diagnostico {
  if (linha.visitas === null) return "sem-visita";
  if (!ref.confiavel) return "sem-referencia";
  if (linha.conversao === null || !temAmostraSuficiente(linha.visitas, ref.medianaConversao)) {
    return "poucas-visitas";
  }

  const muitaVisita = linha.visitas >= ref.medianaVisitas;
  const converteObem = linha.conversao >= ref.medianaConversao;

  if (muitaVisita && !converteObem) return "visto-e-rejeitado";
  if (!muitaVisita && converteObem) return "converte-falta-ser-visto";
  if (muitaVisita && converteObem) return "campeao";
  return "cauda";
}

/** Rótulo e cor de cada diagnóstico, para a tela não espalhar `switch`. */
export const APARENCIA: Record<
  Diagnostico,
  { rotulo: string; cor: string; acao: string; pedeAtencao: boolean }
> = {
  "visto-e-rejeitado": {
    rotulo: "Visto e rejeitado",
    cor: "bg-negative",
    acao: "É visto acima da média e converte abaixo. O gargalo está no anúncio: preço, foto, título ou frete.",
    pedeAtencao: true,
  },
  "converte-falta-ser-visto": {
    rotulo: "Converte, falta ser visto",
    cor: "bg-accent",
    acao: "Converte acima da média com pouca visita. O anúncio funciona — falta visibilidade.",
    pedeAtencao: true,
  },
  campeao: {
    rotulo: "Campeão",
    cor: "bg-positive",
    acao: "Muita visita e conversão acima da média. Proteger estoque.",
    pedeAtencao: false,
  },
  cauda: {
    rotulo: "Cauda",
    cor: "bg-muted",
    acao: "Pouca visita e conversão abaixo da média.",
    pedeAtencao: false,
  },
  "poucas-visitas": {
    rotulo: "Poucas visitas para avaliar",
    cor: "bg-line",
    acao: "Na conversão típica da loja, este produto deveria ter tido menos de uma venda no período. Qualquer leitura seria ruído.",
    pedeAtencao: false,
  },
  "sem-visita": {
    rotulo: "Sem visita colhida",
    cor: "bg-line",
    acao: "O Mercado Livre ainda não entregou visitas deste anúncio.",
    pedeAtencao: false,
  },
  "sem-referencia": {
    rotulo: "Sem referência",
    cor: "bg-line",
    acao: "Poucos produtos com visita suficiente para a mediana da loja significar algo.",
    pedeAtencao: false,
  },
};

/** Contagem por diagnóstico, na ordem em que a tela mostra os filtros. */
export const ORDEM_DOS_FILTROS: Diagnostico[] = [
  "visto-e-rejeitado",
  "converte-falta-ser-visto",
  "campeao",
  "cauda",
  "poucas-visitas",
  "sem-visita",
  "sem-referencia",
];
