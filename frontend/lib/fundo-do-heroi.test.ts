// frontend/lib/fundo-do-heroi.test.ts
import { describe, expect, it } from "vitest";

import { BARRAS, alturasDasBarras, progressoDaEntrada, projeta } from "./fundo-do-heroi";

describe("barras do fundo", () => {
  it("uma altura por barra, entre 0,1 e 1", () => {
    const alturas = alturasDasBarras();
    expect(alturas).toHaveLength(BARRAS);
    for (const a of alturas) {
      expect(a).toBeGreaterThanOrEqual(0.1);
      expect(a).toBeLessThanOrEqual(1);
    }
  });

  it("o mesmo desenho a cada carregamento", () => {
    expect(alturasDasBarras()).toEqual(alturasDasBarras());
  });
});

describe("entrada", () => {
  it("vai de 0 a 1 e para em 1", () => {
    expect(progressoDaEntrada(0)).toBe(0);
    expect(progressoDaEntrada(1100)).toBeGreaterThan(0);
    expect(progressoDaEntrada(1100)).toBeLessThan(1);
    expect(progressoDaEntrada(2200)).toBe(1);
    expect(progressoDaEntrada(60000)).toBe(1);
  });
});

describe("projeção", () => {
  it("o fundo do plano (z maior) sobe na tela", () => {
    const perto = projeta(0, 0, 0, 1000, 600);
    const longe = projeta(0, 0, 1, 1000, 600);
    expect(longe[1]).toBeLessThan(perto[1]);
  });

  it("altura maior fica mais alta na tela", () => {
    expect(projeta(0, 1, 0, 1000, 600)[1]).toBeLessThan(projeta(0, 0, 0, 1000, 600)[1]);
  });
});
