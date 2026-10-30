import { afterEach, describe, expect, it, vi } from "vitest";

import { vitrineComVendasAbertas } from "./vendas";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("vitrineComVendasAbertas", () => {
  it("fica fechada com a variável ausente", () => {
    vi.stubEnv("VENDAS_ABERTAS", undefined as unknown as string);
    expect(vitrineComVendasAbertas()).toBe(false);
  });

  it.each(["", "0", "true"])("fica fechada com %j", (valor) => {
    vi.stubEnv("VENDAS_ABERTAS", valor);
    expect(vitrineComVendasAbertas()).toBe(false);
  });

  it("abre só com 1", () => {
    vi.stubEnv("VENDAS_ABERTAS", "1");
    expect(vitrineComVendasAbertas()).toBe(true);
  });
});
