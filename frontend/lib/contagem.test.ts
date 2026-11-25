import { describe, expect, it } from "vitest";

import { DURACAO_DA_CONTAGEM, valorNaContagem } from "./contagem";

describe("valorNaContagem", () => {
  it("começa em zero", () => {
    expect(valorNaContagem(30836, 0)).toBe(0);
  });

  it("termina no valor exato, e não perto dele", () => {
    expect(valorNaContagem(30836, DURACAO_DA_CONTAGEM)).toBe(30836);
    expect(valorNaContagem(30836, DURACAO_DA_CONTAGEM + 500)).toBe(30836);
  });

  it("sobe sem passar do valor e desacelera no fim", () => {
    const meio = valorNaContagem(1000, DURACAO_DA_CONTAGEM / 2);
    expect(meio).toBeGreaterThan(500);
    expect(meio).toBeLessThan(1000);
    const quase = valorNaContagem(1000, DURACAO_DA_CONTAGEM - 1);
    expect(quase).toBeLessThanOrEqual(1000);
  });

  it("valor negativo desce de zero até ele", () => {
    const meio = valorNaContagem(-500, DURACAO_DA_CONTAGEM / 2);
    expect(meio).toBeLessThan(0);
    expect(meio).toBeGreaterThan(-500);
    expect(valorNaContagem(-500, DURACAO_DA_CONTAGEM)).toBe(-500);
  });

  it("tempo inválido mostra o valor, nunca um número inventado", () => {
    expect(valorNaContagem(42, Number.NaN)).toBe(42);
  });
});
