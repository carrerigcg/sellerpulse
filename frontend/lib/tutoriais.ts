/**
 * Conteúdo e regras do tutorial das telas de análise.
 *
 * Desenho em `docs/specs/2026-10-22-tutorial-das-telas-design.md`, que traz
 * também a FONTE NO CÓDIGO de cada afirmação abaixo. Texto que descreve o
 * produto errado é a mesma falha de número inventado — ao mudar uma frase,
 * confira a fonte, e suba a `versao` da tela para quem já viu ver de novo.
 *
 * Sem React de propósito: o front deste projeto não testa componentes, então
 * a lógica que importa mora aqui, testável no vitest.
 */

export type ChaveDeTutorial =
  | "resumo"
  | "executive"
  | "produtos"
  | "clientes"
  | "custos"
  | "exportar";

export type Contexto = "demo" | "dashboard";

export type Slide = { titulo: string; texto: string };

export type Tutorial = {
  /** Sobe quando o texto muda: o tutorial reaparece só para esta tela. */
  versao: number;
  slides: Slide[];
  /**
   * Só quando a tela da demo é OUTRA coisa — hoje, apenas Custos, que lá é
   * só leitura. Os demais textos são neutros e servem nos dois contextos:
   * uma lista de variantes para trocar uma palavra duplicaria os outros
   * slides, e conteúdo duplicado diverge.
   */
  slidesDaDemo?: Slide[];
};

export const TUTORIAIS: Record<ChaveDeTutorial, Tutorial> = {
  // A tela de entrada. Explica a palavra que ela usa ("sobra") e onde fica o
  // resto — quem não lê gráfico precisa, antes de tudo, saber para onde ir.
  resumo: {
    // v3 em 2026-10-27: o frete passou a ser buscado e descontado (v2 dizia
    // que não entrava, e naquele dia não entrava mesmo).
    versao: 3,
    slides: [
      {
        titulo: "O que é a sobra",
        texto:
          "É o que fica das vendas depois de pagar a comissão do Mercado Livre, o frete e o custo dos produtos informado na tela de Custos. Aluguel, salários e outras despesas também saem daí — por isso não é lucro.",
      },
      {
        titulo: "O que fazer e onde ver mais",
        texto:
          "Os cartões de baixo mostram o que pede atenção agora, e cada botão abre a tela com os detalhes. As outras telas ficam no menu: Financeiro, Produtos, Clientes, Custos e Exportar.",
      },
    ],
  },
  executive: {
    // v3 em 2026-10-27: o frete passou a ser buscado e descontado (v2 dizia
    // que não entrava, e naquele dia não entrava mesmo).
    versao: 3,
    slides: [
      {
        titulo: "Margem de contribuição não é lucro",
        texto:
          "É a receita menos a comissão do Mercado Livre, o frete que você pagou e o custo dos produtos. Aluguel, salários e outras despesas fixas não entram: por isso é margem, e não lucro.",
      },
      {
        titulo: "Quanto da conta está completa",
        texto:
          "O custo do produto só entra quando é informado na tela de Custos. Se falta custo, um aviso abaixo dos cartões mostra quanto da receita já está coberta — e, até chegar a 100%, a margem aparece maior do que a real.",
      },
      {
        titulo: "Comparação e período",
        texto:
          "Cada cartão compara com o período anterior de mesmo tamanho. E o “Até” do seletor não inclui o próprio dia: escolher 13/10 mostra os dados até 12/10.",
      },
    ],
  },
  produtos: {
    versao: 1,
    slides: [
      {
        titulo: "Classes A, B e C",
        texto:
          "Os produtos são ordenados por receita. A classe A soma os primeiros 80% do faturamento do período, a B vai até 95%, e a C é o restante.",
      },
      {
        titulo: "Quem é visto e não vende",
        texto:
          "Em Desempenho dos anúncios, cada anúncio é comparado com a mediana da própria loja. “Visto e rejeitado” pede ajuste no anúncio — preço, foto, título ou frete. “Converte, falta ser visto” pede visibilidade.",
      },
      {
        titulo: "Quando não dá para concluir",
        texto:
          "Anúncio com poucas visitas aparece como “Poucas visitas para avaliar”, sem diagnóstico, para não virar alarme falso. E, em Desempenho dos anúncios, “—” quer dizer que falta dado para calcular — não é zero.",
      },
    ],
  },
  clientes: {
    versao: 1,
    slides: [
      {
        titulo: "Recência, Frequência e Valor",
        texto:
          "Cada comprador recebe uma nota em três critérios: há quanto tempo comprou, quantas vezes comprou e quanto gastou.",
      },
      {
        titulo: "Os segmentos que pedem ação",
        texto:
          "As notas viram seis segmentos. Os que pedem atenção: “Em risco” — já foram bons compradores e estão sumindo — e “Hibernando”, que provavelmente já foram embora.",
      },
      {
        titulo: "Como ler o gráfico",
        texto:
          "Cada ponto é um comprador. Quem está embaixo à direita comprou há muito tempo e gasta pouco: é quem está indo embora.",
      },
    ],
  },
  custos: {
    // v2 em 2026-10-28: o slide 2 dizia que o custo só valia daqui para
    // frente; passou a existir a opção de aplicar às vendas sem custo.
    versao: 2,
    slides: [
      {
        titulo: "Por que informar o custo",
        texto:
          "O Mercado Livre não sabe quanto o produto custa para você. Sem esse número, a margem de contribuição fica maior do que a real.",
      },
      {
        titulo: "E as vendas que já aconteceram",
        texto:
          "Com a opção do topo ligada, o custo salvo também vale para as vendas anteriores que estão sem custo. Um período em que você já informou um custo nunca muda: se o fornecedor subir o preço, a margem dos meses passados continua a mesma.",
      },
      {
        titulo: "Por onde começar",
        texto: "Comece pelos produtos que mais faturam: são eles que mais mexem na margem.",
      },
    ],
    slidesDaDemo: [
      {
        titulo: "O custo que só o vendedor sabe",
        texto:
          "Aqui o vendedor informa quanto cada produto custa para ele — o único número que o Mercado Livre não tem. Sem ele, a margem fica maior do que a real.",
      },
      {
        titulo: "Nesta demonstração",
        texto:
          "A tabela é só leitura. Alguns produtos estão sem custo de propósito, para você ver como as outras telas avisam quando a margem está incompleta.",
      },
    ],
  },
  exportar: {
    versao: 1,
    slides: [
      {
        titulo: "Leve os números para a planilha",
        texto:
          "Cada tabela sai num arquivo CSV. Dá para baixar uma de cada vez ou todas de uma vez — e, mesmo assim, cada uma vem no seu próprio arquivo.",
      },
      {
        titulo: "Abre direto no Excel",
        texto:
          "O arquivo já vem no formato do Excel em português: ponto e vírgula entre colunas, vírgula nos decimais e acentos preservados. Nesta tela há um glossário explicando cada coluna.",
      },
    ],
  },
};

