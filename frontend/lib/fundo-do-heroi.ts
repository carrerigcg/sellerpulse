/**
 * O desenho do fundo do herói, sem canvas: barras de vendas num plano em
 * perspectiva. Spec `2026-11-25-vitrine-mcp-e-heroi`, seção 1.
 *
 * As alturas não são dado de ninguém e não levam rótulo na tela: é enfeite,
 * e enfeite com número seria número inventado.
 */

export const BARRAS = 56;
/** Tempo até as barras terminarem de crescer na entrada. */
export const DURACAO_DA_ENTRADA = 2200;

/** Ondas somadas: um perfil de vendas plausível, igual em todo carregamento. */
export function alturasDasBarras(): number[] {
  return Array.from({ length: BARRAS }, (_, i) => {
    const h =
      0.42 + 0.22 * Math.sin(i * 0.45) + 0.16 * Math.sin(i * 1.3 + 1) + 0.14 * (i / BARRAS);
    return Math.min(1, Math.max(0.1, h));
  });
}

/** 0 → 1 com desaceleração no fim (ease-out cúbico). */
export function progressoDaEntrada(ms: number): number {
  const t = Math.min(1, Math.max(0, ms / DURACAO_DA_ENTRADA));
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Leva um ponto do plano (x lateral, y altura, z profundidade 0..1) para a
 * tela. O plano sobe e encolhe para o fundo, que fica à direita do texto.
 */
export function projeta(
  x: number,
  y: number,
  z: number,
  largura: number,
  altura: number,
): [number, number] {
  const f = 1 / (1 + z * 0.9);
  return [largura * 0.5 + x * largura * 0.62 * f, altura * 0.86 - y * altura * 0.8 * f - z * altura * 0.32];
}
