import { describe, expect, it } from "vitest";

import { destinoSeguro } from "./proximo";

const ORIGEM = "https://sellerpulse.app";

describe("destinoSeguro", () => {
  it("volta para o caminho do próprio site", () => {
    expect(destinoSeguro("/assinar?plano=premium", ORIGEM)).toBe("/assinar?plano=premium");
  });

  it("sem destino, vai para o painel", () => {
    expect(destinoSeguro(null, ORIGEM)).toBe("/dashboard");
  });

  it("não vira redirecionamento aberto para outro site", () => {
    expect(destinoSeguro("https://golpe.dev", ORIGEM)).toBe("/dashboard");
    expect(destinoSeguro("//golpe.dev", ORIGEM)).toBe("/dashboard");
    // O navegador trata "\" como "/": "/\golpe.dev" também sai do site.
    expect(destinoSeguro("/\\golpe.dev", ORIGEM)).toBe("/dashboard");
  });

  it("TAB e quebra de linha no meio não driblam a conferência", () => {
    // O navegador remove os dois de qualquer URL: "/\t/golpe.dev" vira "//golpe.dev".
    expect(destinoSeguro("/\t/golpe.dev", ORIGEM)).toBe("/dashboard");
    expect(destinoSeguro("/\n/golpe.dev", ORIGEM)).toBe("/dashboard");
  });
});
