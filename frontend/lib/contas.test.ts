import { describe, expect, it } from "vitest";

import {
  cabecalhoDaConta,
  contasDoSeletor,
  fraseDasContas,
  nomeDaConta,
  podeAdicionarConta,
  valorDoCookie,
  type Contas,
} from "./contas";

const PRINCIPAL = { id: "a", apelido: "LOJA_A", principal: true, ativa: true };
const EXTRA = { id: "b", apelido: "LOJA_B", principal: false, ativa: true };

function acesso(parcial: Partial<Contas>): Contas {
  return { contas: [PRINCIPAL], conta_aberta: "a", max_contas: 3, ...parcial };
}

describe("cabecalhoDaConta", () => {
  it("sem escolha, não manda cabeçalho: o backend abre a principal", () => {
    expect(cabecalhoDaConta(undefined)).toEqual({});
    expect(cabecalhoDaConta("")).toEqual({});
  });

  it("com escolha, manda o id no X-Conta", () => {
    expect(cabecalhoDaConta("b")).toEqual({ "X-Conta": "b" });
  });
});

describe("valorDoCookie", () => {
  it("acha o cookie entre outros", () => {
    expect(valorDoCookie("x=1; sp_conta=abc-123; y=2", "sp_conta")).toBe("abc-123");
    expect(valorDoCookie("x=1", "sp_conta")).toBeUndefined();
  });

  it("não confunde um nome que só contém o outro", () => {
    expect(valorDoCookie("sp_conta_velha=zzz", "sp_conta")).toBeUndefined();
  });
});

describe("contasDoSeletor", () => {
  it("com uma conta só, não há seletor", () => {
    expect(contasDoSeletor(acesso({}))).toEqual([]);
  });

  it("mostra só as contas que abrem", () => {
    expect(contasDoSeletor(acesso({ contas: [PRINCIPAL, EXTRA] }))).toEqual([PRINCIPAL, EXTRA]);
    const inativa = { ...EXTRA, ativa: false };
    expect(contasDoSeletor(acesso({ contas: [PRINCIPAL, inativa] }))).toEqual([]);
  });
});

describe("podeAdicionarConta", () => {
  it("só com vaga num plano de várias contas", () => {
    expect(podeAdicionarConta(acesso({}))).toBe(true);
    expect(podeAdicionarConta(acesso({ max_contas: 1 }))).toBe(false);
    const tres = [PRINCIPAL, EXTRA, { ...EXTRA, id: "c" }];
    expect(podeAdicionarConta(acesso({ contas: tres }))).toBe(false);
  });
});

describe("fraseDasContas", () => {
  it("diz a vaga do plano", () => {
    expect(fraseDasContas(acesso({ contas: [PRINCIPAL, EXTRA] }))).toMatch(/^2 de 3 contas/);
  });

  it("só manda trocar no topo quando há seletor", () => {
    expect(fraseDasContas(acesso({ contas: [PRINCIPAL, EXTRA] }))).toMatch(/topo do painel/);
    expect(fraseDasContas(acesso({}))).toBe("1 de 3 contas no seu plano.");
  });

  it("fora do Premium, diz que as extras ficam guardadas, e não '2 de 1'", () => {
    const frase = fraseDasContas(acesso({ contas: [PRINCIPAL, EXTRA], max_contas: 1 }));
    expect(frase).toMatch(/ficam guardadas/);
    expect(frase).not.toMatch(/2 de 1/);
  });
});

describe("nomeDaConta", () => {
  it("marca a principal e não inventa apelido", () => {
    expect(nomeDaConta(PRINCIPAL)).toBe("LOJA_A (principal)");
    expect(nomeDaConta({ ...EXTRA, apelido: null })).toBe("Conta sem conexão");
  });
});
