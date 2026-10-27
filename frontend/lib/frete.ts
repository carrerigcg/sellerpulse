import type { FluxoDia } from "./api";

/** O dia como o backend entrega: com o frete ainda numérico. */
export type FluxoDiaDaApi = Omit<FluxoDia, "frete"> & { frete: number };

/**
 * O frete ainda não é calculado — e a tela tem que dizer isso, não mostrar 0.
 *
 * Auditoria de 2026-10-27, na conta real em produção: 1.091 de 1.091 pedidos
 * pagos com frete R$ 0,00. A ingestão lê `shipping_cost` da raiz do pedido, que
 * o Mercado Livre nunca preenche; o custo que o vendedor paga só existe em
 * `GET /shipments/{id}` (ver `extrai_taxa_e_frete` em `backend/ml/ingest_pg.py`).
 * Já a demo, sintética, traz frete — e o backend o desconta da margem dela. Sem
 * esta função, a demo mostraria uma conta que o produto real não faz, e as
 * frases afirmariam um desconto que não acontece.
 *
 * Por isso, num ponto só (os getters do fluxo): frete vira ausência (`null`,
 * que o CSV escreve vazio) e a margem é recalculada sem ele. Quando o frete
 * real existir, esta função sai e o backend volta a mandar o número.
 */
export function semFreteCalculado(dias: readonly FluxoDiaDaApi[]): FluxoDia[] {
  return dias.map((d) => ({
    ...d,
    frete: null,
    margem_contribuicao: d.receita_bruta - d.taxas_ml - d.custo_produtos,
  }));
}
