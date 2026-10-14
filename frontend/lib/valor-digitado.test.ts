import { describe, expect, it } from "vitest";

import { leValorDigitado } from "./valor-digitado";

/**
 * Por que o parser do campo de custo tem teste próprio:
 *
 * ele converte texto digitado em dinheiro que entra numa conta de margem. Ler
 * "48.50" como 4850 não derruba nada — grava um custo cem vezes maior, a
 * margem do mês fica negativa, e a tela mostra isso com toda a confiança.
 */

describe("leValorDigitado", () => {
  it("aceita vírgula decimal, que é o que se digita aqui", () => {
    expect(leValorDigitado("48,00")).toBe(48);
    expect(leValorDigitado("48,5")).toBe(48.5);
    expect(leValorDigitado("0,99")).toBe(0.99);
  });

  it("aceita ponto como milhar quando há vírgula decimal", () => {
    expect(leValorDigitado("1.234,56")).toBe(1234.56);
    expect(leValorDigitado("12.345,00")).toBe(12345);
  });

  it("lê ponto decimal de planilha em inglês sem multiplicar por cem", () => {
    // O erro que esta regra existe para impedir: "48.50" virando 4850.
    expect(leValorDigitado("48.50")).toBe(48.5);
    expect(leValorDigitado("48.5")).toBe(48.5);
    expect(leValorDigitado("0.99")).toBe(0.99);
  });

  it("lê ponto como milhar quando o grupo tem exatamente três dígitos", () => {
    expect(leValorDigitado("1.234")).toBe(1234);
    expect(leValorDigitado("12.345")).toBe(12345);
  });

  it("tolera R$ e espaços colados de outra planilha", () => {
    expect(leValorDigitado("R$ 48,00")).toBe(48);
    expect(leValorDigitado("  r$1.234,56  ")).toBe(1234.56);
  });

  it("campo vazio é não informado, nunca zero", () => {
    // A distinção é a feature inteira: zero afirma "não me custa nada".
    expect(leValorDigitado("")).toBeNull();
    expect(leValorDigitado("   ")).toBeNull();
  });

  it("zero digitado é zero, e é um valor", () => {
    expect(leValorDigitado("0")).toBe(0);
    expect(leValorDigitado("0,00")).toBe(0);
  });

  it("recusa o que não dá para interpretar, em vez de chutar", () => {
    expect(leValorDigitado("abc")).toBeUndefined();
    expect(leValorDigitado("-5")).toBeUndefined();
    expect(leValorDigitado("4,8,9")).toBeUndefined();
  });
});
