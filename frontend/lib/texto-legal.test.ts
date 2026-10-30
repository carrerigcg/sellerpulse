import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ler = (arquivo: string) =>
  readFileSync(path.join(process.cwd(), "content/legal", arquivo), "utf-8");

describe.each(["termos-de-uso.md", "politica-de-privacidade.md"])("%s", (arquivo) => {
  // Trava de publicação: nome, documento e endereço nunca entram por suposição.
  it("não tem dado pendente", () => {
    expect(ler(arquivo).match(/\[DADO:[^\]]*\]/g) ?? []).toEqual([]);
  });

  // Decisão do dono: documento e endereço pessoais não vão para o site.
  it("não expõe CPF, CNPJ nem endereço do titular", () => {
    const texto = ler(arquivo);
    expect(texto.match(/\d{3}\.?\d{3}\.?\d{3}-?\d{2}/g) ?? []).toEqual([]);
    expect(texto.match(/\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}/g) ?? []).toEqual([]);
    expect(texto).not.toMatch(/com endereço em/);
  });

  it("não tem colchete de rascunho", () => {
    // Link de Markdown, `[texto](/rota)`, é o único colchete permitido.
    expect(ler(arquivo).match(/\[[^\]]*\](?!\()/g) ?? []).toEqual([]);
  });
});
