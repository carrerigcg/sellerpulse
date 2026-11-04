import { describe, expect, it } from "vitest";

import { formataTelefone, metadadosDeContato, normalizaTelefone } from "./telefone";

describe("normalizaTelefone", () => {
  it("aceita celular com máscara", () => {
    expect(normalizaTelefone("(11) 98765-4321")).toBe("11987654321");
  });

  it("aceita fixo", () => {
    expect(normalizaTelefone("11 3456 7890")).toBe("1134567890");
  });

  it("tira o 55 de quem cola com o código do país", () => {
    expect(normalizaTelefone("+55 11 98765-4321")).toBe("11987654321");
  });

  it("recusa número sem DDD", () => {
    expect(normalizaTelefone("98765-4321")).toBeNull();
  });

  it("recusa DDD começando com 0", () => {
    expect(normalizaTelefone("011 98765-4321")).toBeNull();
  });

  it("recusa campo vazio", () => {
    expect(normalizaTelefone("")).toBeNull();
  });
});

describe("formataTelefone", () => {
  it("formata celular e fixo", () => {
    expect(formataTelefone("11987654321")).toBe("(11) 98765-4321");
    expect(formataTelefone("1134567890")).toBe("(11) 3456-7890");
  });
});

describe("metadadosDeContato", () => {
  const agora = new Date("2026-11-04T15:00:00Z");

  it("grava a hora do aceite do WhatsApp", () => {
    expect(metadadosDeContato("11987654321", true, null, agora)).toEqual({
      telefone: "11987654321",
      whatsapp_aceito_em: "2026-11-04T15:00:00.000Z",
    });
  });

  const anterior = { telefone: "11987654321", aceitoEm: "2026-10-01T10:00:00.000Z" };

  it("mantém a hora do aceite que já existia para o mesmo número", () => {
    expect(metadadosDeContato("11987654321", true, anterior, agora).whatsapp_aceito_em).toBe(
      "2026-10-01T10:00:00.000Z",
    );
  });

  it("número novo pede aceite novo: a data antiga era de outro número", () => {
    expect(metadadosDeContato("21999990000", true, anterior, agora).whatsapp_aceito_em).toBe(
      "2026-11-04T15:00:00.000Z",
    );
  });

  it("sem a caixa marcada, não há aceite", () => {
    expect(metadadosDeContato("11987654321", false, anterior, agora))
      .toEqual({ telefone: "11987654321", whatsapp_aceito_em: null });
  });

  it("sem telefone, não há aceite mesmo com a caixa marcada", () => {
    expect(metadadosDeContato(null, true, null, agora)).toEqual({
      telefone: null,
      whatsapp_aceito_em: null,
    });
  });
});
