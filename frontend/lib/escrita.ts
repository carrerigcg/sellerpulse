/**
 * A frase de destaque do herói e o ritmo da digitação. Spec
 * `docs/specs/2026-11-25-vitrine-mcp-e-heroi-design.md`, seção 2.
 *
 * Sem React de propósito: o front não testa componentes, então o texto e o
 * ritmo moram aqui, onde o vitest alcança.
 */

export type Trecho = { texto: string; destaque?: boolean };
export type Letra = { letra: string; destaque: boolean };

export const FRASE_DO_HEROI: readonly Trecho[] = [
  { texto: "Todo vendedor tem os números. Poucos têm as " },
  { texto: "respostas", destaque: true },
  { texto: "." },
];

export const SUBTITULO_DO_HEROI =
  "O Mercado Livre te mostra o que entrou. O SellerPulse mostra o que sobrou, qual produto puxa o faturamento, qual anúncio queima visita sem vender e qual cliente valia reconquistar — tudo calculado a partir dos seus pedidos reais.";

/**
 * Respiro antes da primeira letra: o painel aparece, depois a escrita. Curto
 * porque entra na conta do LCP junto com as letras e a pausa do ponto.
 */
export const ATRASO_INICIAL = 100;
/** 30 a 40 ms por letra: cabe em ~2 s, que é o teto do LCP (spec, seção 2). */
const POR_LETRA = 30;
const VARIACAO = 10;
export const PAUSA_NO_PONTO = 280;

export function textoDaFrase(frase: readonly Trecho[]): string {
  return frase.map((t) => t.texto).join("");
}

export function caracteresDaFrase(frase: readonly Trecho[]): Letra[] {
  return frase.flatMap((t) => [...t.texto].map((letra) => ({ letra, destaque: !!t.destaque })));
}

/**
 * Quando cada letra aparece, em ms desde a montagem. A variação imita a mão
 * de quem digita, mas sai do índice e não de `Math.random`: o mesmo ritmo a
 * cada carregamento, e o teste consegue medir.
 */
export function temposDaDigitacao(letras: readonly Letra[]): number[] {
  const tempos: number[] = [];
  let t = ATRASO_INICIAL;
  letras.forEach((c, i) => {
    const anterior = letras[i - 1];
    if (anterior?.letra === ".") t += PAUSA_NO_PONTO;
    t += POR_LETRA + ((i * 7) % (VARIACAO + 1));
    tempos.push(t);
  });
  return tempos;
}

export function fimDaDigitacao(tempos: readonly number[]): number {
  return tempos[tempos.length - 1] ?? 0;
}
