import { describe, expect, it } from "vitest";

import { comReceitaSemFrete, type FluxoDiaDaApi } from "./frete";

describe("comReceitaSemFrete", () => {
  const dia: FluxoDiaDaApi = {
    date: "2026-10-01",
    receita_bruta: 1000,
    taxas_ml: 120,
    frete: 0,
    custo_produtos: 300,
    receita_sem_custo: 0,
    margem_contribuicao: 580,
  };

  it("backend sem a coluna: toda a receita fica sem frete, nunca zero", () => {
    expect(comReceitaSemFrete([dia])[0].receita_sem_frete).toBe(1000);
  });

  it("backend com a coluna: o valor dele passa intacto", () => {
    const comColuna = { ...dia, frete: 35, receita_sem_frete: 200 };
    expect(comReceitaSemFrete([comColuna])[0]).toEqual(comColuna);
  });

  it("zero vindo do backend é zero, e não ausência", () => {
    expect(comReceitaSemFrete([{ ...dia, receita_sem_frete: 0 }])[0].receita_sem_frete).toBe(0);
  });
});
