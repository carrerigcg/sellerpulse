import { describe, expect, it } from "vitest";

import {
  arredondaSemMentir,
  calculaCobertura,
  coberturaDoFluxo,
  produtosSemCusto,
} from "./cobertura";

/**
 * Por que esta função tem teste:
 *
 * uma cobertura errada não derruba nada. Ela faz o vendedor olhar uma margem
 * incompleta sem aviso e concluir que lucra mais do que lucra — o mesmo erro
 * que o percentual de custo chutado produzia, só que mais difícil de ver.
 */

describe("arredondaSemMentir", () => {
  it("não deixa arredondamento comprar o silêncio dos 100%", () => {
    // 100% é o único valor que faz a tela parar de avisar que a margem está
    // incompleta. Um décimo de ponto não pode comprar esse silêncio.
    expect(arredondaSemMentir(0.996)).toBe(99);
    expect(arredondaSemMentir(0.9999)).toBe(99);
    expect(arredondaSemMentir(1)).toBe(100);
  });

  it("não deixa arredondamento apagar quem preencheu alguma coisa", () => {
    // 0% é o estado "nenhum custo informado". Quem preencheu um produto de
    // 400 tem que ver 1%, não 0%.
    expect(arredondaSemMentir(0.004)).toBe(1);
    expect(arredondaSemMentir(0.0001)).toBe(1);
    expect(arredondaSemMentir(0)).toBe(0);
  });

  it("arredonda normalmente no meio da escala", () => {
    expect(arredondaSemMentir(0.68)).toBe(68);
    expect(arredondaSemMentir(0.675)).toBe(68);
    expect(arredondaSemMentir(0.5)).toBe(50);
  });
});

describe("calculaCobertura", () => {
  it("mede a fatia coberta por custo informado", () => {
    const c = calculaCobertura(1000, 320);
    expect(c.pct).toBe(68);
    expect(c.vazia).toBe(false);
    expect(c.completa).toBe(false);
  });

  it("reconhece o estado vazio", () => {
    const c = calculaCobertura(1000, 1000);
    expect(c.pct).toBe(0);
    expect(c.vazia).toBe(true);
  });

  it("reconhece o estado completo", () => {
    const c = calculaCobertura(1000, 0);
    expect(c.pct).toBe(100);
    expect(c.completa).toBe(true);
  });

  it("período sem receita não é período descoberto", () => {
    // Zero vendas não é "margem incompleta" — não há o que cobrir, e a tela
    // não deve acusar falta de custo de um período sem venda nenhuma.
    const c = calculaCobertura(0, 0);
    expect(c.semReceita).toBe(true);
    expect(c.pct).toBe(0);
  });

  it("nunca passa de 100% nem desce de 0%", () => {
    // `receita_sem_custo` é medida na base de itens e `receitaTotal` no total
    // do pedido; as duas coincidem no dado, não por garantia do schema.
    expect(calculaCobertura(1000, -50).pct).toBe(100);
    expect(calculaCobertura(1000, 1500).pct).toBe(0);
  });

  it("trata número inválido como zero em vez de propagar NaN", () => {
    expect(calculaCobertura(NaN, 10).semReceita).toBe(true);
    expect(calculaCobertura(1000, NaN).pct).toBe(100);
  });
});

describe("coberturaDoFluxo", () => {
  it("soma os dias antes de dividir", () => {
    // Média das porcentagens diárias daria outro número: um dia de R$ 10 com
    // 0% pesaria igual a um dia de R$ 10.000 com 100%.
    const c = coberturaDoFluxo([
      { receita_bruta: 10, receita_sem_custo: 10 },
      { receita_bruta: 990, receita_sem_custo: 0 },
    ]);
    expect(c.pct).toBe(99);
  });

  it("lista vazia não quebra", () => {
    expect(coberturaDoFluxo([]).semReceita).toBe(true);
  });
});

describe("produtosSemCusto", () => {
  it("conta só quem não tem custo nenhum informado", () => {
    const produtos = [
      { receita: 100, receita_sem_custo: 100 }, // sem custo
      { receita: 100, receita_sem_custo: 0 }, // com custo
      { receita: 100, receita_sem_custo: 40 }, // parcial: tem custo em parte da janela
    ];
    expect(produtosSemCusto(produtos)).toBe(1);
  });

  it("produto sem receita no período não conta como pendência", () => {
    expect(produtosSemCusto([{ receita: 0, receita_sem_custo: 0 }])).toBe(0);
  });
});
