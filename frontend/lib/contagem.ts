/**
 * A conta da animação de contagem dos números do painel (de 0 até o valor).
 *
 * Fica separada do componente para ser testada sem navegador. O último quadro
 * devolve o valor exato, nunca uma aproximação: a animação é enfeite, o
 * número final é o dado.
 */

/** Quanto dura a subida, em milissegundos. Rápido: o número é o que importa. */
export const DURACAO_DA_CONTAGEM = 700;

/** Desacelera no fim (cúbica), para o número "pousar" no valor. */
function desacelera(t: number): number {
  return 1 - (1 - t) ** 3;
}

/** O valor a mostrar `decorrido` ms depois do início da contagem. */
export function valorNaContagem(
  valor: number,
  decorrido: number,
  duracao = DURACAO_DA_CONTAGEM,
): number {
  if (!(decorrido < duracao)) return valor;
  if (decorrido <= 0) return 0;
  return valor * desacelera(decorrido / duracao);
}
