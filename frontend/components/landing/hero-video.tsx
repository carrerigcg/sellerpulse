"use client";

import { useSyncExternalStore } from "react";

/**
 * Vídeo de fundo do herói — carregado condicionalmente, nunca no HTML
 * inicial.
 *
 * `useSyncExternalStore` em vez de `useEffect` + `useState`: isto não é
 * estado que muda por interação, é uma leitura de uma API externa
 * (`matchMedia`) que precisa concordar entre servidor e cliente sem
 * cascata de re-render nem divergência de hidratação.
 * `getServerSnapshot` devolve `false` (o servidor nunca sabe a preferência
 * de quem vai abrir a página), e `getSnapshot` só é chamado no cliente,
 * depois do primeiro paint — então o primeiro HTML nunca contém a tag
 * `<video>`.
 *
 * Duas condições desligam o vídeo, e as duas são preferência declarada de
 * quem visita, não palpite nosso sobre a máquina dela:
 *
 * - `prefers-reduced-motion: reduce` — quem liga isso costuma ter enxaqueca
 *   vestibular, epilepsia fotossensível ou distúrbio vestibular. Vídeo de
 *   tela cheia em movimento é exatamente o que essa preferência existe pra
 *   evitar, então aqui a tag nem é criada e o arquivo nunca é baixado.
 * - `connection.saveData` — o "Economia de dados" do navegador. Quem ligou
 *   pediu explicitamente pra não gastar banda com enfeite.
 *
 * NÃO há mais trava por largura de tela. Havia uma (`min-width: 768px`)
 * enquanto o vídeo pesava 13 MB e gastar isso no 4G de alguém era abusivo.
 * Depois de comprimir pra 1,4 MB o argumento caiu: é o peso de duas ou três
 * imagens, e no celular é onde a maior parte do tráfego frio chega — cortar
 * justo ali entregava a versão pior pra maioria.
 *
 * `subscribe` é um no-op de propósito: a decisão é tomada uma vez no
 * carregamento e não precisa reagir a mudança depois.
 *
 * O poster (`/hero/heroi.jpg`) já cobre o fundo por baixo deste componente
 * (ver `hero.tsx`) — se este vídeo nunca aparecer, a seção continua correta.
 */

type ConexaoComEconomia = { saveData?: boolean };

function subscribe() {
  return () => {};
}

function economizandoDados() {
  const conexao = (navigator as Navigator & { connection?: ConexaoComEconomia }).connection;
  return conexao?.saveData === true;
}

function getSnapshot() {
  const movimentoReduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return !movimentoReduzido && !economizandoDados();
}

function getServerSnapshot() {
  return false;
}

export function HeroVideo() {
  const mostrarVideo = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  if (!mostrarVideo) return null;

  return (
    <video
      className="absolute inset-0 h-full w-full object-cover"
      poster="/hero/heroi.jpg"
      autoPlay
      muted
      loop
      playsInline
      preload="auto"
      aria-hidden="true"
    >
      <source src="/hero/heroi.mp4" type="video/mp4" />
    </video>
  );
}
