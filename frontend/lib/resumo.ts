/**
 * Regras e frases do Resumo da loja — a porta de entrada do produto.
 *
 * Desenho em `docs/specs/2026-10-23-resumo-da-loja-design.md`, com o texto
 * exato de cada frase na seção 4. Frase que descreve o número errado é a mesma
 * falha de número inventado: ao mudar uma, mude a spec junto.
 *
 * Sem React de propósito, como `lib/tutoriais.ts`: o front não testa
 * componentes, então a regra e o texto moram aqui, onde o vitest alcança.
 * Imports relativos porque o vitest do projeto roda sem config e não resolve
 * o alias `@/` (medido).
 */
import type { Cobertura } from "./cobertura";
import { calculaReferencia, diagnostica, type Diagnostico, type LinhaDeFunil } from "./diagnostico";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/** Valor absoluto em reais: o sentido vai na frase ("a mais", "caíram"), não no sinal. */
const reais = (valor: number) => brl.format(Math.abs(valor));

/** O formato de `totalizarFluxo` (`components/analytics/executive-totals.ts`). */
export type Totais = { receita: number; custo: number; custoProdutos: number; margem: number };

export const EXPLICACAO_DA_SOBRA =
  "É o que fica depois de pagar o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas ainda saem daí.";

export type Veredito = {
  sobra: string;
  comparacao: string;
  /** Para a cor da linha de comparação — sempre junto do texto, nunca no lugar dele. */
  direcao: "mais" | "menos" | "igual" | "sem-comparacao";
  explicacao: string;
  maiorPeso: string | null;
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
  const sobra = Math.round(atual.margem);
  const comum = {
    sobra:
      sobra >= 0
        ? `Sobraram ${reais(sobra)} das suas vendas.`
        : `As vendas não cobriram os custos: faltaram ${reais(sobra)}.`,
    explicacao: EXPLICACAO_DA_SOBRA,
    avisoCobertura: avisoDeCobertura(coberturaAtual),
  };

  if (anterior === null) {
    return {
      ...comum,
      comparacao: "Não houve vendas nos 30 dias anteriores para comparar.",
      direcao: "sem-comparacao",
      maiorPeso: null,
    };
  }

  // Comparada já arredondada: "o mesmo" quer dizer o mesmo no número que a
  // tela mostra, e não uma diferença de centavos que ninguém vê.
  const diferenca = sobra - Math.round(anterior.margem);
  if (diferenca === 0) {
    return {
      ...comum,
      comparacao: "O mesmo que nos 30 dias anteriores.",
      direcao: "igual",
      maiorPeso: null,
    };
  }

  return {
    ...comum,
    comparacao: `${reais(diferenca)} a ${diferenca > 0 ? "mais" : "menos"} que nos 30 dias anteriores.`,
    direcao: diferenca > 0 ? "mais" : "menos",
    maiorPeso: oQueMaisPesou(atual, anterior, diferenca, coberturaAtual, coberturaAnterior),
  };
}

/**
 * A parte da conta que mais mexeu na sobra, no sentido da mudança.
 *
 * As três fecham a diferença: `margem_contribuicao` é receita − comissão −
 * frete − custo dos produtos (`lib/api.ts`). Só concorre quem empurrou para o
 * mesmo lado — se a sobra caiu, vendas que subiram não "pesaram" para a queda.
 *
 * Valores arredondados antes da conta, para a frase fechar na tela:
 * "caíram R$ 10.000 — de R$ 128.000 para R$ 118.000".
 */
function oQueMaisPesou(
  atual: Totais,
  anterior: Totais,
  diferenca: number,
  coberturaAtual: Cobertura,
  coberturaAnterior: Cobertura | null,
): string | null {
  const r = Math.round;
  const partes = [
    { parte: "vendas", efeito: r(atual.receita) - r(anterior.receita) },
    { parte: "mercado-livre", efeito: r(anterior.custo) - r(atual.custo) },
    { parte: "produtos", efeito: r(anterior.custoProdutos) - r(atual.custoProdutos) },
  ] as const;

  const maior = partes
    .filter((p) => Math.sign(p.efeito) === Math.sign(diferenca))
    .sort((a, b) => Math.abs(b.efeito) - Math.abs(a.efeito))[0];
  if (!maior) return null;

  if (maior.parte === "vendas") {
    return `O que mais pesou: as vendas ${maior.efeito > 0 ? "subiram" : "caíram"} ${reais(maior.efeito)} — de ${reais(anterior.receita)} para ${reais(atual.receita)}.`;
  }
  if (maior.parte === "mercado-livre") {
    return `O que mais pesou: o que o Mercado Livre e o frete levaram ${maior.efeito < 0 ? "subiu" : "caiu"} ${reais(maior.efeito)}.`;
  }
  // Quem preenche custos hoje faz as vendas novas passarem a descontar o
  // produto: o "custo dos produtos" sobe sem a loja ter piorado. Com
  // coberturas diferentes, culpar o custo seria tirar conclusão de uma
  // comparação desigual — então a frase diz isso em vez de culpar.
  if (coberturaAnterior && coberturaAnterior.pct !== coberturaAtual.pct) {
    return `A comparação mistura meses diferentes: neste, ${coberturaAtual.pct}% das vendas têm custo informado; no anterior, ${coberturaAnterior.pct}%.`;
  }
  return `O que mais pesou: o custo dos produtos ${maior.efeito < 0 ? "subiu" : "caiu"} ${reais(maior.efeito)}.`;
}

