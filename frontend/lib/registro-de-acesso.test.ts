import { describe, expect, it, vi } from "vitest";

import { INTERVALO_DO_REGISTRO, criaRegistrador } from "./registro-de-acesso";

describe("criaRegistrador", () => {
  it("não repete dentro do intervalo, e volta a enviar depois dele", async () => {
    let agora = 0;
    const enviar = vi.fn().mockResolvedValue(undefined);
    const tenta = criaRegistrador(enviar, () => agora);

    await tenta();
    agora = INTERVALO_DO_REGISTRO - 1;
    await tenta();
    expect(enviar).toHaveBeenCalledTimes(1);

    agora = INTERVALO_DO_REGISTRO;
    await tenta();
    expect(enviar).toHaveBeenCalledTimes(2);
  });

  it("a latência do envio não faz o relógio pular uma volta", async () => {
    let agora = 0;
    const enviar = vi.fn().mockImplementation(async () => {
      agora += 150;
    });
    const tenta = criaRegistrador(enviar, () => agora);

    await tenta();
    agora = INTERVALO_DO_REGISTRO;
    await tenta();
    expect(enviar).toHaveBeenCalledTimes(2);
  });

  it("depois de uma falha tenta de novo na chamada seguinte, sem quebrar a tela", async () => {
    const enviar = vi.fn().mockRejectedValueOnce(new Error("rede")).mockResolvedValue(undefined);
    const tenta = criaRegistrador(enviar, () => 0);

    await expect(tenta()).resolves.toBeUndefined();
    await tenta();
    expect(enviar).toHaveBeenCalledTimes(2);
  });
});
