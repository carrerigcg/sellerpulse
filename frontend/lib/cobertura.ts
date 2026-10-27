/**
 * Quanto da receita de um período está coberta por custo informado.
 *
 * É a regra de honestidade da margem: nunca apresentar um número como
 * completo quando ele não é, e nunca esconder o número por estar incompleto.
 * Esconder faz a tela parecer quebrada para quem nunca preencheu nada;
 * mostrar sem a marca é o mesmo chute de 55% que foi removido em outubro, só
 * que mais sutil.
 *
 * Função pura, separada do componente, porque o modo de falha aqui é
 * silencioso: uma cobertura errada não derruba nada, só faz o vendedor
 * acreditar numa margem que não existe.
 */

export type Cobertura = {
  /** Fração coberta, de 0 a 1. */
  fracao: number;
  /** Porcentagem para exibir, inteira. Ver `arredondaSemMentir`. */
  pct: number;
  /** Não houve receita no período — não há o que cobrir. */
  semReceita: boolean;
  /** Nada informado: a margem não considera custo de produto nenhum. */
  vazia: boolean;
  /** Tudo informado: a margem está completa e não precisa de aviso. */
  completa: boolean;
};

/**
 * Arredonda para inteiro sem nunca afirmar 0% ou 100% por arredondamento.
 *
 * 99,6% arredondado normalmente vira 100 — e 100 é o único valor que faz a
 * tela parar de avisar que a margem está incompleta. Um décimo de ponto
 * percentual não pode comprar esse silêncio.
 *
 * O mesmo do outro lado: 0,4% viraria 0, e "0%" é o estado em que a tela diz
 * que nenhum custo foi informado. Quem preencheu um produto merece ver 1%.
 */
export function arredondaSemMentir(fracao: number): number {
  if (fracao >= 1) return 100;
  if (fracao <= 0) return 0;
  const bruto = Math.round(fracao * 100);
  if (bruto >= 100) return 99;
  if (bruto <= 0) return 1;
  return bruto;
}

export function calculaCobertura(receitaTotal: number, receitaSemCusto: number): Cobertura {
  const total = Number.isFinite(receitaTotal) ? receitaTotal : 0;
  const semCusto = Number.isFinite(receitaSemCusto) ? receitaSemCusto : 0;

  if (total <= 0) {
    return { fracao: 0, pct: 0, semReceita: true, vazia: true, completa: false };
  }

  // Limitado a [0, 1] de propósito. `receita_sem_custo` é medida na base de
  // ITENS (quantidade × preço) e `receitaTotal` vem do total do pedido; as
  // duas coincidem quando o total do pedido é a soma dos seus itens, o que é
  // propriedade do dado e não garantia do schema. Sem o limite, um desvio
  // minúsculo exibiria "101% coberto".
  const fracao = Math.min(1, Math.max(0, 1 - semCusto / total));

  return {
    fracao,
    pct: arredondaSemMentir(fracao),
    semReceita: false,
    vazia: fracao <= 0,
    completa: fracao >= 1,
  };
}

/** Soma de um campo numérico, tolerante a linha malformada. */
function soma<T>(linhas: readonly T[], campo: keyof T): number {
  return linhas.reduce((acc, linha) => {
    const valor = linha[campo];
    return acc + (typeof valor === "number" && Number.isFinite(valor) ? valor : 0);
  }, 0);
}

/** Cobertura do fluxo financeiro, a partir das linhas por dia. */
export function coberturaDoFluxo(
  dias: readonly { receita_bruta: number; receita_sem_custo: number }[],
): Cobertura {
  return calculaCobertura(soma(dias, "receita_bruta"), soma(dias, "receita_sem_custo"));
}

/**
 * Quanto da receita já tem o frete buscado no Mercado Livre.
 *
 * Mesma régua do custo de produto, outra origem: aqui a lacuna não depende
 * do vendedor — o frete é colhido por envio depois de cada sincronização, e
 * fica incompleto só enquanto a colheita não termina.
 */
export function coberturaDoFrete(totais: { receita: number; receitaSemFrete: number }): Cobertura {
  return calculaCobertura(totais.receita, totais.receitaSemFrete);
}

/** Cobertura da curva ABC, a partir das linhas por produto. */
export function coberturaDosProdutos(
  produtos: readonly { receita: number; receita_sem_custo: number }[],
): Cobertura {
  return calculaCobertura(soma(produtos, "receita"), soma(produtos, "receita_sem_custo"));
}

/**
 * Cobertura da tela de Custos, a partir do que está informado HOJE.
 *
 * Base diferente das duas acima de propósito. Lá a pergunta é histórica —
 * quanto da receita que já aconteceu tinha custo na data do pedido. Aqui é
 * "quanto do meu catálogo está preenchido agora", que é a pergunta de quem
 * está no meio do preenchimento e quer saber o que falta.
 */
export function coberturaInformada(
  linhas: readonly { receita: number; custo_unitario: number | null }[],
): Cobertura {
  const total = soma(linhas, "receita");
  const descoberta = linhas
    .filter((l) => l.custo_unitario === null)
    .reduce((acc, l) => acc + (Number.isFinite(l.receita) ? l.receita : 0), 0);
  return calculaCobertura(total, descoberta);
}

/** Quantos produtos ainda não têm custo informado. */
export function produtosSemCusto(
  produtos: readonly { receita: number; receita_sem_custo: number }[],
): number {
  // `receita_sem_custo === receita` é a assinatura de "nada informado para
  // este produto": toda a receita dele veio de venda sem custo.
  return produtos.filter((p) => p.receita > 0 && p.receita_sem_custo >= p.receita).length;
}
