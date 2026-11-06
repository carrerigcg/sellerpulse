import { describe, expect, it } from "vitest";

import {
  estadoDaMargem,
  fraseDaMargem,
  fraseDoParado,
  fraseSemAlertaDeMargem,
  fraseSemParados,
  linkDoAnuncio,
  type Alertas,
} from "./alertas";

const VAZIO: Alertas = {
  produtos_avaliados: 0,
  margem_negativa: [],
  parados: [],
  produtos_com_ritmo: null,
  referencia: null,
};

describe("frases sem alerta", () => {
  it("sem produto avaliado, não diz que a margem está boa nem culpa só o custo", () => {
    const frase = fraseSemAlertaDeMargem(VAZIO);
    expect(frase).toMatch(/ainda não dá para medir/i);
    expect(frase).not.toMatch(/^nenhum/i);
  });

  it("diz entre quantos produtos não há prejuízo, com o plural certo", () => {
    expect(fraseSemAlertaDeMargem({ ...VAZIO, produtos_avaliados: 4 })).toBe(
      "Nenhum, entre os 4 produtos com custo e frete conhecidos em todas as vendas.",
    );
    expect(fraseSemAlertaDeMargem({ ...VAZIO, produtos_avaliados: 1 })).not.toMatch(/os 1/);
  });

  it("nenhum parado diz sobre quantos produtos vale", () => {
    expect(fraseSemParados({ ...VAZIO, produtos_com_ritmo: 7 })).toBe(
      "Nenhum dos 7 produtos que vendem com frequência parou.",
    );
    expect(fraseSemParados({ ...VAZIO, produtos_com_ritmo: 0 })).toMatch(/nenhum produto vende com frequência/i);
    expect(fraseSemParados(VAZIO)).toMatch(/primeira sincronização/);
  });
});

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