export function slidesDoContexto(tutorial: Tutorial, contexto: Contexto): Slide[] {
  return contexto === "demo" && tutorial.slidesDaDemo ? tutorial.slidesDaDemo : tutorial.slides;
}

/**
 * Chave do "já vi" no `localStorage`. Contexto separado de propósito: quem
 * viu na demo e criou conta vê de novo, agora com os próprios números.
 */
export function chaveDeArmazenamento(
  contexto: Contexto,
  tela: ChaveDeTutorial,
  versao: number,
): string {
  return `sellerpulse:tutorial:${contexto}:${tela}:v${versao}`;
}

/**
 * As condições para abrir sem a pessoa pedir.
 *
 * `temDados`: tela vazia ou com erro não abre. Um usuário recém-cadastrado
 * cai no dashboard sem pedido e com o atalho para conectar a conta — um modal
 * explicando margem por cima disso esconderia a ação mais importante dele.
 *
 * `armazenamentoDisponivel`: sem como lembrar que já viu, abriria em toda
 * visita. Melhor não abrir sozinho; o botão continua funcionando.
 *
 * `chegouFiltrado`: a pessoa veio por um atalho que já mostra o que ela quer
 * ver — os cartões do Resumo abrem Produtos e Clientes rolados e filtrados.
 * Um modal por cima esconderia exatamente isso. Como não abre, também não
 * marca como visto: o tutorial abre na próxima visita direta à tela.
 */
export function deveAbrirSozinho(estado: {
  jaVisto: boolean;
  temDados: boolean;
  armazenamentoDisponivel: boolean;
  chegouFiltrado: boolean;
}): boolean {
  return (
    estado.armazenamentoDisponivel && estado.temDados && !estado.jaVisto && !estado.chegouFiltrado
  );
}

export function contextoDaRota(pathname: string): Contexto {
  return pathname === "/demo" || pathname.startsWith("/demo/") ? "demo" : "dashboard";
}
