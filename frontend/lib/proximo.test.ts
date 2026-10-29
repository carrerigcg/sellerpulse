import { describe, expect, it } from "vitest";

import { destinoSeguro } from "./proximo";

describe("destinoSeguro", () => {
  it("volta para o caminho do próprio site", () => {
    expect(destinoSeguro("/assinar?plano=premium")).toBe("/assinar?plano=premium");
  });

  it("sem destino, vai para o painel", () => {
    expect(destinoSeguro(null)).toBe("/dashboard");
  });

  it("não vira redirecionamento aberto para outro site", () => {
    expect(destinoSeguro("https://golpe.dev")).toBe("/dashboard");
    expect(destinoSeguro("//golpe.dev")).toBe("/dashboard");
    // O navegador trata "\" como "/": "/\golpe.dev" também sai do site.
    expect(destinoSeguro("/\\golpe.dev")).toBe("/dashboard");
  });
});
