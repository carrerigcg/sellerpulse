import { describe, expect, it } from "vitest";

import { SEGMENTOS } from "../components/analytics/segmentos";
import { parametroDoSegmento, segmentoDaUrl } from "./segmento-da-url";

describe("segmentoDaUrl", () => {
  it("aceita cada segmento pelo parâmetro em português", () => {
    expect(segmentoDaUrl("em-risco")).toBe("At Risk");
    for (const def of SEGMENTOS) {
      expect(segmentoDaUrl(def.parametro)).toBe(def.chave);
    }
  });

  it("ignora o resto — a URL é digitável", () => {
    expect(segmentoDaUrl("qualquer-coisa")).toBeNull();
    expect(segmentoDaUrl(undefined)).toBeNull();
    expect(segmentoDaUrl(["em-risco"])).toBeNull();
    // A chave do backend e o rótulo da tela não são o parâmetro: um só
    // formato, para o link do Resumo e o filtro nunca discordarem.
    expect(segmentoDaUrl("At Risk")).toBeNull();
    expect(segmentoDaUrl("Em risco")).toBeNull();
  });
});

describe("parametroDoSegmento", () => {
  it("faz o caminho de volta para todos os segmentos", () => {
    for (const def of SEGMENTOS) {
      expect(segmentoDaUrl(parametroDoSegmento(def.chave))).toBe(def.chave);
    }
  });

  it("os parâmetros são únicos e não precisam de escape na URL", () => {
    // Com espaço, "At Risk" viraria "At+Risk" ou "At%20Risk" conforme quem
    // monta o link — e um dos dois lados deixaria de reconhecer o outro.
    const parametros = SEGMENTOS.map((s) => s.parametro);
    expect(new Set(parametros).size).toBe(SEGMENTOS.length);
    for (const p of parametros) expect(p).toMatch(/^[a-z]+(-[a-z]+)*$/);
  });
});
