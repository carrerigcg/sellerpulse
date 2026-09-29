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
 * `getServerSnapshot` devolve `false` (o servidor nunca sabe a largura da
 * tela nem a preferência de movimento de quem vai abrir a página), e
 * `getSnapshot` só é chamado no cliente, depois do primeiro paint — então
 * o primeiro HTML nunca contém a tag `<video>`.
 *
 * `prefers-reduced-motion: reduce` desliga o vídeo por completo (a tag
 * nunca é criada, o arquivo nunca é baixado), e abaixo de `md` também não
 * entra: nesse ponto o herói já empilhou o texto por cima da imagem numa
 * faixa estreita, e o vídeo vira peso de rede pago por alguém que nunca vê
 * metade dele em movimento. `subscribe` é um no-op de propósito — a decisão
 * é tomada uma vez no carregamento, não precisa reagir a um resize depois.
 *
 * O poster (`/hero/heroi.jpg`) já cobre o fundo por baixo deste componente
 * (ver `hero.tsx`) — se este vídeo nunca aparecer, a seção continua
 * correta.
 */
function subscribe() {
  return () => {};
}

function getSnapshot() {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const desktop = window.matchMedia("(min-width: 768px)").matches;
  return !reducedMotion && desktop;
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
      aria-hidden="true"
    >
      <source src="/hero/heroi.mp4" type="video/mp4" />
    </video>
  );
}
