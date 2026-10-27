import { describe, expect, it } from "vitest";

import { semFreteCalculado } from "./frete";

/**
 * O que carrega peso: a margem que sai daqui NÃO desconta frete. Na conta real
 * o frete chega sempre zerado (o campo que a ingestão lê nunca vem preenchido);
 * na demo ele é sintético e chega preenchido. Sem esta normalização, a demo
 * mostraria uma conta de frete que o produto real não faz.
 */
describe("semFreteCalculado", () => {
  const dia = {
    date: "2026-10-01",
    receita_bruta: 1_000,
    taxas_ml: 120,
    frete: 35,
    custo_produtos: 300,
    receita_sem_custo: 0,
    margem_contribuicao: 545, // o backend descontou o frete
  };

  it("o frete vira ausência, não zero", () => {
    expect(semFreteCalculado([dia])[0].frete).toBeNull();
  });

  it("a margem é recalculada sem o frete", () => {
    expect(semFreteCalculado([dia])[0].margem_contribuicao).toBe(580);
  });

  it("o resto do dia passa intacto", () => {
    const [d] = semFreteCalculado([dia]);
    expect(d).toMatchObject({
      date: "2026-10-01",
      receita_bruta: 1_000,
      taxas_ml: 120,
      custo_produtos: 300,
      receita_sem_custo: 0,
    });
  });
});
