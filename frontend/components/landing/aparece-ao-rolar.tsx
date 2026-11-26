"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";

/**
 * Marca `data-visivel` quando o bloco entra na tela, uma vez só. O CSS
 * (`.etapa-da-conversa`) faz o resto; os filhos podem ser Server Components.
 * `data-montado` desliga o fallback de 1,2 s, que só existe para quem está
 * sem JavaScript.
 *
 * Os dois atributos vão direto no DOM, e não por estado: nada no React
 * depende deles, e um `setState` síncrono no efeito só custaria um render a
 * mais (a regra `react-hooks/set-state-in-effect` barra).
 */
export function AparecerAoRolar({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  // Antes da pintura, como `texto-do-heroi.tsx`: as etapas não chegam a
  // aparecer pelo fallback e sumir de novo quando `data-montado` entra.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    // O CSS já mostrou a conversa (o JavaScript demorou mais que 1,2 s):
    // escondê-la de novo tiraria da frente o que a pessoa já está lendo.
    const etapa = el.querySelector(".etapa-da-conversa");
    const jaVisivel = etapa !== null && getComputedStyle(etapa).opacity !== "0";
    el.dataset.montado = "";
    if (jaVisivel) {
      el.dataset.visivel = "";
      return;
    }
    const observador = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          el.dataset.visivel = "";
          observador.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    observador.observe(el);
    return () => observador.disconnect();
  }, []);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
