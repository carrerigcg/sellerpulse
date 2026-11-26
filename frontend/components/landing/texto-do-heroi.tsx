"use client";

import { useLayoutEffect, useRef, useState } from "react";

import {
  FRASE_DO_HEROI,
  SUBTITULO_DO_HEROI,
  type Letra,
  caracteresDaFrase,
  fimDaDigitacao,
  temposDaDigitacao,
  textoDaFrase,
} from "@/lib/escrita";

const LETRAS = caracteresDaFrase(FRASE_DO_HEROI);
const TEMPOS = temposDaDigitacao(LETRAS);
const FIM = fimDaDigitacao(TEMPOS);
const PALAVRAS = SUBTITULO_DO_HEROI.split(" ");
/** Intervalo da cascata do subtítulo, e quanto o cursor fica depois do fim. */
const POR_PALAVRA = 40;
const CURSOR_DEPOIS = 2000;

/**
 * A frase de destaque digitada letra a letra, e o subtítulo surgindo palavra
 * por palavra depois dela. Spec `2026-11-25-vitrine-mcp-e-heroi`, seção 2.
 *
 * O texto inteiro sai do servidor: num `sr-only` para leitor de tela e busca,
 * e numa cópia invisível que reserva o espaço (a página não pula). A camada
 * digitada é `aria-hidden`. Sem JavaScript, o CSS mostra a frase pronta em
 * 1,2 s (`.escrita`); com movimento reduzido, ela já vem pronta.
 */
export function TextoDoHeroi() {
  const ref = useRef<HTMLSpanElement>(null);
  const [mostradas, setMostradas] = useState(LETRAS.length);
  const [pronto, setPronto] = useState(false);
  const [cursor, setCursor] = useState(false);
  const [revelar, setRevelar] = useState(false);
  const [montado, setMontado] = useState(false);

  // Antes da pintura, para a frase pronta não piscar antes de sumir e
  // começar a digitação.
  useLayoutEffect(() => {
    const el = ref.current;
    const semMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // O CSS já mostrou a frase (o JavaScript demorou mais que 1,2 s):
    // apagar e redigitar tiraria da frente o que a pessoa já está lendo.
    const jaVisivel = el !== null && getComputedStyle(el).opacity !== "0";
    if (semMovimento || jaVisivel) {
      setMontado(true);
      setPronto(true);
      setRevelar(true);
      return;
    }
    setMontado(true);
    setMostradas(0);
    setPronto(true);
    setCursor(true);
    const timers = TEMPOS.map((t, i) => window.setTimeout(() => setMostradas(i + 1), t));
    timers.push(window.setTimeout(() => setRevelar(true), FIM + 150));
    timers.push(window.setTimeout(() => setCursor(false), FIM + CURSOR_DEPOIS));
    return () => {
      timers.forEach(clearTimeout);
      setMostradas(LETRAS.length);
    };
  }, []);

  const digitadas = LETRAS.slice(0, mostradas);

  return (
    <>
      <h1 className="mt-4 text-4xl font-semibold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-6xl">
        <span className="sr-only">{textoDaFrase(FRASE_DO_HEROI)}</span>
        <span aria-hidden="true" className="relative block">
          {/* Reserva o espaço da frase inteira: a digitação não empurra o resto. */}
          <span className="invisible">
            <Frase letras={LETRAS} />
          </span>
          <span ref={ref} className="escrita absolute inset-0" data-pronto={pronto || undefined}>
            <Frase letras={digitadas} />
            {cursor && <span className="cursor-da-escrita" />}
          </span>
        </span>
      </h1>
      <p
        className="subtitulo-do-heroi mt-6 text-lg text-white/80"
        data-revelar={revelar || undefined}
        data-montado={montado || undefined}
      >
        {PALAVRAS.map((p, i) => (
          <span key={i}>
            <span className="palavra-revelada" style={{ transitionDelay: `${i * POR_PALAVRA}ms` }}>
              {p}
            </span>{" "}
          </span>
        ))}
      </p>
    </>
  );
}

/** Junta as letras de volta em texto, com o trecho de destaque na cor da marca. */
function Frase({ letras }: { letras: readonly Letra[] }) {
  const fatia = (a: number, b?: number) =>
    letras
      .slice(a, b)
      .map((c) => c.letra)
      .join("");
  // Três pedaços na ordem: antes do destaque, o destaque, depois dele.
  const inicio = letras.findIndex((c) => c.destaque);
  if (inicio === -1) return <>{fatia(0)}</>;
  const depois = letras.findIndex((c, i) => i > inicio && !c.destaque);
  return (
    <>
      {fatia(0, inicio)}
      <span className="text-accent-on-dark">{fatia(inicio, depois === -1 ? undefined : depois)}</span>
      {depois !== -1 && fatia(depois)}
    </>
  );
}
