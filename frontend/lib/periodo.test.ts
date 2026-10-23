import { describe, expect, it } from "vitest";

import { hojeNoFusoDoVendedor, periodoDoResumo, periodoPadrao } from "./periodo";

/**
 * O teste que carrega peso aqui é o das 22h. As seis cópias antigas usavam
 * `toISOString()`, e às 22h em São Paulo a data UTC já é amanhã — a janela
 * padrão passava a incluir o dia corrente só à noite. Todos os instantes
 * abaixo estão em UTC de propósito, porque é o relógio do servidor (Vercel)
 * que roda estas páginas.
 */

describe("hojeNoFusoDoVendedor", () => {
  it("de manhã, o dia de São Paulo é o mesmo do UTC", () => {
    // 13:00 UTC = 10:00 em São Paulo.
    expect(hojeNoFusoDoVendedor(new Date("2026-10-22T13:00:00Z"))).toBe("2026-10-22");
  });

  it("às 22h em São Paulo, continua sendo hoje — não o amanhã do UTC", () => {
    // 01:00 UTC do dia 23 = 22:00 do dia 22 em São Paulo.
    // `toISOString().slice(0, 10)` devolveria "2026-10-23" aqui.
    expect(hojeNoFusoDoVendedor(new Date("2026-10-23T01:00:00Z"))).toBe("2026-10-22");
  });

  it("logo depois da meia-noite em São Paulo, já é o dia seguinte", () => {
    // 03:30 UTC = 00:30 em São Paulo.
    expect(hojeNoFusoDoVendedor(new Date("2026-10-23T03:30:00Z"))).toBe("2026-10-23");
  });
});

describe("periodoPadrao", () => {
  it("termina hoje no fuso do vendedor e começa 90 dias antes", () => {
    expect(periodoPadrao(new Date("2026-10-22T13:00:00Z"))).toEqual({
      de: "2026-07-24",
      ate: "2026-10-22",
    });
  });

  it("à noite, a janela é a mesma da manhã — o recorte não depende da hora", () => {
    const manha = periodoPadrao(new Date("2026-10-22T13:00:00Z"));
    const noite = periodoPadrao(new Date("2026-10-23T01:00:00Z"));
    expect(noite).toEqual(manha);
  });

  it("atravessa a virada do ano sem perder um dia", () => {
    // 15:00 UTC = 12:00 em São Paulo, 15/01/2026.
    expect(periodoPadrao(new Date("2026-01-15T15:00:00Z"))).toEqual({
      de: "2025-10-17",
      ate: "2026-01-15",
    });
  });
});

describe("periodoDoResumo", () => {
  it("30 dias terminando hoje, com a legenda incluindo as duas pontas", () => {
    // `ate` é exclusivo como no resto do projeto; a legenda diz o último dia
    // que entra de fato, porque o Resumo não tem seletor para explicar isso.
    expect(periodoDoResumo(new Date("2026-10-23T13:00:00Z"))).toEqual({
      de: "2026-09-23",
      ate: "2026-10-23",
      legenda: "de 23/09 a 22/10",
    });
  });

  it("atravessa a virada do ano", () => {
    expect(periodoDoResumo(new Date("2026-01-10T13:00:00Z"))).toEqual({
      de: "2025-12-11",
      ate: "2026-01-10",
      legenda: "de 11/12 a 09/01",
    });
  });

  it("às 22h em São Paulo, ainda é o dia de São Paulo", () => {
    // 01:00 UTC do dia 24 = 22:00 do dia 23 em São Paulo.
    expect(periodoDoResumo(new Date("2026-10-24T01:00:00Z")).ate).toBe("2026-10-23");
  });
});
