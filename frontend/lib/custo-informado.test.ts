import { describe, expect, it } from "vitest";

import { corpoDoCusto } from "./custo-informado";

/**
 * O que carrega peso: a opção "aplicar também às vendas anteriores sem custo"
 * chega à API. Se o campo sumisse do corpo, o backend gravaria "a partir de
 * hoje" (o padrão, para cliente antigo) e a tela diria uma coisa que o banco
 * não fez — sem nenhum erro.
 */
describe("corpoDoCusto", () => {
  it("com a opção ligada, pede o retroativo", () => {
    expect(corpoDoCusto(12.5, true)).toEqual({ custo_unitario: 12.5, retroativo: true });
  });

  it("com a opção desligada, pede só a partir de hoje", () => {
    expect(corpoDoCusto(12.5, false)).toEqual({ custo_unitario: 12.5, retroativo: false });
  });
});
