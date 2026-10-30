"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { registrarAcesso } from "@/lib/ml";
import { INTERVALO_DO_REGISTRO, criaRegistrador } from "@/lib/registro-de-acesso";

/**
 * Avisa o backend de que a pessoa está usando o painel (Marco Civil, art. 15).
 *
 * Sai do navegador porque é o IP dele que precisa ser guardado: um Server
 * Component gravaria o da Vercel. Dispara ao trocar de tela, ao voltar para a
 * aba e, com a aba visível, a cada intervalo, para quem fica parado numa tela só.
 */
export function RegistroDeAcesso() {
  const caminho = usePathname();
  const tenta = useRef(criaRegistrador(registrarAcesso));

  useEffect(() => {
    void tenta.current();
  }, [caminho]);

  useEffect(() => {
    const seVisivel = () => {
      if (!document.hidden) void tenta.current();
    };
    const relogio = setInterval(seVisivel, INTERVALO_DO_REGISTRO);
    document.addEventListener("visibilitychange", seVisivel);
    return () => {
      clearInterval(relogio);
      document.removeEventListener("visibilitychange", seVisivel);
    };
  }, []);

  return null;
}
