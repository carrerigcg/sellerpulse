/**
 * Leitura do que a pessoa digita no campo de custo.
 *
 * Arquivo separado de `custos-client.ts` pelo mesmo motivo que `csv.ts` é
 * separado de `baixar-arquivo.ts`: esta parte é função pura e precisa rodar
 * em teste sem navegador, sem sessão e sem rede. O outro arquivo importa o
 * cliente Supabase e não carrega fora do browser.
 */

/**
 * Lê o que a pessoa digitou no campo de custo.
 *
 * Aceita vírgula decimal, porque é o que um vendedor brasileiro digita, e
 * aceita "R$" colado na frente, porque é o que acontece quando se cola um
 * valor de outra planilha.
 *
 * Os três retornos são distintos de propósito:
 * - `null`   — campo vazio, ou seja "não informado". Nunca zero.
 * - `undefined` — não dá para interpretar; a tela recusa e não salva.
 * - número   — o valor.
 *
 * O PONTO É AMBÍGUO e a conta é em dinheiro, então não dá para escolher no
 * chute. "1.234,56" é padrão brasileiro e o ponto é milhar; "48.50" é o que
 * sai de uma planilha em inglês e o ponto é decimal. Ler o segundo como
 * milhar daria 4850 — custo cem vezes maior, margem do mês destruída, e nada
 * falharia.
 *
 * A regra: havendo vírgula, ela é o decimal e todo ponto é milhar. Sem
 * vírgula, um ponto seguido de exatamente 3 dígitos é milhar ("1.234") e
 * qualquer outro ponto é decimal ("48.50", "48.5").
 */
export function leValorDigitado(bruto: string): number | null | undefined {
  const semRuido = bruto.replace(/R\$/gi, "").replace(/\s/g, "");
  if (semRuido === "") return null;

  let normalizado: string;
  if (semRuido.includes(",")) {
    normalizado = semRuido.replace(/\./g, "").replace(",", ".");
  } else if (/^\d{1,3}(\.\d{3})+$/.test(semRuido)) {
    normalizado = semRuido.replace(/\./g, "");
  } else {
    normalizado = semRuido;
  }

  const numero = Number(normalizado);
  if (!Number.isFinite(numero) || numero < 0) return undefined;
  return numero;
}
