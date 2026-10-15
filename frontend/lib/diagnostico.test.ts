import { describe, expect, it } from "vitest";

import {
  MIN_PRODUTOS_PARA_REFERENCIA,
  VENDAS_ESPERADAS_MINIMAS,
  calculaReferencia,
  diagnostica,
  type LinhaDeFunil,
} from "./diagnostico";

/**
 * Por que esta lógica tem teste próprio:
 *
 * um quadrante trocado não derruba nada. Mostra um rótulo errado, com toda a
 * confiança, e o vendedor vai mexer no preço de um produto cujo problema era
 * tráfego — ou pior, vai encerrar um anúncio que estava convertendo bem.
 */

/** Gera uma loja com produtos previsíveis, para as medianas serem conhecidas. */
function loja(
  especificacoes: { visitas: number | null; unidades: number }[],
): LinhaDeFunil[] {
  return especificacoes.map(({ visitas, unidades }) => ({
    unidades,
    visitas,
    conversao: visitas && visitas > 0 ? (100 * unidades) / visitas : null,
  }));
}

/** Cinco produtos com 100 visitas e conversão 2,4,6,8,10% — mediana 6%. */
const BASE = loja([
  { visitas: 100, unidades: 2 },
  { visitas: 100, unidades: 4 },
  { visitas: 100, unidades: 6 },
  { visitas: 100, unidades: 8 },
  { visitas: 100, unidades: 10 },
]);

describe("calculaReferencia", () => {
  it("usa a mediana, não a média", () => {
    // Um item barato de alta recompra (26% no dado real) puxaria a média e
    // faria metade do catálogo parecer ruim.
    const comOutlier = [...BASE, ...loja([{ visitas: 100, unidades: 90 }])];
    const ref = calculaReferencia(comOutlier);
    expect(ref.medianaConversao).toBe(7); // 2,4,6,8,10,90 -> (6+8)/2
    expect(ref.medianaConversao).toBeLessThan(20);
  });

  it("calcula mediana com número par e ímpar de produtos", () => {
    expect(calculaReferencia(BASE).medianaConversao).toBe(6);
    expect(calculaReferencia(BASE.slice(0, 4)).medianaConversao).toBe(5); // 2,4,6,8
  });

  it("ignora produto sem visita ao montar a régua", () => {
    const comAusente = [...BASE, ...loja([{ visitas: null, unidades: 3 }])];
    expect(calculaReferencia(comAusente).medianaConversao).toBe(6);
  });

  it("a régua não é definida por produtos de amostra mínima", () => {
    // Cinco produtos sérios de 6%, mais cinco de 1 visita e 1 venda (100%).
    // Sem as duas passagens, a mediana viraria 53% e todo produto de verdade
    // apareceria "abaixo da média".
    const ruido = loja([
      { visitas: 1, unidades: 1 },
      { visitas: 1, unidades: 1 },
      { visitas: 1, unidades: 1 },
      { visitas: 1, unidades: 1 },
      { visitas: 1, unidades: 1 },
    ]);
    const ref = calculaReferencia([...BASE, ...ruido]);
    expect(ref.medianaConversao).toBe(6);
  });

  it("marca como não confiável quando há poucos produtos", () => {
    const ref = calculaReferencia(BASE.slice(0, MIN_PRODUTOS_PARA_REFERENCIA - 1));
    expect(ref.confiavel).toBe(false);
  });

  it("lista vazia não quebra", () => {
    const ref = calculaReferencia([]);
    expect(ref.confiavel).toBe(false);
    expect(ref.medianaConversao).toBe(0);
  });
});

