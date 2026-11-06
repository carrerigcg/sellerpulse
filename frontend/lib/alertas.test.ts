import { describe, expect, it } from "vitest";

import { estadoDaMargem, fraseDaMargem, fraseDoParado, linkDoAnuncio, type Alertas } from "./alertas";

const VAZIO: Alertas = { produtos_avaliados: 0, margem_negativa: [], parados: [], referencia: null };

describe("estadoDaMargem", () => {
  it("sem produto avaliado, pede o custo em vez de dizer que está tudo bem", () => {
    expect(estadoDaMargem(VAZIO)).toBe("sem-custo");
  });

  it("com produtos avaliados e nenhum negativo, diz que não há alerta", () => {
    expect(estadoDaMargem({ ...VAZIO, produtos_avaliados: 3 })).toBe("nenhum");
  });

  it("com produto negativo, mostra os alertas", () => {
    const alertas = {
      ...VAZIO,
      produtos_avaliados: 3,
      margem_negativa: [{ sku: "MLB1", titulo: "Fone", receita: 100, margem: -10 }],
    };
    expect(estadoDaMargem(alertas)).toBe("alertas");
  });
});

describe("frases", () => {
  it("o prejuízo sai positivo na frase, com a receita ao lado", () => {
    const frase = fraseDaMargem({ sku: "MLB1", titulo: "Fone", receita: 100, margem: -10 });
    expect(frase).toContain("Prejuízo de R$ 10,00");
    expect(frase).toContain("R$ 100,00");
  });

  it("o parado diz o ritmo normal do produto", () => {
    const base = { sku: "MLB1", titulo: "Fone", dias_sem_vender: 28, ultima_venda: "2026-09-22" };
    expect(fraseDoParado({ ...base, intervalo_normal: 8 })).toBe(
      "Sem vender há 28 dias; costuma vender a cada 8 dias.",
    );
    expect(fraseDoParado({ ...base, intervalo_normal: 1 })).toBe(
      "Sem vender há 28 dias; costuma vender todo dia.",
    );
  });
});

describe("linkDoAnuncio", () => {
  it("converte o id da API para o do endereço do anúncio", () => {
    expect(linkDoAnuncio("MLB999134972")).toBe("https://produto.mercadolivre.com.br/MLB-999134972");
  });

  it("não adivinha endereço para id em outro formato", () => {
    expect(linkDoAnuncio("ITEM_X")).toBeNull();
  });
});
