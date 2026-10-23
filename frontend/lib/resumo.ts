/**
 * Regras e frases do Resumo da loja — a porta de entrada do produto.
 *
 * Desenho em `docs/specs/2026-10-23-resumo-da-loja-design.md`, com o texto
 * exato de cada frase na seção 4. Frase que descreve o número errado é a mesma
 * falha de número inventado: ao mudar uma, mude a spec junto.
 *
 * Sem React de propósito, como `lib/tutoriais.ts`: o front não testa
 * componentes, então a regra e o texto moram aqui, onde o vitest alcança —
 * inclusive a montagem que as duas páginas fazem com o resultado das buscas.
 * Imports relativos porque o vitest do projeto roda sem config e não resolve
 * o alias `@/` (medido).
 */
// `totalizarFluxo` é a conta dos cartões do Financeiro. Importá-la daqui, em
// vez de repetir a soma, é o que garante que a sobra do Resumo e a margem do
// cartão sejam o mesmo número.
import { totalizarFluxo } from "../components/analytics/executive-totals";
import type { FluxoDia } from "./api";
import { coberturaDoFluxo, type Cobertura } from "./cobertura";
import { calculaReferencia, diagnostica, type Diagnostico, type LinhaDeFunil } from "./diagnostico";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/** Valor absoluto em reais: o sentido vai na frase ("a mais", "caíram"), não no sinal. */
const reais = (valor: number) => brl.format(Math.abs(valor));

/**
 * Arredonda para longe do zero no meio, como o `Intl` arredonda ao formatar.
 * `Math.round(-1000.5)` dá −1000 e o cartão do Financeiro mostra −R$ 1.001: a
 * sobra do Resumo deixaria de bater com ele justo quando falta dinheiro.
 */
const arredonda = (valor: number) => Math.sign(valor) * Math.round(Math.abs(valor));

export type Totais = ReturnType<typeof totalizarFluxo>;

export type Veredito = {
  sobra: string;
  comparacao: string;
  /** Para a cor da linha de comparação — sempre junto do texto, nunca no lugar dele. */
  direcao: "mais" | "menos" | "igual" | "sem-comparacao";
  explicacao: string;
  maiorPeso: string | null;
  /** A comparação mistura coberturas de custo que puxam no mesmo sentido do custo. */
  avisoComparacao: string | null;
  avisoCobertura: string | null;
};

export function montaVeredito(entrada: {
  atual: Totais;
  /** `null` = o período anterior não teve venda. */
  anterior: Totais | null;
  coberturaAtual: Cobertura;
  coberturaAnterior: Cobertura | null;
}): Veredito {
  const { atual, anterior, coberturaAtual, coberturaAnterior } = entrada;
  const sobra = arredonda(atual.margem);
  const comum = {
    sobra:
      sobra >= 0
        ? `Sobraram ${reais(sobra)} das suas vendas.`
        : `As vendas não cobriram os custos: faltaram ${reais(sobra)}.`,
    explicacao: explicacao(sobra, coberturaAtual),
    avisoCobertura: avisoDeCobertura(coberturaAtual),
  };

  if (anterior === null) {
    return {
      ...comum,
      comparacao: "Não houve vendas nos 30 dias anteriores para comparar.",
      direcao: "sem-comparacao",
      maiorPeso: null,
      avisoComparacao: null,
    };
  }

  // Comparada já arredondada: "o mesmo" quer dizer o mesmo no número que a
  // tela mostra, e não uma diferença de centavos que ninguém vê.
  const sobraAnterior = arredonda(anterior.margem);
  const diferenca = sobra - sobraAnterior;
  if (diferenca === 0) {
    return {
      ...comum,
      comparacao: "O mesmo que nos 30 dias anteriores.",
      direcao: "igual",
      maiorPeso: null,
      avisoComparacao: null,
    };
  }

  // Com algum mês no negativo, "a mais" pegaria carona no "faltaram" de cima
  // e se leria ao contrário ("faltaram R$ 600 a mais" para uma falta que
  // diminuiu). Nesse caso a frase ganha sujeito próprio.
  const comparacao =
    sobra < 0 || sobraAnterior < 0
      ? `O resultado foi ${reais(diferenca)} ${diferenca > 0 ? "melhor" : "pior"} que nos 30 dias anteriores.`
      : `${reais(diferenca)} a ${diferenca > 0 ? "mais" : "menos"} do que sobrou nos 30 dias anteriores.`;

  return {
    ...comum,
    comparacao,
    direcao: diferenca > 0 ? "mais" : "menos",
    maiorPeso: oQueMaisPesou(atual, anterior, diferenca),
    avisoComparacao: avisoDeComparacao(atual, anterior, coberturaAtual, coberturaAnterior),
  };
}

