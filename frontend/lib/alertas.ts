/**
 * Os alertas do Premium, como `GET /metrics/alertas` os devolve, e as frases
 * do card. Spec `docs/specs/2026-11-06-premium-alertas-no-painel-design.md`.
 *
 * Quem decide o que é alerta é o backend; aqui só se escreve.
 */

export type AlertaDeMargem = { sku: string; titulo: string; receita: number; margem: number };

export type AlertaDeParado = {
  sku: string;
  titulo: string;
  dias_sem_vender: number;
  intervalo_normal: number;
  ultima_venda: string;
};

export type Alertas = {
  /** Produtos com custo e frete conhecidos em todas as vendas dos 30 dias. */
  produtos_avaliados: number;
  margem_negativa: AlertaDeMargem[];
  parados: AlertaDeParado[];
  /** O dia da última sincronização, até onde os dias parados são contados. */
  referencia: string | null;
};

/** No card, os piores primeiro; o total vai ao lado. */
export const MAX_POR_TIPO = 5;

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/**
 * O anúncio no Mercado Livre. O id da API ("MLB123") vira o do endereço
 * ("MLB-123"). Id em outro formato não ganha link: um endereço adivinhado
 * levaria a uma página de erro.
 */
export function linkDoAnuncio(sku: string): string | null {
  const partes = /^([A-Z]{3})(\d+)$/.exec(sku);
  return partes ? `https://produto.mercadolivre.com.br/${partes[1]}-${partes[2]}` : null;
}

/**
 * O que dizer sobre a margem. Sem nenhum produto avaliado, "nenhum alerta"
 * afirmaria que a margem está boa, e o que se sabe é que ela não foi medida.
 */
export function estadoDaMargem(alertas: Alertas): "sem-custo" | "nenhum" | "alertas" {
  if (alertas.margem_negativa.length > 0) return "alertas";
  return alertas.produtos_avaliados === 0 ? "sem-custo" : "nenhum";
}

export function fraseDaMargem(alerta: AlertaDeMargem): string {
  return `Prejuízo de ${brl.format(-alerta.margem)} em ${brl.format(alerta.receita)} vendidos nos últimos 30 dias, já tirando taxa, frete e custo.`;
}

export function fraseDoParado(alerta: AlertaDeParado): string {
  const ritmo =
    alerta.intervalo_normal <= 1 ? "costuma vender todo dia" : `costuma vender a cada ${alerta.intervalo_normal} dias`;
  return `Sem vender há ${alerta.dias_sem_vender} dias; ${ritmo}.`;
}