function avisoDeCobertura(c: Cobertura): string | null {
  if (c.semReceita || c.completa) return null;
  if (c.vazia) {
    return "Nenhuma venda deste mês tem custo informado — a sobra acima não desconta o custo dos produtos.";
  }
  return `${100 - c.pct}% das vendas deste mês estão sem custo informado — a sobra real é menor.`;
}

export type ChaveDaTarefa =
  | "custos"
  | "visto-e-rejeitado"
  | "clientes-em-risco"
  | "converte-falta-ser-visto";

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

export const NADA_PEDINDO_ATENCAO = "Nada pedindo atenção agora.";
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

/**
 * Os cartões de "O que fazer agora", em ordem fixa e só os que se aplicam.
 *
 * Cada fonte é `null` quando a busca falhou. A tarefa dela some, e o resultado
 * marca `incompleto` — que o rodapé nunca transforma em "nada pedindo atenção".
 */
export function montaTarefas(entrada: {
  custos: readonly { custo_unitario: number | null }[] | null;
  abc: readonly LinhaDeFunil[] | null;
  rfm: readonly { segmento: string; monetary: number }[] | null;
  links: LinksDoResumo;
}): { tarefas: Tarefa[]; incompleto: boolean } {
  const { custos, abc, rfm, links } = entrada;
  const tarefas: Tarefa[] = [];
  const contagem = abc ? contaDiagnosticos(abc) : null;

  // Pelo custo vazio HOJE, que é a conta da tela de Custos — o número do
  // cartão tem que bater com o que ele vê ao clicar. Contar pela venda
  // passada (`produtosSemCusto`) daria outro número: custo informado hoje
  // não volta para trás.
  if (custos) {
    const n = custos.filter((l) => l.custo_unitario === null).length;
    if (n > 0) {
      tarefas.push({
        chave: "custos",
        frase: `${n} ${plural(n, "produto", "produtos")} que você vendeu ${plural(n, "está", "estão")} sem custo informado`,
        apoio: "Sem ele, a sobra lá em cima aparece maior do que a real.",
        botao: links.base === "/demo" ? "Ver custos" : "Informar custos",
        href: link(`${links.base}/custos`, links.periodo),
      });
    }
  }

  const rejeitados = contagem?.get("visto-e-rejeitado") ?? 0;
  if (rejeitados > 0) {
    const n = rejeitados;
    tarefas.push({
      chave: "visto-e-rejeitado",
      frase: `${n} ${plural(n, "anúncio recebe", "anúncios recebem")} visitas, mas ${plural(n, "vende", "vendem")} pouco`,
      apoio: "Muita gente entra e não compra — vale revisar preço, foto, título ou frete.",
      botao: "Ver quais anúncios",
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
  // risco" passaria a significar "comprou há 25 dias". A frase diz a janela.
  if (rfm) {
    const emRisco = rfm.filter((c) => c.segmento === "At Risk");
    const n = emRisco.length;
    if (n > 0) {
      const total = emRisco.reduce((acc, c) => acc + c.monetary, 0);
      tarefas.push({
        chave: "clientes-em-risco",
        frase: `${n} ${plural(n, "cliente que comprava bem está sumindo", "clientes que compravam bem estão sumindo")}`,
        apoio: `Nos últimos 3 meses, ${plural(n, "gastou", "gastaram")} ${brl.format(total)} com você.`,
        botao: "Ver quais clientes",
        href: link(`${links.base}/clientes`, links.periodoClientes),
      });
    }
  }

  const poucoVistos = contagem?.get("converte-falta-ser-visto") ?? 0;
  if (poucoVistos > 0) {
    const n = poucoVistos;
    tarefas.push({
      chave: "converte-falta-ser-visto",
      frase: `${n} ${plural(n, "anúncio vende", "anúncios vendem")} bem quando ${plural(n, "é visto", "são vistos")}, mas pouca gente chega até ${plural(n, "ele", "eles")}`,
      apoio: `Vale dar mais visibilidade a ${plural(n, "ele", "eles")}.`,
      botao: "Ver quais anúncios",
      href: link(
        `${links.base}/produtos`,
        links.periodo,
        { diagnostico: "converte-falta-ser-visto" },
        "#desempenho-anuncios",
      ),
    });
  }

  return { tarefas, incompleto: custos === null || abc === null || rfm === null };
}

/** A mesma regra da seção Desempenho dos anúncios, para o número bater com o filtro de lá. */
function contaDiagnosticos(abc: readonly LinhaDeFunil[]): Map<Diagnostico, number> {
  const referencia = calculaReferencia(abc);
  const contagem = new Map<Diagnostico, number>();
  for (const linha of abc) {
    const d = diagnostica(linha, referencia);
    contagem.set(d, (contagem.get(d) ?? 0) + 1);
  }
  return contagem;
}

export function rodapeDasTarefas(resultado: { tarefas: Tarefa[]; incompleto: boolean }): string | null {
  if (resultado.incompleto) return RESUMO_INCOMPLETO;
  return resultado.tarefas.length === 0 ? NADA_PEDINDO_ATENCAO : null;
}

/** Valor de um `Promise.allSettled`, ou `null` se aquela busca falhou. */
export function valorOuNulo<T>(resultado: PromiseSettledResult<T>): T | null {
  return resultado.status === "fulfilled" ? resultado.value : null;
}