/**
 * O que a sobra já descontou — e o que não. Com cobertura zero, dizer "depois
 * de pagar os produtos" seria afirmar um desconto que não aconteceu, na frase
 * que vem antes do aviso que o desmente.
 */
function explicacao(sobra: number, cobertura: Cobertura): string {
  const semCustoDeProduto = cobertura.vazia && !cobertura.semReceita;
  if (sobra < 0) {
    return semCustoDeProduto
      ? "Na conta entram o Mercado Livre e o frete — o custo dos produtos ainda não foi descontado. Aluguel, salários e outras despesas vêm depois."
      : "Na conta entram o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas vêm depois.";
  }
  return semCustoDeProduto
    ? "É o que fica depois de pagar o Mercado Livre e o frete — o custo dos produtos ainda não foi descontado. Aluguel, salários e outras despesas também saem daí."
    : "É o que fica depois de pagar o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas ainda saem daí.";
}

/**
 * A parte da conta que mais mexeu na sobra, no sentido da mudança.
 *
 * Antes do arredondamento as três fecham a diferença: `margem_contribuicao` é
 * receita − comissão − frete − custo dos produtos (`lib/api.ts`). Depois dele
 * a soma pode se afastar da diferença em um ou dois reais — e, numa diferença
 * de R$ 1, nenhuma parte pode ter andado no mesmo sentido. Daí o `null`.
 *
 * Só concorre quem empurrou para o mesmo lado: se a sobra caiu, vendas que
 * subiram não são o motivo da queda.
 */
function oQueMaisPesou(atual: Totais, anterior: Totais, diferenca: number): string | null {
  const partes = [
    { parte: "vendas", efeito: arredonda(atual.receita) - arredonda(anterior.receita) },
    { parte: "mercado-livre", efeito: arredonda(anterior.custo) - arredonda(atual.custo) },
    {
      parte: "produtos",
      efeito: arredonda(anterior.custoProdutos) - arredonda(atual.custoProdutos),
    },
  ] as const;

  const maior = partes
    .filter((p) => Math.sign(p.efeito) === Math.sign(diferenca))
    .sort((a, b) => Math.abs(b.efeito) - Math.abs(a.efeito))[0];
  if (!maior) return null;

  if (maior.parte === "vendas") {
    return `Principal motivo: as vendas ${maior.efeito > 0 ? "subiram" : "caíram"} ${reais(maior.efeito)} — de ${reais(anterior.receita)} para ${reais(atual.receita)}.`;
  }
  if (maior.parte === "mercado-livre") {
    return `Principal motivo: as tarifas do Mercado Livre e o frete ${maior.efeito < 0 ? "subiram" : "caíram"} ${reais(maior.efeito)}.`;
  }
  return `Principal motivo: o custo dos produtos ${maior.efeito < 0 ? "subiu" : "caiu"} ${reais(maior.efeito)}.`;
}

