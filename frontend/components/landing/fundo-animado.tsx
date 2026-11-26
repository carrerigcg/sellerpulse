"use client";

import { useEffect, useRef } from "react";

import { BARRAS, alturasDasBarras, progressoDaEntrada, projeta } from "@/lib/fundo-do-heroi";

const ALTURAS = alturasDasBarras();

/**
 * Fundo do herói desenhado em canvas: grade em perspectiva, barras de vendas
 * que crescem e "respiram", e a linha da sobra se desenhando. Substitui o
 * vídeo de 720p (borrado em tela grande; medição na spec
 * `2026-11-25-vitrine-mcp-e-heroi`).
 *
 * - Nítido em qualquer tela: desenha em `devicePixelRatio`.
 * - Para fora da tela (`IntersectionObserver`) e com a aba oculta.
 * - Movimento reduzido, economia de dados ou tela estreita: um quadro parado,
 *   o estado final.
 * - Sem JavaScript, fica o degradê da `<section>` (hero.tsx).
 */
export function FundoAnimado() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const conexao = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
    // Em tela estreita o painel do herói cobre quase todo o canvas: animar ali
    // gasta bateria de celular com um fundo que mal aparece.
    const parado =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      window.matchMedia("(max-width: 767px)").matches ||
      conexao?.saveData === true;

    let largura = 0;
    let altura = 0;
    const ajusta = () => {
      const r = canvas.getBoundingClientRect();
      const d = window.devicePixelRatio || 1;
      largura = r.width;
      altura = r.height;
      canvas.width = Math.round(r.width * d);
      canvas.height = Math.round(r.height * d);
      ctx.setTransform(d, 0, 0, d, 0, 0);
    };

    const desenha = (ms: number) => {
      const s = ms / 1000;
      ctx.clearRect(0, 0, largura, altura);
      const brilho = ctx.createRadialGradient(
        largura * 0.72,
        altura * 0.35,
        0,
        largura * 0.72,
        altura * 0.35,
        largura * 0.7,
      );
      brilho.addColorStop(0, "#3a1a08");
      brilho.addColorStop(1, "#0b0f1a");
      ctx.fillStyle = brilho;
      ctx.fillRect(0, 0, largura, altura);

      // Grade
      ctx.lineWidth = 1;
      for (let i = -14; i <= 14; i++) {
        const [x1, y1] = projeta(i / 12, 0, 0, largura, altura);
        const [x2, y2] = projeta(i / 12, 0, 1, largura, altura);
        ctx.strokeStyle = "rgba(251,146,60,0.16)";
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      for (let j = 0; j <= 10; j++) {
        const z = j / 10;
        const [x1, y1] = projeta(-1.2, 0, z, largura, altura);
        const [x2, y2] = projeta(1.2, 0, z, largura, altura);
        ctx.strokeStyle = `rgba(251,146,60,${0.12 * (1 - z)})`;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }

      // Barras
      const entrada = progressoDaEntrada(ms);
      for (let i = 0; i < BARRAS; i++) {
        const x = -0.85 + i * (1.75 / BARRAS);
        const z = 0.1 + 0.5 * (i / BARRAS);
        const cresce = Math.min(1, Math.max(0, entrada * 1.6 - (i / BARRAS) * 0.6));
        const respira = parado ? 1 : 0.92 + 0.08 * Math.sin(s * 0.8 + i * 0.6);
        const h = ALTURAS[i] * cresce * respira;
        const [bx, by] = projeta(x, 0, z, largura, altura);
        const [, ty] = projeta(x, h, z, largura, altura);
        const [bx2] = projeta(x + 0.018, 0, z, largura, altura);
        const g = ctx.createLinearGradient(0, by, 0, ty);
        g.addColorStop(0, "rgba(234,88,12,0.25)");
        g.addColorStop(1, "rgba(253,186,116,1)");
        ctx.fillStyle = g;
        ctx.shadowColor = "rgba(251,146,60,0.55)";
        ctx.shadowBlur = 14;
        ctx.fillRect(bx, ty, Math.max(2, bx2 - bx), by - ty);
      }
      ctx.shadowBlur = 0;

      // Linha da sobra, desenhando-se depois das barras
      const ate = parado ? 1 : Math.min(1, Math.max(0, (ms - 800) / 3000));
      ctx.beginPath();
      for (let i = 0; i <= Math.floor((BARRAS - 1) * ate); i++) {
        const x = -0.85 + i * (1.75 / BARRAS) + 0.009;
        const y = ALTURAS[i] * 0.55 + (parado ? 0 : 0.04 * Math.sin(s * 0.6 + i * 0.3));
        const [px, py] = projeta(x, y, 0.1 + 0.5 * (i / BARRAS), largura, altura);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "rgba(250,204,21,0.8)";
      ctx.shadowBlur = 18;
      ctx.stroke();
      ctx.shadowBlur = 0;
    };

    ajusta();
    if (parado) {
      desenha(60_000);
      const aoMudar = () => {
        ajusta();
        desenha(60_000);
      };
      window.addEventListener("resize", aoMudar);
      return () => window.removeEventListener("resize", aoMudar);
    }

    let quadro = 0;
    let visivel = true;
    let inicio: number | null = null;
    const passo = (agora: number) => {
      inicio ??= agora;
      desenha(agora - inicio);
      quadro = requestAnimationFrame(passo);
    };
    const liga = () => {
      cancelAnimationFrame(quadro);
      if (visivel && document.visibilityState === "visible") quadro = requestAnimationFrame(passo);
    };
    const observador = new IntersectionObserver(([e]) => {
      visivel = e.isIntersecting;
      liga();
    });
    observador.observe(canvas);
    document.addEventListener("visibilitychange", liga);
    window.addEventListener("resize", ajusta);
    liga();

    return () => {
      cancelAnimationFrame(quadro);
      observador.disconnect();
      document.removeEventListener("visibilitychange", liga);
      window.removeEventListener("resize", ajusta);
    };
  }, []);

  return <canvas ref={ref} aria-hidden="true" className="absolute inset-0 h-full w-full" />;
}
