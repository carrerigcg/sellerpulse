import { describe, expect, it } from "vitest";

import { fraseDosCancelamentos } from "./cancelamentos";

/** O Intl usa espaço não separável em "R$ 1.000"; os textos esperados, não. */
const t = (s: string | null) => (s === null ? null : s.replace(/ /g, " "));

/**
 * O que carrega peso: com esta frase, a conta contra o "vendas brutas" do
 * Mercado Livre fecha na própria tela. Na conta real, 01/09 a 28/09:
 * R$ 22.919 pagos + R$ 5.004 cancelados ou devolvidos (+ o dia 28, do "Até"
 * exclusivo) = os R$ 28.674 do painel do ML.
 */
describe("fraseDosCancelamentos", () => {
  it("diz quanto ficou fora e por quê, com o valor arredondado como os cartões", () => {
    expect(t(fraseDosCancelamentos({ pedidos: 32, valor: 5004 }))).toBe(
      "Fora da receita: R$ 5.004 em 32 pedidos cancelados ou devolvidos no período. O “vendas brutas” do Mercado Livre soma esse valor à receita.",
    );
  });

  it("singular com um pedido", () => {
    expect(t(fraseDosCancelamentos({ pedidos: 1, valor: 79 }))).toContain(
      "R$ 79 em 1 pedido cancelado ou devolvido",
    );
  });

  it("sem cancelamento no período não há o que explicar: some", () => {
    expect(fraseDosCancelamentos({ pedidos: 0, valor: 0 })).toBeNull();
  });

  it("sem o dado (busca falhou) também some, sem quebrar a tela", () => {
    expect(fraseDosCancelamentos(null)).toBeNull();
  });
});