/**
 * Avisa quando parte da diferença vem de a conta ter ficado mais (ou menos)
 * completa, e não da loja.
 *
 * Só dispara quando a cobertura mudou NO MESMO SENTIDO do custo dos produtos:
 * mais vendas com custo informado fazem o custo subir sem a loja ter piorado.
 * Se a cobertura caiu e o custo subiu mesmo assim, a alta é real — e calar
 * sobre ela seria esconder uma piora. Independe de qual parte é o "principal
 * motivo": a cobertura distorce a comparação inteira, não só aquela linha.
 */
function avisoDeComparacao(
  atual: Totais,
  anterior: Totais,
  coberturaAtual: Cobertura,
  coberturaAnterior: Cobertura | null,
): string | null {
  if (!coberturaAnterior || coberturaAnterior.pct === coberturaAtual.pct) return null;
  const sentidoDaCobertura = Math.sign(coberturaAtual.fracao - coberturaAnterior.fracao);
  const sentidoDoCusto = Math.sign(arredonda(atual.custoProdutos) - arredonda(anterior.custoProdutos));
  if (sentidoDoCusto === 0 || sentidoDaCobertura !== sentidoDoCusto) return null;
  return `Parte da diferença vem do custo informado: neste período, ${coberturaAtual.pct}% do valor vendido tinha custo; no anterior, ${coberturaAnterior.pct}%.`;
}

/**
 * No passado ("saiu sem custo") de propósito: o custo vale da data em que foi
 * informado em diante, então quem acabou de preencher tudo continua vendo este
 * aviso por até 30 dias. No presente, ele desmentiria o que a pessoa acabou de
 * fazer, e ela concluiria que o sistema não salvou.
 */
function avisoDeCobertura(c: Cobertura): string | null {
  if (c.semReceita || c.completa) return null;
  if (c.vazia) return "Nenhuma venda deste período saiu com custo informado.";
  return `${100 - c.pct}% do valor vendido neste período saiu sem custo informado — a sobra verdadeira é menor que essa.`;
}

export type ChaveDaTarefa = "custos" | "visto-e-rejeitado" | "clientes-em-risco";

export type Tarefa = {
  chave: ChaveDaTarefa;
  frase: string;
  apoio: string;
  botao: string;
  href: string;
};

export type LinksDoResumo = {
  base: "/dashboard" | "/demo";
  periodo: { de: string; ate: string };
  /** Os segmentos de cliente usam 90 dias — ver `montaTarefas`. */
  periodoClientes: { de: string; ate: string };
};

/** O que o Resumo usa de cada comprador (`RfmLinha`, em `lib/api.ts`). */
export type LinhaDeCliente = { segmento: string; monetary: number; recency_dias: number };

export const NADA_PEDINDO_ATENCAO = "Nada pedindo atenção agora.";
export const NADA_E_ANUNCIOS_SEM_AVALIACAO =
  "Nada pedindo atenção nos custos e nos clientes. Os anúncios ainda não têm visitas suficientes para avaliar.";
export const RESUMO_INCOMPLETO = "Parte do resumo não carregou agora. Tente de novo em instantes.";

function plural(n: number, um: string, varios: string): string {
  return n === 1 ? um : varios;
}

function link(
  caminho: string,
  periodo: { de: string; ate: string },
  extra: Record<string, string> = {},
  ancora = "",
): string {
  const consulta = new URLSearchParams({ de: periodo.de, ate: periodo.ate, ...extra });
  return `${caminho}?${consulta.toString()}${ancora}`;
}

export function hrefDoFinanceiro(links: LinksDoResumo): string {
  return link(`${links.base}/financeiro`, links.periodo);
}

export type ResultadoDasTarefas = {
  tarefas: Tarefa[];
  /** Alguma fonte falhou ao carregar. */
  incompleto: boolean;
  /** A régua da loja é confiável — sem ela, "nenhum anúncio" não quer dizer "nenhum problema". */
  anunciosAvaliados: boolean;
};

/**
 * Os cartões de "O que fazer agora", em ordem fixa e só os que se aplicam.
 *
 * Cada fonte é `null` quando a busca falhou. A tarefa dela some, e o resultado
 * marca `incompleto` — que o rodapé nunca transforma em "nada pedindo atenção".
 */
