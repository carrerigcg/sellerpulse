import { describe, expect, it } from "vitest";

import { formatarPreco, precoAnual } from "./precos";

describe("preços", () => {
  it("o anual é 10 mensais, sem resto de ponto flutuante", () => {
    expect(precoAnual("essencial")).toBe(499.2);
    expect(precoAnual("exclusive")).toBe(799.7);
    expect(precoAnual("premium")).toBe(1399.5);
  });

  it("mostra os centavos, sem arredondar o preço quebrado", () => {
    // ` `: o Intl separa "R$" do número com espaço que não quebra.
    expect(formatarPreco(49.92)).toBe("R$ 49,92");
    expect(formatarPreco(1399.5)).toBe("R$ 1.399,50");
  });
});
