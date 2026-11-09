import { describe, expect, it } from "vitest";

import {
  cabecalhoDaConta,
  apagaEscolhaAoRemover,
  avisoDaSoma,
  contasDoSeletor,
  ehVisaoSomada,
  opcoesDoSeletor,
  fraseDasContas,
  nomeDaConta,
  podeAdicionarConta,
  valorDoCookie,
  type Contas,
} from "./contas";

const EM_DIA = { sincronizada_em: "2026-11-09T12:00:00+00:00", importacao_completa: true };
const PRINCIPAL = { id: "a", apelido: "LOJA_A", principal: true, ativa: true, ...EM_DIA };
const EXTRA = { id: "b", apelido: "LOJA_B", principal: false, ativa: true, ...EM_DIA };

function acesso(parcial: Partial<Contas>): Contas {
  return { contas: [PRINCIPAL], conta_aberta: "a", max_contas: 3, ...parcial };
}

describe("avisoDaSoma", () => {
  const AGORA = new Date("2026-11-09T15:00:00Z");
  const SOMA = { conta_aberta: "todas" };

  it("com as contas em dia, não avisa nada", () => {
    expect(avisoDaSoma(acesso({ ...SOMA, contas: [PRINCIPAL, EXTRA] }), AGORA)).toBeNull();
  });

  it("fora da soma, não avisa: a conta aberta tem a própria tela de conexão", () => {
    const parada = { ...EXTRA, sincronizada_em: "2026-10-01T12:00:00+00:00" };
    expect(avisoDaSoma(acesso({ contas: [PRINCIPAL, parada] }), AGORA)).toBeNull();
  });

  it("conta parada há mais de 12 horas diz desde quando, no horário de Brasília", () => {
    const parada = { ...EXTRA, sincronizada_em: "2026-11-08T02:30:00+00:00" };
    const aviso = avisoDaSoma(acesso({ ...SOMA, contas: [PRINCIPAL, parada] }), AGORA);
    expect(aviso).toContain("LOJA_B não sincroniza desde 07/11");
    expect(aviso).toContain("aparecem como dias sem venda");
  });

  it("conta sem conexão e conta importando entram no aviso", () => {
    const sem = { ...EXTRA, apelido: null, sincronizada_em: null, importacao_completa: false };
    const nova = { ...EXTRA, id: "c", apelido: "LOJA_C", importacao_completa: false };
    const aviso = avisoDaSoma(acesso({ ...SOMA, contas: [PRINCIPAL, sem, nova] }), AGORA);
    expect(aviso).toContain("uma conta está sem conexão");
    expect(aviso).toContain("LOJA_C ainda está importando o histórico");
  });

  it("conta que não abre no plano não entra na soma, nem no aviso", () => {
    const guardada = { ...EXTRA, ativa: false, sincronizada_em: null };
    expect(avisoDaSoma(acesso({ ...SOMA, contas: [PRINCIPAL, guardada] }), AGORA)).toBeNull();
  });
});

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

describe("opcoesDoSeletor", () => {
  it("com uma conta só, não há seletor nem soma", () => {
    expect(opcoesDoSeletor(acesso({}))).toEqual([]);
  });

  it("com duas contas que abrem, a soma vem por último", () => {
    expect(opcoesDoSeletor(acesso({ contas: [PRINCIPAL, EXTRA] }))).toEqual([
      { valor: "a", rotulo: "LOJA_A (principal)", principal: true },
      { valor: "b", rotulo: "LOJA_B", principal: false },
      { valor: "todas", rotulo: "Todas as contas (soma)", principal: false },
    ]);
  });

  it("a extra que não abre no plano não entra, e sem ela não há o que somar", () => {
    const inativa = { ...EXTRA, ativa: false };
    expect(opcoesDoSeletor(acesso({ contas: [PRINCIPAL, inativa] }))).toEqual([]);
  });
});

describe("apagaEscolhaAoRemover", () => {
  it("apaga quando a removida era a aberta", () => {
    expect(apagaEscolhaAoRemover(acesso({ conta_aberta: "b" }), "b")).toBe(true);
    expect(apagaEscolhaAoRemover(acesso({ conta_aberta: "a" }), "b")).toBe(false);
  });

  it("apaga na soma: com uma conta a menos, pode não sobrar seletor para sair dela", () => {
    expect(apagaEscolhaAoRemover(acesso({ conta_aberta: "todas" }), "b")).toBe(true);
  });
});

describe("ehVisaoSomada", () => {
  it("só quando a conta aberta é a soma", () => {
    expect(ehVisaoSomada(acesso({ conta_aberta: "todas" }))).toBe(true);
    expect(ehVisaoSomada(acesso({ conta_aberta: "a" }))).toBe(false);
    expect(ehVisaoSomada(null)).toBe(false);
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
    // O Premium está fora da venda: mandar contratá-lo apontaria para nada.
    expect(frase).not.toMatch(/Premium/);
  });
});

describe("nomeDaConta", () => {
  it("marca a principal e não inventa apelido", () => {
    expect(nomeDaConta(PRINCIPAL)).toBe("LOJA_A (principal)");
    expect(nomeDaConta({ ...EXTRA, apelido: null })).toBe("Conta sem conexão");
  });
});
