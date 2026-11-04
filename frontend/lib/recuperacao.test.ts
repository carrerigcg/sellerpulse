import { describe, expect, it } from "vitest";

import {
  linkDeRecuperacao,
  mensagemDaSenhaNova,
  mensagemDoEnvio,
  motivoDoLinkInvalido,
} from "./recuperacao";

describe("linkDeRecuperacao", () => {
  it("lê o código do modelo próprio do e-mail (token_hash)", () => {
    expect(linkDeRecuperacao("?token_hash=abc123&type=recovery")).toEqual({
      tipo: "token",
      valor: "abc123",
    });
  });

  it("recusa token_hash de outro tipo: confirmar cadastro não troca senha", () => {
    expect(linkDeRecuperacao("?token_hash=abc123&type=signup")).toBeNull();
  });

  it("lê o código do modelo padrão do Supabase (PKCE)", () => {
    expect(linkDeRecuperacao("?code=xyz789")).toEqual({ tipo: "codigo", valor: "xyz789" });
  });

  it("recusa a página aberta sem código", () => {
    expect(linkDeRecuperacao("")).toBeNull();
    expect(linkDeRecuperacao("?type=recovery")).toBeNull();
    expect(linkDeRecuperacao("?token_hash=&type=recovery")).toBeNull();
    expect(linkDeRecuperacao("?code=")).toBeNull();
  });
});

describe("mensagemDoEnvio", () => {
  it("sem erro, não diz se a conta existe", () => {
    const m = mensagemDoEnvio(null);
    expect(m.tom).toBe("ok");
    expect(m.texto).toMatch(/se houver uma conta/i);
  });

  it("remetente padrão sem permissão: não promete um e-mail que não vai chegar", () => {
    const m = mensagemDoEnvio({
      code: "email_address_not_authorized",
      message: "Email address not authorized",
    });
    expect(m.tom).toBe("erro");
    expect(m.texto).not.toMatch(/enviamos/i);
    expect(m.contato).toBe(true);
  });

  it("muitos pedidos seguidos pedem para esperar", () => {
    const m = mensagemDoEnvio({ code: "over_email_send_rate_limit", message: "x", status: 429 });
    expect(m.tom).toBe("erro");
    expect(m.texto).toMatch(/espere/i);
  });

  it("falha de rede não vira 'enviamos'", () => {
    const m = mensagemDoEnvio({ name: "AuthRetryableFetchError", message: "Failed to fetch" });
    expect(m.tom).toBe("erro");
    expect(m.texto).toMatch(/internet/i);
  });
});

describe("mensagemDaSenhaNova", () => {
  it("repetir a senha atual tem mensagem própria", () => {
    expect(mensagemDaSenhaNova({ code: "same_password", message: "x" })).toMatch(/atual/i);
  });

  it("senha fraca diz o mínimo", () => {
    expect(mensagemDaSenhaNova({ code: "weak_password", message: "x" })).toMatch(/6 caracteres/);
  });

  it("sessão sem o código do app pede um link novo: o link usado não vale de novo", () => {
    const m = mensagemDaSenhaNova({ code: "insufficient_aal", message: "x" });
    expect(m).toMatch(/código do app/i);
    expect(m).toMatch(/link novo/i);
  });
});

describe("motivoDoLinkInvalido", () => {
  it("link vencido ou gasto diz isso", () => {
    expect(motivoDoLinkInvalido({ code: "otp_expired", message: "x", status: 403 })).toMatch(
      /venceu ou já foi usado/,
    );
  });

  it("link do modelo padrão lembra que precisa ser o mesmo navegador", () => {
    expect(
      motivoDoLinkInvalido({ code: "flow_state_not_found", message: "x" }, "codigo"),
    ).toMatch(/mesmo navegador/);
  });

  it("queda de conexão não culpa o link, que continua valendo", () => {
    const m = motivoDoLinkInvalido({ name: "AuthRetryableFetchError", message: "Failed to fetch" });
    expect(m).not.toMatch(/venceu|usado/);
    expect(m).toMatch(/internet/i);
  });
});
