import { describe, expect, it } from "vitest";

import { quemRecebeOFoco } from "./foco";

describe("quemRecebeOFoco", () => {
  it("devolve o foco ao botão da confirmação que acabou de fechar", () => {
    expect(quemRecebeOFoco("cancelar", null)).toBe("cancelar");
  });

  it("não mexe no foco ao abrir: ali quem decide é o autoFocus do Voltar", () => {
    expect(quemRecebeOFoco(null, "cancelar")).toBeNull();
  });

  it("não mexe no foco na primeira renderização", () => {
    expect(quemRecebeOFoco(null, null)).toBeNull();
  });

  it("trocar de uma confirmação para outra não devolve o foco à primeira", () => {
    expect(quemRecebeOFoco("essencial", "premium")).toBeNull();
  });
});
