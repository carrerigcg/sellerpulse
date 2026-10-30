"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { registrarAcesso } from "@/lib/ml";

const UMA_HORA = 60 * 60 * 1000;

/**
 * Avisa o backend de que a pessoa está usando o painel (Marco Civil, art. 15).
 *
 * Sai do navegador porque é o IP dele que precisa ser guardado: um Server
 * Component gravaria o da Vercel. O backend guarda uma linha por hora, então
 * só se chama de novo quando muda a hora. Falha aqui nunca atrapalha a tela.
 */
export function RegistroDeAcesso() {
  const caminho = usePathname();
  const ultimo = useRef(0);

  useEffect(() => {
    if (Date.now() - ultimo.current < UMA_HORA) return;
    ultimo.current = Date.now();
    registrarAcesso().catch(() => {});
  }, [caminho]);

  return null;
}
