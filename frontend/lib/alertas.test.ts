import { describe, expect, it } from "vitest";

import {
  estadoDaMargem,
  estadoDoPrejuizo,
  estadoDosParados,
  fraseDaReferencia,
  fraseSemAlertaDeMargem,
  fraseSemParados,
  linkDoAnuncio,
  partesDaMargem,
  partesDoParado,
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

  it("com poucos produtos medidos, diz quantos de quantos e não promete que está tudo bem", () => {
    expect(fraseSemAlertaDeMargem({ ...VAZIO, produtos_avaliados: 5, produtos_vendidos: 50 })).toBe(
      "Nenhum entre os 5 produtos com custo e frete conhecidos, de 50 vendidos nos últimos 30 dias. Com tão poucos medidos, ainda não dá para dizer que está tudo bem.",
    );
    expect(fraseSemAlertaDeMargem({ ...VAZIO, produtos_avaliados: 1, produtos_vendidos: 50 })).toBe(
      "Nenhum: só 1 produto, de 50 vendidos nos últimos 30 dias, tem custo e frete conhecidos. Com tão poucos medidos, ainda não dá para dizer que está tudo bem.",
    );
  });

  it("com a maior parte medida, mantém a frase de sempre", () => {
    expect(fraseSemAlertaDeMargem({ ...VAZIO, produtos_avaliados: 3, produtos_vendidos: 4 })).toBe(
      "Nenhum, entre os 3 produtos com custo e frete conhecidos em todas as vendas.",
    );
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

const nbsp = (s: string) => s.replace(/\u00a0/g, " ");

describe("partes de cada alerta", () => {
  it("o prejuízo sai sem sinal no destaque, com a receita no contexto", () => {
    const p = partesDaMargem({ sku: "MLB1", titulo: "Fone", receita: 100, margem: -10 });
    expect(nbsp(p.prejuizo)).toBe("R$ 10,00");
    expect(nbsp(p.contexto)).toBe("em R$ 100,00 vendidos nos últimos 30 dias, já tirando taxa, frete e custo.");
  });

  it("o parado destaca os dias e diz o ritmo normal", () => {
    const base = { sku: "MLB1", titulo: "Fone", dias_sem_vender: 28, ultima_venda: "2026-09-22" };
    expect(partesDoParado({ ...base, intervalo_normal: 8 })).toEqual({
      dias: "28 dias",
      contexto: "sem vender; costuma vender a cada 8 dias.",
    });
    expect(partesDoParado({ ...base, intervalo_normal: 1 }).contexto).toBe(
      "sem vender; costuma vender todo dia.",
    );
  });
});

describe("estado das caixas — não medido nunca é verde", () => {
  const prejuizo = { sku: "MLB1", titulo: "Fone", receita: 100, margem: -10 };
  const parado = { sku: "MLB2", titulo: "Capa", dias_sem_vender: 9, intervalo_normal: 2, ultima_venda: "2026-11-01" };

  it("prejuízo", () => {
    expect(estadoDoPrejuizo(VAZIO)).toBe("nao-medido");
    // Resposta de backend antigo, sem `produtos_vendidos`: vale o que já valia.
    expect(estadoDoPrejuizo({ ...VAZIO, produtos_avaliados: 3 })).toBe("tudo-certo");
    expect(estadoDoPrejuizo({ ...VAZIO, produtos_avaliados: 3, margem_negativa: [prejuizo] })).toBe("alerta");
  });

  it("prejuízo: verde só com a maior parte dos vendidos medida", () => {
    expect(estadoDoPrejuizo({ ...VAZIO, produtos_avaliados: 3, produtos_vendidos: 4 })).toBe("tudo-certo");
    expect(estadoDoPrejuizo({ ...VAZIO, produtos_avaliados: 5, produtos_vendidos: 50 })).toBe("nao-medido");
    // Exatamente a metade não é "a maior parte".
    expect(estadoDoPrejuizo({ ...VAZIO, produtos_avaliados: 2, produtos_vendidos: 4 })).toBe("nao-medido");
  });

  it("prejuízo real é alerta mesmo com pouca cobertura", () => {
    const alertas = { ...VAZIO, produtos_avaliados: 1, produtos_vendidos: 50, margem_negativa: [prejuizo] };
    expect(estadoDoPrejuizo(alertas)).toBe("alerta");
  });

  it("parados", () => {
    expect(estadoDosParados(VAZIO)).toBe("nao-medido"); // nunca sincronizou
    expect(estadoDosParados({ ...VAZIO, produtos_com_ritmo: 0 })).toBe("nao-medido");
    expect(estadoDosParados({ ...VAZIO, produtos_com_ritmo: 14 })).toBe("tudo-certo");
    expect(estadoDosParados({ ...VAZIO, produtos_com_ritmo: 14, parados: [parado] })).toBe("alerta");
  });
});

describe("fraseDaReferencia", () => {
  it("diz até que dia os dias parados foram contados", () => {
    expect(fraseDaReferencia({ ...VAZIO, referencia: "2026-11-08" })).toBe(
      "Dias contados até a última sincronização, em 08/11.",
    );
  });

  it("sem sincronização, não diz data nenhuma", () => {
    expect(fraseDaReferencia(VAZIO)).toBeNull();
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
