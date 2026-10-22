import { describe, expect, it } from "vitest";

import { formatarVariacao } from "./variacao";

/**
 * O teste que carrega peso é o da vírgula. O cartão usava `toFixed(1)`, que
 * ignora o locale e escrevia "+1.1%" na mesma tela em que o resto do produto
 * escreve "94,2%" — e em pt-BR o ponto é separador de milhar.
 */

describe("formatarVariacao", () => {
  it("usa vírgula decimal, não ponto", () => {
    expect(formatarVariacao(1.1)).toBe("+1,1%");
  });

  it("mantém o + em alta e o - em queda", () => {
    expect(formatarVariacao(12.34)).toBe("+12,3%");
    expect(formatarVariacao(-54.7)).toBe("-54,7%");
  });

  it("sempre uma casa decimal, como o toFixed(1) que substitui", () => {
    expect(formatarVariacao(5)).toBe("+5,0%");
  });

  it("separa milhar com ponto", () => {
    expect(formatarVariacao(1234.5)).toBe("+1.234,5%");
  });

  it("o que arredonda para zero sai sem sinal", () => {
    expect(formatarVariacao(0)).toBe("0,0%");
    expect(formatarVariacao(0.04)).toBe("0,0%");
    expect(formatarVariacao(-0.04)).toBe("0,0%");
  });
});
