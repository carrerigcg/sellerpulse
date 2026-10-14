/**
 * Dispara o download de um texto como arquivo, no navegador.
 *
 * Mora fora de `lib/csv.ts` de propósito: aquele arquivo é função pura e os
 * seus 16 testes rodam sem navegador nenhum. Este toca `document` e `URL`,
 * então só pode ser importado de Client Component — um Server Component que
 * o importe quebra em tempo de execução, com `lint` e `build` passando.
 *
 * Existe para não haver duas cópias da dança do blob: o botão de uma tabela
 * e o "baixar tudo" da aba Exportar chamam o mesmo código.
 */

/** Tipo MIME do CSV. O BOM dentro do conteúdo é o que o Excel realmente lê. */
const TIPO_CSV = "text/csv;charset=utf-8;";

export function baixaTexto(conteudo: string, nome: string, tipo = TIPO_CSV) {
  const blob = new Blob([conteudo], { type: tipo });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Sem o revoke, o blob fica preso na memória da aba até ela fechar — e
  // quem exporta dez vezes acumula dez cópias da tabela.
  URL.revokeObjectURL(url);
}

/**
 * Espera entre downloads consecutivos.
 *
 * Três `a.click()` no mesmo tique às vezes entregam só o último: o navegador
 * trata a rajada como uma coisa só. Um intervalo curto entre eles resolve, e
 * é imperceptível para quem clicou.
 */
export const INTERVALO_ENTRE_DOWNLOADS = 150;

export function espera(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
