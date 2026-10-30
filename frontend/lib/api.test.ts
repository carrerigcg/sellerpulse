import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase/server", () => ({ createClient: vi.fn() }));

import { ApiError, mensagemDeFalhaAoCarregar } from "./api";

describe("mensagemDeFalhaAoCarregar", () => {
  it("janela fora do plano diz o limite, e não culpa o backend", () => {
    const erro = new ApiError(403, "fora", "fora-do-plano");
    expect(mensagemDeFalhaAoCarregar(erro)).toContain("histórico do seu plano");
  });

  it("sessão expirada e pane continuam com as suas mensagens", () => {
    expect(mensagemDeFalhaAoCarregar(new ApiError(401, "x"))).toContain("sessão expirou");
    expect(mensagemDeFalhaAoCarregar(new Error("x"), "os produtos")).toContain("os produtos");
  });
});
