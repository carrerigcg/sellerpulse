import { describe, expect, it } from "vitest";

import {
  dataDaAutorizacao,
  destinoDoRetorno,
  ENDERECO_DO_MCP,
  nomeDoCliente,
  situacaoDoPlano,
} from "./conexoes-ia";

describe("situacaoDoPlano", () => {
  it("só o plano com o recurso autoriza", () => {
    expect(situacaoDoPlano(["alertas", "mcp-conta"])).toBe("liberado");
    expect(situacaoDoPlano(["alertas", "clientes"])).toBe("fora-do-plano");
    expect(situacaoDoPlano([])).toBe("fora-do-plano");
  });

  it("sem resposta do servidor não é o mesmo que fora do plano", () => {
    // Backend fora ou acordando: dizer "o seu plano não inclui" a um assinante
    // do Premium seria falso. Ausência não é negativa.
    expect(situacaoDoPlano(null)).toBe("sem-resposta");
  });
});

describe("destinoDoRetorno", () => {
  it("o Claude e o ChatGPT são reconhecidos", () => {
    expect(destinoDoRetorno("https://claude.ai/api/mcp/auth_callback")).toEqual({
      host: "claude.ai",
      conhecido: true,
    });
    expect(destinoDoRetorno("https://chatgpt.com/connector_platform_oauth_redirect").conhecido).toBe(
      true,
    );
  });

  it("um aplicativo neste computador é reconhecido", () => {
    expect(destinoDoRetorno("http://localhost:33418/callback")).toEqual({
      host: "localhost",
      conhecido: true,
    });
  });

  it("um nome parecido não engana", () => {
    // Quem registra o cliente escolhe o nome ("Claude") e o retorno. É o
    // retorno que diz para quem vai o acesso.
    expect(destinoDoRetorno("https://claude.ai.golpe.dev/cb")).toEqual({
      host: "claude.ai.golpe.dev",
      conhecido: false,
    });
    expect(destinoDoRetorno("https://naoclaude.ai/cb").conhecido).toBe(false);
  });

  it("retorno inválido não é reconhecido", () => {
    expect(destinoDoRetorno("nada")).toEqual({ host: null, conhecido: false });
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
