import { describe, expect, it } from "vitest";

import {
  TUTORIAIS,
  chaveDeArmazenamento,
  contextoDaRota,
  deveAbrirSozinho,
  slidesDoContexto,
  type ChaveDeTutorial,
  type Contexto,
} from "./tutoriais";

/**
 * O teste que carrega peso é o de `deveAbrirSozinho` com `temDados: false`.
 * Ele garante que o tutorial não cubra o atalho "Conectar uma conta do
 * Mercado Livre" de quem acabou de criar conta — a ação mais importante da
 * vida de um usuário novo no produto.
 */

const TELAS = Object.keys(TUTORIAIS) as ChaveDeTutorial[];
const CONTEXTOS: Contexto[] = ["demo", "dashboard"];

describe("conteúdo dos tutoriais", () => {
  it("cobre as cinco telas de análise", () => {
    expect([...TELAS].sort()).toEqual(["clientes", "custos", "executive", "exportar", "produtos"]);
  });

  it("toda tela tem de 1 a 3 slides, nos dois contextos", () => {
    for (const tela of TELAS) {
      for (const contexto of CONTEXTOS) {
        const n = slidesDoContexto(TUTORIAIS[tela], contexto).length;
        expect(n, `${tela}/${contexto}`).toBeGreaterThanOrEqual(1);
        expect(n, `${tela}/${contexto}`).toBeLessThanOrEqual(3);
      }
    }
  });

  it("nenhum título ou texto vazio, e nenhum texto que obrigue a rolar no celular", () => {
    for (const tela of TELAS) {
      for (const contexto of CONTEXTOS) {
        for (const slide of slidesDoContexto(TUTORIAIS[tela], contexto)) {
          expect(slide.titulo.trim(), `${tela}/${contexto}`).not.toBe("");
          expect(slide.texto.trim(), `${tela}/${contexto}`).not.toBe("");
          expect(slide.texto.length, `${tela}/${contexto}: ${slide.titulo}`).toBeLessThanOrEqual(260);
        }
      }
    }
  });

  it("toda versão é um inteiro positivo", () => {
    for (const tela of TELAS) {
      const { versao } = TUTORIAIS[tela];
      expect(Number.isInteger(versao) && versao > 0, tela).toBe(true);
    }
  });
});

describe("slidesDoContexto", () => {
  it("na demo, usa a variante quando ela existe", () => {
    const custos = TUTORIAIS.custos;
    expect(custos.slidesDaDemo).toBeDefined();
    expect(slidesDoContexto(custos, "demo")).toBe(custos.slidesDaDemo);
  });

  it("na demo, cai nos slides comuns quando não há variante", () => {
    const executive = TUTORIAIS.executive;
    expect(executive.slidesDaDemo).toBeUndefined();
    expect(slidesDoContexto(executive, "demo")).toBe(executive.slides);
  });

  it("no dashboard, ignora a variante da demo", () => {
    expect(slidesDoContexto(TUTORIAIS.custos, "dashboard")).toBe(TUTORIAIS.custos.slides);
  });
});

describe("chaveDeArmazenamento", () => {
  it("leva contexto, tela e versão", () => {
    expect(chaveDeArmazenamento("demo", "custos", 2)).toBe("sellerpulse:tutorial:demo:custos:v2");
  });

  it("demo e dashboard não compartilham o 'já vi'", () => {
    expect(chaveDeArmazenamento("demo", "produtos", 1)).not.toBe(
      chaveDeArmazenamento("dashboard", "produtos", 1),
    );
  });
});

describe("deveAbrirSozinho", () => {
  const base = { jaVisto: false, temDados: true, armazenamentoDisponivel: true };

  it("abre na primeira visita a uma tela com dado", () => {
    expect(deveAbrirSozinho(base)).toBe(true);
  });

  it("não abre sobre tela vazia ou com erro", () => {
    expect(deveAbrirSozinho({ ...base, temDados: false })).toBe(false);
  });

  it("não abre de novo depois de visto", () => {
    expect(deveAbrirSozinho({ ...base, jaVisto: true })).toBe(false);
  });

  it("não abre sem armazenamento — senão abriria em toda visita", () => {
    expect(deveAbrirSozinho({ ...base, armazenamentoDisponivel: false })).toBe(false);
  });
});

describe("contextoDaRota", () => {
  it("a demo e as subrotas dela são demo", () => {
    expect(contextoDaRota("/demo")).toBe("demo");
    expect(contextoDaRota("/demo/produtos")).toBe("demo");
  });

  it("o dashboard é dashboard", () => {
    expect(contextoDaRota("/dashboard")).toBe("dashboard");
    expect(contextoDaRota("/dashboard/custos")).toBe("dashboard");
  });

  it("não confunde um prefixo parecido com a demo", () => {
    expect(contextoDaRota("/demonstracao")).toBe("dashboard");
  });
});
