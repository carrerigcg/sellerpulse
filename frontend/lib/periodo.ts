/**
 * Janela padrão das telas de análise: os últimos 90 dias, terminando em HOJE
 * NO FUSO DO VENDEDOR.
 *
 * Uma função para as dez telas — as cinco do dashboard e as cinco da demo.
 * Antes eram seis cópias idênticas byte a byte: cinco locais nas páginas do
 * dashboard e uma em `lib/demo.ts`. A da demo dizia viver num lugar só
 * "porque três cópias divergem", enquanto o dashboard ao lado tinha cinco.
 *
 * ## Por que o fuso, e não `toISOString()`
 *
 * As seis cópias usavam `new Date().toISOString().slice(0, 10)`, que é a data
 * em UTC. O backend conta o dia em `America/Sao_Paulo` (`FUSO_DO_VENDEDOR` em
 * `backend/analytics/_common.py`) — agrupar em UTC já moveu 14% dos pedidos
 * para o dia seguinte lá.
 *
 * Estas páginas são Server Components e rodam na Vercel, em UTC. Depois das
 * 21h em São Paulo a data UTC já é amanhã, e com o "Até" exclusivo a janela
 * padrão INCLUÍA o dia corrente à noite e o EXCLUÍA de manhã: a mesma tela
 * mudava de recorte conforme a hora em que era aberta. Calculado no fuso do
 * vendedor, "Até = hoje" significa sempre "até ontem, inclusive" — que é o
 * que o seletor exclusivo promete.
 *
 * ## A demo usa a mesma janela, de propósito
 *
 * A janela da demo já foi fixa, e a cicatriz vale registrar. O vendedor da
 * demo é sintético e seus pedidos paravam em 31/07/2026; uma janela ancorada
 * em hoje escorregava para fora do dado, e em 01/10 os cartões da Executive
 * exibiam −54,7% — a conta estava certa, e a leitura era de um negócio em
 * colapso, na única tela feita para atrair cliente.
 *
 * A causa foi resolvida no backend: o seller de demonstração é regenerado no
 * boot sempre que a venda mais recente passa de 7 dias, terminando em hoje
 * (`backend/demo_refresh.py`). Com o dado sempre corrente, a janela relativa
 * volta a ser a certa, e passa a ser a MESMA do dashboard. É por isso que esta
 * função não tem variante para a demo: a vitrine mostra o produto, não uma
 * versão especial dele.
 */

export const FUSO_DO_VENDEDOR = "America/Sao_Paulo";

export const DIAS_DO_PERIODO_PADRAO = 90;

/**
 * Data de hoje no fuso do vendedor, como `YYYY-MM-DD`.
 *
 * `formatToParts` em vez de formatar com um locale que "por acaso" sai como
 * `YYYY-MM-DD` (o truque comum é o `en-CA`). O formato de data de um locale é
 * dado do ICU, não contrato; montar a partir das partes nomeadas não depende
 * de nenhum locale manter a ordem e o separador.
 */
export function hojeNoFusoDoVendedor(agora: Date = new Date()): string {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: FUSO_DO_VENDEDOR,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(agora);
  const parte = (tipo: Intl.DateTimeFormatPartTypes) =>
    partes.find((p) => p.type === tipo)?.value ?? "";
  return `${parte("year")}-${parte("month")}-${parte("day")}`;
}

/**
 * `{ de, ate }` dos últimos 90 dias, com `ate` = hoje no fuso do vendedor.
 *
 * `ate` é EXCLUSIVO, como em todo o projeto: a janela vai até ontem.
 */
export function periodoPadrao(agora: Date = new Date()): { de: string; ate: string } {
  const ate = hojeNoFusoDoVendedor(agora);
  const [ano, mes, dia] = ate.split("-").map(Number);
  // A subtração é sobre a DATA de calendário, em UTC puro: o resultado é um
  // dia, não um instante, então nenhum fuso nem horário de verão consegue
  // empurrar o início um dia para o lado.
  const inicio = new Date(Date.UTC(ano, mes - 1, dia - DIAS_DO_PERIODO_PADRAO));
  return { de: inicio.toISOString().slice(0, 10), ate };
}