export function montaTarefas(entrada: {
  custos: readonly { custo_unitario: number | null }[] | null;
  abc: readonly LinhaDeFunil[] | null;
  rfm: readonly LinhaDeCliente[] | null;
  links: LinksDoResumo;
}): ResultadoDasTarefas {
  const { custos, abc, rfm, links } = entrada;
  const tarefas: Tarefa[] = [];
  const contagem = abc ? contaDiagnosticos(abc) : null;

  // Pelo custo vazio HOJE, que é a conta da tela de Custos — o número do
  // cartão tem que bater com o que ele vê ao clicar. Contar pela venda
  // passada (`produtosSemCusto`) daria outro número: custo informado hoje
  // não volta para trás, e o apoio diz isso para o efeito não parecer sumido.
  if (custos) {
    const n = custos.filter((l) => l.custo_unitario === null).length;
    if (n > 0) {
      tarefas.push({
        chave: "custos",
        frase: `${n} ${plural(n, "produto", "produtos")} que você vendeu ${plural(n, "está", "estão")} sem custo informado`,
        apoio: "Com o custo informado, as próximas vendas já descontam o produto.",
        botao: links.base === "/demo" ? "Ver custos" : "Informar custos",
        href: link(`${links.base}/custos`, links.periodo),
      });
    }
  }

  // "Média da loja" e não "mediana": é a palavra que a própria seção usa
  // ("É visto acima da média"), e é a que esse vendedor conhece.
  const rejeitados = contagem?.diagnosticos.get("visto-e-rejeitado") ?? 0;
  if (rejeitados > 0) {
    const n = rejeitados;
    tarefas.push({
      chave: "visto-e-rejeitado",
      frase: `${n} ${plural(n, "anúncio recebe", "anúncios recebem")} mais visitas que a média da sua loja, mas ${plural(n, "vende", "vendem")} menos`,
      apoio: "Muita gente entra e não compra — vale revisar preço, foto, título ou frete.",
      botao: "Ver os que vendem menos",
      href: link(
        `${links.base}/produtos`,
        links.periodo,
        { diagnostico: "visto-e-rejeitado" },
        "#desempenho-anuncios",
      ),
    });
  }

  // 90 dias, não 30: o segmento é calculado DENTRO da janela — a recência
  // conta do fim do período e as notas são quintis entre os compradores dela
  // (`backend/analytics/segmentation_pg.py`, `rfm_scores`). Em 30 dias, "Em
  // risco" passaria a significar "comprou há 25 dias".
  //
  // "Já compraram bem" e não "compravam bem": a regra do segmento é recência
  // baixa E (frequência OU valor altos), então nem todos compraram muitas
  // vezes. O que vale para todos é o número de dias sem comprar — e é ele que
  // diz "sumindo" sem precisar da palavra.
  if (rfm) {
    const emRisco = rfm.filter((c) => c.segmento === "At Risk");
    const n = emRisco.length;
    if (n > 0) {
      const total = emRisco.reduce((acc, c) => acc + c.monetary, 0);
      const dias = Math.min(...emRisco.map((c) => c.recency_dias));
      tarefas.push({
        chave: "clientes-em-risco",
        frase: `${n} ${plural(n, "cliente que já comprou", "clientes que já compraram")} bem com você não ${plural(n, "compra", "compram")} há ${dias} dias ou mais`,
        apoio: `Nos últimos 3 meses, ${plural(n, "gastou", "gastaram")} ${brl.format(total)} com você.`,
        botao: "Ver quais clientes",
        href: link(`${links.base}/clientes`, links.periodoClientes),
      });
    }
  }

  // Sem cartão de "converte, falta ser visto", de propósito (decisão do dono,
  // 2026-10-23): com o corte na mediana nos dois eixos, ele sai quase sempre
  // junto do de rejeitados e com o mesmo número, em qualquer loja — metade da
  // lista viraria efeito do método. O diagnóstico continua na seção de
  // Produtos, onde a comparação com a loja é o assunto.

  return {
    tarefas,
    incompleto: custos === null || abc === null || rfm === null,
    anunciosAvaliados: contagem?.confiavel ?? false,
  };
}

