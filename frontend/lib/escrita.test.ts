// frontend/lib/escrita.test.ts
import { describe, expect, it } from "vitest";

import {
  ATRASO_INICIAL,
  FRASE_DO_HEROI,
  PAUSA_NO_PONTO,
  SUBTITULO_DO_HEROI,
  caracteresDaFrase,
  fimDaDigitacao,
  temposDaDigitacao,
  textoDaFrase,
} from "./escrita";

describe("frase do herói", () => {
  it("é a frase aprovada, com 'respostas' em destaque", () => {
    expect(textoDaFrase(FRASE_DO_HEROI)).toBe(
      "Todo vendedor tem os números. Poucos têm as respostas.",
    );
    const destacados = caracteresDaFrase(FRASE_DO_HEROI)
      .filter((c) => c.destaque)
      .map((c) => c.letra)
      .join("");
    expect(destacados).toBe("respostas");
  });

  it("o subtítulo é o texto aprovado", () => {
    expect(SUBTITULO_DO_HEROI).toBe(
      "O Mercado Livre te mostra o que entrou. O SellerPulse mostra o que sobrou, qual produto puxa o faturamento, qual anúncio queima visita sem vender e qual cliente valia reconquistar — tudo calculado a partir dos seus pedidos reais.",
    );
  });
});

describe("tempos da digitação", () => {
  const letras = caracteresDaFrase(FRASE_DO_HEROI);
  const tempos = temposDaDigitacao(letras);

  it("um tempo por letra, sempre crescendo", () => {
    expect(tempos).toHaveLength(letras.length);
    for (let i = 1; i < tempos.length; i++) expect(tempos[i]).toBeGreaterThan(tempos[i - 1]);
  });

  it("começa depois do atraso inicial", () => {
    expect(tempos[0]).toBeGreaterThanOrEqual(ATRASO_INICIAL);
  });

  // O LCP só conta quando a H1 termina de aparecer: acima de ~2,3 s a nota do
  // Google piora. Abaixo de 1,6 s já não se lê como digitação.
  it("a frase termina perto de 2 segundos", () => {
    expect(fimDaDigitacao(tempos)).toBeGreaterThanOrEqual(1600);
    expect(fimDaDigitacao(tempos)).toBeLessThanOrEqual(2300);
  });

  it("para depois do primeiro ponto, como quem respira", () => {
    const ponto = letras.findIndex((c) => c.letra === ".");
    expect(tempos[ponto + 1] - tempos[ponto]).toBeGreaterThanOrEqual(PAUSA_NO_PONTO);
  });

  it("é igual a cada carregamento (sem Math.random)", () => {
    expect(temposDaDigitacao(letras)).toEqual(tempos);
  });
});
