import { describe, expect, it } from "vitest";

import { dataDaAutorizacao, ENDERECO_DO_MCP, nomeDoCliente, podeConectarIa } from "./conexoes-ia";

describe("podeConectarIa", () => {
  it("só o plano com o recurso autoriza", () => {
    expect(podeConectarIa(["alertas", "mcp-conta"])).toBe(true);
    expect(podeConectarIa(["alertas", "clientes"])).toBe(false);
  });

  it("sem resposta do acesso, não autoriza", () => {
    // Na dúvida, a tela de consentimento não oferece o botão: o servidor
    // recusaria a chamada de qualquer jeito, e o vendedor ficaria sem saber.
    expect(podeConectarIa(null)).toBe(false);
  });
});

describe("nomeDoCliente", () => {
  it("cliente registrado sem nome não vira texto vazio", () => {
    expect(nomeDoCliente("Claude")).toBe("Claude");
    expect(nomeDoCliente("  ")).toBe("Aplicativo sem nome");
    expect(nomeDoCliente(null)).toBe("Aplicativo sem nome");
  });
});

describe("dataDaAutorizacao", () => {
  it("usa o dia do vendedor, não o UTC", () => {
    // 01h UTC do dia 17 ainda é dia 16 em Brasília.
    expect(dataDaAutorizacao("2026-11-17T01:00:00Z")).toBe("16/11/2026");
  });
});

it("o endereço do MCP é o do domínio próprio", () => {
  expect(ENDERECO_DO_MCP).toBe("https://api.usesellerpulse.com/mcp/conta");
});
