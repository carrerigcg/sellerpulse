import { describe, expect, it } from "vitest";

import { codigoValido, faltaOCodigo } from "./duas-etapas";

describe("faltaOCodigo", () => {
  it("quem ativou o app e só digitou a senha precisa do código", () => {
    expect(faltaOCodigo({ currentLevel: "aal1", nextLevel: "aal2" })).toBe(true);
  });

  it("quem já digitou o código entra", () => {
    expect(faltaOCodigo({ currentLevel: "aal2", nextLevel: "aal2" })).toBe(false);
  });

  it("quem não ativou o app entra só com a senha", () => {
    expect(faltaOCodigo({ currentLevel: "aal1", nextLevel: "aal1" })).toBe(false);
  });

  it("sem resposta do Supabase, não inventa a exigência", () => {
    expect(faltaOCodigo(null)).toBe(false);
  });
});

describe("codigoValido", () => {
  it("aceita seis dígitos, com espaço no meio", () => {
    expect(codigoValido("123 456")).toBe("123456");
  });

  it("recusa menos de seis dígitos ou letras", () => {
    expect(codigoValido("12345")).toBeNull();
    expect(codigoValido("12a456")).toBeNull();
  });
});
