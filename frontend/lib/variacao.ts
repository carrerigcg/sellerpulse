/**
 * Variação sobre o período anterior no formato do resto do produto: vírgula
 * decimal e sinal explícito ("+1,1%", "-54,7%").
 *
 * Não recebe `null` de propósito. Sem período anterior não há variação, e o
 * `KpiCard` omite o selo inteiro — passar um 0 aqui para preencher o buraco
 * afirmaria que nada mudou.
 */
const variacao = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  // O que arredonda para zero sai sem sinal: "+0,0%" e "-0,0%" afirmariam um
  // sentido que a casa decimal mostrada não sustenta.
  signDisplay: "exceptZero",
});

export function formatarVariacao(pct: number): string {
  return `${variacao.format(pct)}%`;
}
