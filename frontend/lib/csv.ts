/**
 * Geração de CSV que o Excel em português abre com dois cliques.
 *
 * Função pura, separada do botão de propósito: é o que a torna testável sem
 * navegador — e esta é a parte que precisa de teste, porque o modo de falha
 * aqui é silencioso. Um decimal com ponto em vez de vírgula não derruba nada:
 * gera um arquivo que abre, parece certo e tem os números errados.
 *
 * Três convenções, todas não-negociáveis pro Excel pt-BR:
 *
 * 1. `;` separa campos. Com `,`, o Excel em português joga a linha inteira
 *    numa coluna só — o arquivo "abre" e é ilegível.
 * 2. Decimal com vírgula. `1234.5` precisa virar `1234,5`, senão o Excel lê
 *    como texto e nenhuma soma funciona.
 * 3. BOM no começo. Sem ele o Excel no Windows lê UTF-8 como ANSI e
 *    "Iluminação" vira "IluminaÃ§Ã£o". São três bytes.
 */

/** Marca de ordem de byte. O Excel usa isto pra detectar UTF-8. */
export const BOM = "﻿";

const SEPARADOR = ";";
/** CRLF: o que o Excel espera, e o que evita linha corrida em editores do Windows. */
const FIM_DE_LINHA = "\r\n";

/**
 * Uma coluna do arquivo. **Dado puro, nunca função.**
 *
 * A tentação é `valor: (linha) => linha.receita`, que é mais flexível e
 * permitiria coluna derivada. Não funciona: estas definições saem de um Server
 * Component e entram num Client Component (o botão), e **função não atravessa
 * a fronteira RSC**. O erro aparece em tempo de execução, com `lint` e `build`
 * passando — as rotas do dashboard são dinâmicas e nunca são renderizadas no
 * build, então nada avisa. Este projeto já pagou por isso uma vez.
 *
 * `campo` é `keyof T` pra o TypeScript recusar nome de coluna que não existe.
 */
export type Coluna<T> = {
  /** Cabeçalho como a pessoa lê na planilha, não nome de coluna de banco. */
  titulo: string;
  /** Nome do campo na linha. Ausente ou nulo vira campo vazio. */
  campo: keyof T & string;
};

/**
 * Formata um valor como campo CSV.
 *
 * Número vira string com vírgula decimal. Texto é escapado quando contém
 * separador, aspas ou quebra de linha — título de produto com `;` e com `"`
 * existem no mundo real.
 *
 * Nulo e indefinido viram campo VAZIO, nunca `0` nem a string "null". É a
 * mesma regra do custo de produto e das visitas: ausência não é zero. Um `0`
 * numa planilha é uma afirmação, e quem somar a coluna vai acreditar nela.
 */
export function formataCampo(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined) return "";

  if (typeof valor === "number") {
    // NaN e Infinity viram vazio: é ausência de número, não um número.
    if (!Number.isFinite(valor)) return "";
    return String(valor).replace(".", ",");
  }

  const precisaDeAspas = /[;"\r\n]/.test(valor);
  // Aspas dentro do campo são duplicadas — é como o formato CSV as escapa.
  return precisaDeAspas ? `"${valor.replace(/"/g, '""')}"` : valor;
}

/**
 * Monta o conteúdo completo do arquivo, com BOM e cabeçalho.
 *
 * A ordem das colunas vem do array `colunas`, nunca das chaves do objeto —
 * ordem de chave em JavaScript é estável mas não é contrato, e a planilha
 * precisa sair igual sempre.
 */
export function montaCsv<T>(linhas: readonly T[], colunas: readonly Coluna<T>[]): string {
  const cabecalho = colunas.map((c) => formataCampo(c.titulo)).join(SEPARADOR);
  const corpo = linhas.map((linha) =>
    colunas
      .map((c) => formataCampo(linha[c.campo] as string | number | null | undefined))
      .join(SEPARADOR),
  );
  return BOM + [cabecalho, ...corpo].join(FIM_DE_LINHA) + FIM_DE_LINHA;
}

/**
 * Nome do arquivo com a tela e o período.
 *
 * `sellerpulse-produtos-2026-07-15_2026-10-13.csv`. O período no nome importa:
 * quem exporta três vezes com janelas diferentes acaba com três arquivos na
 * pasta de downloads, e sem a data não dá pra saber qual é qual.
 */
export function nomeDoArquivo(tela: string, de: string, ate: string): string {
  return `sellerpulse-${tela}-${de}_${ate}.csv`;
}
