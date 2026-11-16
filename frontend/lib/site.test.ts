import { describe, expect, it } from "vitest";

import robots from "../app/robots";
import sitemap from "../app/sitemap";
import { FORA_DA_BUSCA, PAGINAS_PUBLICAS } from "./site";

describe("site público", () => {
  it("o sitemap só lista o domínio próprio, nunca um endereço da Vercel", () => {
    for (const { url } of sitemap()) {
      expect(url).toMatch(/^https:\/\/usesellerpulse\.com(\/|$)/);
    }
  });

  it("nenhuma página do sitemap está bloqueada no robots", () => {
    for (const pagina of PAGINAS_PUBLICAS) {
      expect(FORA_DA_BUSCA.some((bloqueada) => pagina.startsWith(bloqueada))).toBe(false);
    }
  });

  it("o painel fica fora da busca", () => {
    const regra = robots().rules;
    const disallow = Array.isArray(regra) ? regra[0].disallow : regra.disallow;
    expect(disallow).toContain("/dashboard");
  });
});
