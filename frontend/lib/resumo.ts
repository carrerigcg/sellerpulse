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
