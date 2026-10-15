import { describe, expect, it } from "vitest";

import { incluiDiasNaoConsolidados, temVisitaColhida } from "./visitas";

/**
 * A pegadinha que estes testes existem para fixar: o "Até" do seletor é
 * EXCLUSIVO neste projeto. O último dia que o período contém é o anterior a
 * ele, e calcular sobre o limite em vez do último dia real faz o aviso
 * aparecer um dia fora — cedo demais ou tarde demais, sem nada falhar.
 */

const HOJE = new Date("2026-10-15T10:00:00Z");

describe("incluiDiasNaoConsolidados", () => {
  it("avisa quando o período alcança hoje", () => {
    // "Até 16/10" exclusivo contém o dia 15 — hoje.
    expect(incluiDiasNaoConsolidados("2026-10-16", HOJE)).toBe(true);
  });

  it("avisa quando o período termina em ontem", () => {
    // "Até 15/10" exclusivo contém até o dia 14.
    expect(incluiDiasNaoConsolidados("2026-10-15", HOJE)).toBe(true);
  });

  it("avisa quando o período termina em anteontem", () => {
    // Dia 13 ainda está na janela de 48h.
    expect(incluiDiasNaoConsolidados("2026-10-14", HOJE)).toBe(true);
  });

  it("não avisa quando o período fecha antes da janela de 48h", () => {
    // "Até 13/10" exclusivo contém até o dia 12, que já consolidou.
    expect(incluiDiasNaoConsolidados("2026-10-13", HOJE)).toBe(false);
  });

  it("não avisa para período antigo", () => {
    expect(incluiDiasNaoConsolidados("2026-09-01", HOJE)).toBe(false);
  });

  it("data inválida não vira aviso", () => {
    // Melhor não avisar do que avisar errado por causa de entrada quebrada.
    expect(incluiDiasNaoConsolidados("nao-e-data", HOJE)).toBe(false);
  });
});

describe("temVisitaColhida", () => {
  it("reconhece quando nenhuma visita foi colhida", () => {
    // Avisar sobre consolidação de dado que não existe é ruído, e ruído
    // ensina a ignorar avisos.
    expect(temVisitaColhida([{ visitas: null }, { visitas: null }])).toBe(false);
  });

  it("zero colhido conta como colhido", () => {
    // Zero é um fato medido; null é a ausência de medida.
    expect(temVisitaColhida([{ visitas: null }, { visitas: 0 }])).toBe(true);
  });

  it("lista vazia não tem visita", () => {
    expect(temVisitaColhida([])).toBe(false);
  });
});
