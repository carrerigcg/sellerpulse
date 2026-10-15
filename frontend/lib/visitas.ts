/**
 * Quando avisar que as visitas ainda não fecharam.
 *
 * O Mercado Livre leva cerca de 48 horas para consolidar a contagem de
 * visitas. Um período que inclua ontem ou anteontem mostra números que vão
 * subir depois — e conversão calculada sobre eles sai alta demais, porque as
 * vendas já estão todas lá e as visitas não.
 *
 * Não é motivo para esconder o número: é motivo para dizer que ele ainda vai
 * mudar. Mesma regra da cobertura de custo — nunca apresentar como fechado o
 * que não fechou.
 *
 * Função pura e testada porque a conta tem uma pegadinha: o "Até" do seletor
 * é EXCLUSIVO neste projeto, então o último dia que o período realmente
 * contém é o anterior a ele. Errar isso faz o aviso aparecer um dia atrasado
 * ou adiantado, e ninguém notaria.
 */

/** Dias que o Mercado Livre ainda pode revisar para cima. */
export const DIAS_SEM_CONSOLIDAR = 2;

function soData(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

/**
 * O período vai até perto demais de hoje para as visitas estarem fechadas?
 *
 * @param ate Fim do período no formato `YYYY-MM-DD`, EXCLUSIVO.
 * @param hoje Referência; o padrão é a data corrente.
 */
export function incluiDiasNaoConsolidados(ate: string, hoje: Date = new Date()): boolean {
  const fimExclusivo = new Date(`${ate}T00:00:00Z`);
  if (Number.isNaN(fimExclusivo.getTime())) return false;

  // O último dia REALMENTE contido é o anterior ao limite exclusivo.
  const ultimoDiaIncluido = soData(fimExclusivo) - 24 * 60 * 60 * 1000;
  const primeiroDiaDuvidoso = soData(hoje) - DIAS_SEM_CONSOLIDAR * 24 * 60 * 60 * 1000;

  return ultimoDiaIncluido >= primeiroDiaDuvidoso;
}

/**
 * Há alguma visita colhida nestas linhas?
 *
 * Sem isto, quem nunca sincronizou visitas veria um aviso sobre consolidação
 * de dados que não existem — ruído puro, e ruído ensina a ignorar avisos.
 */
export function temVisitaColhida(linhas: readonly { visitas: number | null }[]): boolean {
  return linhas.some((linha) => linha.visitas !== null);
}
