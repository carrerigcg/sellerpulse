"use client";

import { useLayoutEffect, useRef, useState } from "react";

import { DURACAO_DA_CONTAGEM, valorNaContagem } from "@/lib/contagem";

/**
 * Os formatos são nomeados, e não uma função passada de fora: função não
 * atravessa a fronteira de Server Component para Client Component.
 */
const FORMATOS = {
  reais: new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }),
} as const;

export type FormatoDoNumero = keyof typeof FORMATOS;

/**
 * Um número que sobe de 0 até o valor quando a tela abre.
 *
 * O servidor já manda o valor final no HTML, escondido pela classe `contador`
 * (globals.css). Ao montar, o número conta de 0 até ele. Sem JavaScript, o
 * CSS mostra o valor final depois de 1,2 s: nunca fica um "R$ 0" na tela,
 * porque zero seria uma afirmação. Com movimento reduzido, aparece direto. O
 * leitor de tela lê só o valor final.
 */
export function NumeroAnimado({
  valor,
  formato = "reais",
}: {
  valor: number;
  formato?: FormatoDoNumero;
}) {
  const formatador = FORMATOS[formato];
  const ref = useRef<HTMLSpanElement>(null);
  const [mostrado, setMostrado] = useState(valor);
  const [pronto, setPronto] = useState(false);

  // Antes da pintura: na navegação dentro do painel, o valor final não chega
  // a piscar antes de a contagem começar.
  useLayoutEffect(() => {
    const el = ref.current;
    const semMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // O CSS já mostrou o número (o JavaScript demorou mais que o atraso dele):
    // recomeçar do zero faria o valor certo sumir da frente de quem já leu.
    const jaVisivel = el !== null && getComputedStyle(el).opacity !== "0";
    if (semMovimento || jaVisivel || valor === 0) {
      setMostrado(valor);
      setPronto(true);
      return;
    }
    let quadro = 0;
    const inicio = performance.now();
    const passo = (agora: number) => {
      const decorrido = agora - inicio;
      setMostrado(valorNaContagem(valor, decorrido));
      if (decorrido < DURACAO_DA_CONTAGEM) quadro = requestAnimationFrame(passo);
    };
    setMostrado(0);
    setPronto(true);
    quadro = requestAnimationFrame(passo);
    return () => {
      cancelAnimationFrame(quadro);
      setMostrado(valor);
    };
  }, [valor]);

  return (
    <>
      <span ref={ref} aria-hidden="true" className="contador" data-pronto={pronto || undefined}>
        {formatador.format(mostrado)}
      </span>
      <span className="sr-only">{formatador.format(valor)}</span>
    </>
  );
}
