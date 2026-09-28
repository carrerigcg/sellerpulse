"use client";

import { useEffect } from "react";

import { sincronizar } from "@/lib/ml";

/**
 * Dispara a sincronização incremental ao abrir o dashboard.
 *
 * Quem decide se vale a pena é o backend (janela de 6h) — aqui só avisamos
 * que o usuário chegou. Deixar a decisão no cliente permitiria que uma aba
 * aberta desde ontem ignorasse a janela e queimasse o rate limit do ML.
 *
 * Não renderiza nada e falha em silêncio: se a sincronização não rolar, o
 * dashboard ainda mostra o dado que já está no banco.
 */
export function DisparaDelta() {
  useEffect(() => {
    void sincronizar("login").catch(() => {});
  }, []);
  return null;
}