/** A mesma regra da seção Desempenho dos anúncios, para o número bater com o filtro de lá. */
function contaDiagnosticos(abc: readonly LinhaDeFunil[]): {
  diagnosticos: Map<Diagnostico, number>;
  confiavel: boolean;
} {
  const referencia = calculaReferencia(abc);
  const diagnosticos = new Map<Diagnostico, number>();
  for (const linha of abc) {
    const d = diagnostica(linha, referencia);
    diagnosticos.set(d, (diagnosticos.get(d) ?? 0) + 1);
  }
  return { diagnosticos, confiavel: referencia.confiavel };
}

export function rodapeDasTarefas(resultado: ResultadoDasTarefas): string | null {
  if (resultado.incompleto) return RESUMO_INCOMPLETO;
  if (resultado.tarefas.length > 0) return null;
  return resultado.anunciosAvaliados ? NADA_PEDINDO_ATENCAO : NADA_E_ANUNCIOS_SEM_AVALIACAO;
}

/** Valor de um `Promise.allSettled`, ou `null` se aquela busca falhou. */
function valorOuNulo<T>(resultado: PromiseSettledResult<T>): T | null {
  return resultado.status === "fulfilled" ? resultado.value : null;
}

/**
 * Tudo o que as páginas do Resumo fazem com o resultado das buscas, num lugar
 * só e testável: a página só busca (com os getters do contexto) e escreve a
 * mensagem de erro.
 *
 * Os dois fluxos são obrigatórios — sem o anterior, a frase de comparação
 * mentiria por omissão. Fluxo anterior que volta VAZIO (sem erro) é outra
 * coisa: não houve venda para comparar, e a frase diz isso.
 */
export function montaResumo(entrada: {
  fluxo: PromiseSettledResult<FluxoDia[]>;
  anterior: PromiseSettledResult<FluxoDia[]>;
  abc: PromiseSettledResult<readonly LinhaDeFunil[]>;
  custos: PromiseSettledResult<readonly { custo_unitario: number | null }[]>;
  rfm: PromiseSettledResult<readonly LinhaDeCliente[]>;
  links: LinksDoResumo;
}): {
  /** `motivo` é o erro da busca, para a página escrever a mensagem do contexto. */
  erroNoFluxo: { motivo: unknown } | null;
  semVendas: boolean;
  veredito: Veredito;
  tarefas: Tarefa[];
  rodape: string | null;
  hrefFinanceiro: string;
} {
  const falha = [entrada.fluxo, entrada.anterior].find(
    (r): r is PromiseRejectedResult => r.status === "rejected",
  );
  const dias = valorOuNulo(entrada.fluxo) ?? [];
  const diasAnteriores = valorOuNulo(entrada.anterior) ?? [];
  const resultado = montaTarefas({
    custos: valorOuNulo(entrada.custos),
    abc: valorOuNulo(entrada.abc),
    rfm: valorOuNulo(entrada.rfm),
    links: entrada.links,
  });

  return {
    erroNoFluxo: falha ? { motivo: falha.reason } : null,
    semVendas: dias.length === 0,
    veredito: montaVeredito({
      atual: totalizarFluxo(dias),
      anterior: diasAnteriores.length > 0 ? totalizarFluxo(diasAnteriores) : null,
      coberturaAtual: coberturaDoFluxo(dias),
      coberturaAnterior: diasAnteriores.length > 0 ? coberturaDoFluxo(diasAnteriores) : null,
    }),
    tarefas: resultado.tarefas,
    rodape: rodapeDasTarefas(resultado),
    hrefFinanceiro: hrefDoFinanceiro(entrada.links),
  };
}
