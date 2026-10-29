import { describe, expect, it } from "vitest";

import {
  comparaComAnterior,
  destinoSemAcesso,
  historicoCortado,
  inicioDoHistorico,
  libera,
  type Acesso,
} from "./plano";

const ESSENCIAL: Acesso = {
  plano: "essencial",
  recursos: [],
  dias_de_historico: 90,
  produtos_na_abc: 10,
  termos: { versao: "v1", aceito: true },
};

const EXCLUSIVE: Acesso = {
  ...ESSENCIAL,
  plano: "exclusive",
  recursos: ["abc-completa", "clientes", "cohort", "desempenho-anuncios", "exportar", "sync-sob-demanda"],
  dias_de_historico: null,
  produtos_na_abc: null,
};

describe("destinoSemAcesso", () => {
  it("sem plano vai para os planos, mesmo sem aceite", () => {
    expect(
      destinoSemAcesso({ ...ESSENCIAL, plano: null, termos: { versao: "v1", aceito: false } }),
    ).toBe("/planos");
  });

  it("com plano e sem aceite vai para o aceite", () => {
    expect(destinoSemAcesso({ ...ESSENCIAL, termos: { versao: "v1", aceito: false } })).toBe(
      "/aceite",
    );
  });

  it("com plano e aceite entra no painel", () => {
    expect(destinoSemAcesso(ESSENCIAL)).toBeNull();
  });
});

describe("histórico do plano", () => {
  it("começa 90 dias antes de hoje no Essencial, como no backend", () => {
    // 28/10 menos 90 dias = 30/07 (o mesmo par do teste do backend).
    expect(inicioDoHistorico(ESSENCIAL, "2026-10-28")).toBe("2026-07-30");
  });

  it("a janela padrão de 90 dias não conta como corte", () => {
    expect(historicoCortado(ESSENCIAL, "2026-07-30", "2026-10-28")).toBe(false);
  });

  it("um dia antes do início já é corte", () => {
    expect(historicoCortado(ESSENCIAL, "2026-07-29", "2026-10-28")).toBe(true);
  });

  it("plano sem limite nunca corta", () => {
    expect(inicioDoHistorico(EXCLUSIVE, "2026-10-28")).toBeNull();
    expect(historicoCortado(EXCLUSIVE, "2020-01-01", "2026-10-28")).toBe(false);
  });
});

describe("libera", () => {
  it("o Essencial não libera clientes; o Exclusive libera", () => {
    expect(libera(ESSENCIAL, "clientes")).toBe(false);
    expect(libera(EXCLUSIVE, "clientes")).toBe(true);
  });
});

describe("comparaComAnterior", () => {
  it("não compara quando o anterior começa antes do histórico, mesmo em parte", () => {
    // Período de 58 dias até 29/10: o anterior começaria em 03/07, antes de 31/07.
    expect(comparaComAnterior(ESSENCIAL, "2026-07-03", "2026-10-29")).toBe(false);
  });

  it("compara quando o anterior cabe inteiro", () => {
    // Resumo: 30 dias, anterior a partir de 29/08.
    expect(comparaComAnterior(ESSENCIAL, "2026-08-29", "2026-10-29")).toBe(true);
  });

  it("sem resposta do acesso, compara como antes", () => {
    expect(comparaComAnterior(null, "2020-01-01", "2026-10-29")).toBe(true);
  });
});