describe("diagnostica", () => {
  const ref = calculaReferencia(BASE); // mediana: 6% de conversão, 100 visitas

  it("muita visita e conversão baixa é problema de anúncio", () => {
    const linha = loja([{ visitas: 200, unidades: 4 }])[0]; // 2%
    expect(diagnostica(linha, ref)).toBe("visto-e-rejeitado");
  });

  it("pouca visita e conversão alta é problema de tráfego", () => {
    // O quadrante mais valioso: o anúncio funciona, falta ser visto.
    const linha = loja([{ visitas: 50, unidades: 5 }])[0]; // 10%
    expect(diagnostica(linha, ref)).toBe("converte-falta-ser-visto");
  });

  it("muita visita e conversão alta é campeão", () => {
    const linha = loja([{ visitas: 200, unidades: 20 }])[0]; // 10%
    expect(diagnostica(linha, ref)).toBe("campeao");
  });

  it("pouca visita e conversão baixa é cauda", () => {
    const linha = loja([{ visitas: 50, unidades: 1 }])[0]; // 2%
    expect(diagnostica(linha, ref)).toBe("cauda");
  });

  it("empate na mediana conta como acima, nos dois eixos", () => {
    // Arbitrário de propósito; o que importa é ser consistente. Sem regra
    // fixa, o produto na mediana trocaria de quadrante conforme a comparação.
    const linha = loja([{ visitas: 100, unidades: 6 }])[0]; // exatamente 100 e 6%
    expect(diagnostica(linha, ref)).toBe("campeao");
  });

  // ---------- as três travas ----------

  it("número pequeno não vira diagnóstico", () => {
    // 8 visitas com mediana de 6%: o esperado eram 0,48 vendas. A conversão
    // de 12,5% é ruído, e sem esta trava o produto viraria "campeão".
    const linha = loja([{ visitas: 8, unidades: 1 }])[0];
    expect(diagnostica(linha, ref)).toBe("poucas-visitas");
  });

  it("ausência de medição é estado próprio, nunca cauda", () => {
    // "Não medimos" e "medimos e deu pouco" são coisas diferentes, e tratar
    // a primeira como a segunda é afirmar o que não se sabe.
    const linha: LinhaDeFunil = { unidades: 3, visitas: null, conversao: null };
    expect(diagnostica(linha, ref)).toBe("sem-visita");
  });

  it("colhido com zero visitas não é o mesmo que não colhido", () => {
    const linha: LinhaDeFunil = { unidades: 0, visitas: 0, conversao: null };
    expect(diagnostica(linha, ref)).toBe("poucas-visitas");
  });

  it("sem régua confiável, ninguém recebe rótulo de quadrante", () => {
    const poucos = calculaReferencia(BASE.slice(0, 2));
    const linha = loja([{ visitas: 500, unidades: 50 }])[0];
    expect(diagnostica(linha, poucos)).toBe("sem-referencia");
  });

  it("sem régua, ausência de visita ainda é ausência", () => {
    // A ordem das travas importa: "não medimos" vale mesmo sem referência.
    const poucos = calculaReferencia(BASE.slice(0, 2));
    const linha: LinhaDeFunil = { unidades: 1, visitas: null, conversao: null };
    expect(diagnostica(linha, poucos)).toBe("sem-visita");
  });
});

describe("a cauda precisa ser alcançável", () => {
  /**
   * O defeito que custou uma rodada: com o limiar em UMA venda esperada, o
   * produto na fronteira da amostra tem exatamente a conversão da mediana —
   * então nunca fica abaixo dela, e o quadrante "cauda" é inalcançável por
   * construção.
   *
   * Nesta população todo produto vendeu ao menos uma vez (a lista sai de
   * `order_items`), logo a conversão mínima possível é `1/visitas`. Medido na
   * loja real: com limiar 1, a cauda tinha 0 de 229 produtos; com 2, tem 9 de
   * 91. Nenhum dos outros testes distinguia os dois valores.
   */
  const ref = calculaReferencia(BASE); // mediana 6% de conversão, 100 visitas

  it("o produto no limiar tem faixa real para ficar abaixo da mediana", () => {
    // Medir a LARGURA da faixa, e não só o sinal: com limiar 1 o produto na
    // fronteira fica 0,12 ponto abaixo da mediana — tecnicamente abaixo,
    // praticamente em cima. Foi assim que a cauda zerou na loja real.
    const m = ref.medianaConversao;
    const minimoQuePassa = Math.ceil(VENDAS_ESPERADAS_MINIMAS / (m / 100));
    const menorConversaoPossivel = 100 / minimoQuePassa; // uma venda
    const faixa = m - menorConversaoPossivel;

    expect(faixa).toBeGreaterThan(m * 0.3);
  });

  it("existe produto que cai na cauda", () => {
    // 50 visitas (abaixo da mediana de 100), 1 venda -> 2% (abaixo de 6%).
    // Passa na trava: 50 × 6% = 3 vendas esperadas.
    const linha = loja([{ visitas: 50, unidades: 1 }])[0];
    expect(diagnostica(linha, ref)).toBe("cauda");
  });

  it("o limiar exige mais de uma venda esperada", () => {
    // Trava direta no valor: com 1, a fronteira iguala a mediana e a cauda
    // some. Qualquer volta para 1 quebra aqui.
    expect(VENDAS_ESPERADAS_MINIMAS).toBeGreaterThan(1);
  });
});
