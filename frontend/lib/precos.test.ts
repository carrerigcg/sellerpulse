import { describe, expect, it } from "vitest";

import { descontoDeLancamento, economiaMensal, formatarPreco, precoAnual } from "./precos";

describe("preços", () => {
  it("o anual é 10 mensais, sem resto de ponto flutuante", () => {
    expect(precoAnual("essencial")).toBe(499);
    expect(precoAnual("exclusive")).toBe(799);
    expect(precoAnual("premium")).toBe(1399);
  });

  it("mostra os centavos, sem arredondar o preço quebrado", () => {
    // ` `: o Intl separa "R$" do número com espaço que não quebra.
    expect(formatarPreco(49.92)).toBe("R$ 49,92");
    expect(formatarPreco(1399.5)).toBe("R$ 1.399,50");
  });
});

describe("promoção de lançamento", () => {
  it("o desconto sai do preço de depois e do de agora", () => {
    expect(descontoDeLancamento("essencial")).toBe(17);
    expect(descontoDeLancamento("exclusive")).toBe(27);
    expect(descontoDeLancamento("premium")).toBe(18);
  });

  it("a economia por mês fecha nos centavos", () => {
    expect(economiaMensal("essencial")).toBe(10);
    expect(economiaMensal("exclusive")).toBe(30);
    expect(economiaMensal("premium")).toBe(30);
  });
});
