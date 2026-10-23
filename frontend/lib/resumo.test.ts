import { describe, expect, it } from "vitest";

import { calculaCobertura } from "./cobertura";
import { EXPLICACAO_DA_SOBRA, montaVeredito, type Totais } from "./resumo";

/**
 * O que carrega peso aqui é a proteção da cobertura. Quem preenche custos
 * hoje passa a ver as vendas novas descontando o produto, e a sobra "cai" —
 * sem a proteção, a frase culparia o custo e o vendedor concluiria que a loja
 * piorou, quando o que mudou foi a conta ficar honesta.
 */

/** O Intl usa espaço não separável em "R$ 1.000"; os textos esperados, não. */
const t = (s: string | null) => (s === null ? null : s.replace(/ /g, " "));

/** Totais coerentes: a margem é sempre a conta das outras três. */
function totais(receita: number, custo: number, custoProdutos: number): Totais {
  return { receita, custo, custoProdutos, margem: receita - custo - custoProdutos };
}

const COMPLETA = calculaCobertura(100, 0);

describe("montaVeredito — a sobra", () => {
  it("sobra positiva que caiu, com o que mais pesou", () => {
    const v = montaVeredito({
      atual: totais(118_000, 20_000, 45_700),
      anterior: totais(128_000, 21_000, 51_400),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.sobra)).toBe("Sobraram R$ 52.300 das suas vendas.");
    expect(t(v.comparacao)).toBe("R$ 3.300 a menos que nos 30 dias anteriores.");
    expect(v.direcao).toBe("menos");
    expect(t(v.maiorPeso)).toBe(
      "O que mais pesou: as vendas caíram R$ 10.000 — de R$ 128.000 para R$ 118.000.",
    );
    expect(v.explicacao).toBe(EXPLICACAO_DA_SOBRA);
  });

  it("sobra que subiu", () => {
    const v = montaVeredito({
      atual: totais(128_000, 21_000, 51_400),
      anterior: totais(118_000, 20_000, 45_700),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.comparacao)).toBe("R$ 3.300 a mais que nos 30 dias anteriores.");
    expect(v.direcao).toBe("mais");
  });

  it("sobra negativa vira falta, nunca 'sobraram -R$'", () => {
    const v = montaVeredito({
      atual: totais(10_000, 3_000, 9_000),
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(t(v.sobra)).toBe("As vendas não cobriram os custos: faltaram R$ 2.000.");
  });

  it("'o mesmo' quando os números da tela, já arredondados, são iguais", () => {
    const atual = { receita: 5_000, custo: 1_000, custoProdutos: 2_999.6, margem: 1_000.4 };
    const anterior = { receita: 5_000, custo: 1_000, custoProdutos: 3_000.4, margem: 999.6 };
    const v = montaVeredito({ atual, anterior, coberturaAtual: COMPLETA, coberturaAnterior: COMPLETA });
    expect(v.comparacao).toBe("O mesmo que nos 30 dias anteriores.");
    expect(v.direcao).toBe("igual");
    expect(v.maiorPeso).toBeNull();
  });

  it("sem vendas no período anterior, não compara", () => {
    const v = montaVeredito({
      atual: totais(10_000, 2_000, 3_000),
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(v.comparacao).toBe("Não houve vendas nos 30 dias anteriores para comparar.");
    expect(v.direcao).toBe("sem-comparacao");
    expect(v.maiorPeso).toBeNull();
  });
});

describe("montaVeredito — o que mais pesou", () => {
  it("só conta quem empurrou para o mesmo lado da mudança", () => {
    // A sobra caiu R$ 3.000. As vendas SUBIRAM R$ 5.000 — não pesaram para a
    // queda; o custo dos produtos subiu R$ 8.000 e é quem explica.
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe("O que mais pesou: o custo dos produtos subiu R$ 8.000.");
  });

  it("Mercado Livre e frete", () => {
    const v = montaVeredito({
      atual: totais(100_000, 30_000, 30_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe(
      "O que mais pesou: o que o Mercado Livre e o frete levaram subiu R$ 10.000.",
    );
  });

  it("proteção: com cobertura diferente entre os meses, não culpa o custo", () => {
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: calculaCobertura(105_000, 6_300), // 94%
      coberturaAnterior: calculaCobertura(100_000, 40_000), // 60%
    });
    expect(v.maiorPeso).toBe(
      "A comparação mistura meses diferentes: neste, 94% das vendas têm custo informado; no anterior, 60%.",
    );
  });
});

describe("montaVeredito — aviso de cobertura", () => {
  const base = { atual: totais(100, 10, 10), anterior: null, coberturaAnterior: null };

  it("parcial", () => {
    const v = montaVeredito({ ...base, coberturaAtual: calculaCobertura(100, 6) });
    expect(v.avisoCobertura).toBe(
      "6% das vendas deste mês estão sem custo informado — a sobra real é menor.",
    );
  });

  it("nenhum custo informado", () => {
    const v = montaVeredito({ ...base, coberturaAtual: calculaCobertura(100, 100) });
    expect(v.avisoCobertura).toBe(
      "Nenhuma venda deste mês tem custo informado — a sobra acima não desconta o custo dos produtos.",
    );
  });

  it("completa: sem aviso", () => {
    expect(montaVeredito({ ...base, coberturaAtual: COMPLETA }).avisoCobertura).toBeNull();
  });
});
