import type { NomeDoPlano } from "@/lib/plano";

/**
 * Os preços que a vitrine e a contratação MOSTRAM.
 *
 * Quem cobra é o backend (`backend/planos.py`), que nunca recebe o valor do
 * navegador. Um teste de lá (`test_os_precos_da_vitrine_batem_com_os_do_backend`)
 * lê este arquivo e confere que os números batem: a tela não pode prometer um
 * preço e o checkout cobrar outro.
 *
 * Decididos pelo dono em 2026-10-29, com entrada baixa de propósito para trazer
 * os primeiros clientes e feedback.
 */
export const PRECOS_MENSAIS: Record<NomeDoPlano, number> = {
  essencial: 49.92,
  exclusive: 79.97,
  premium: 139.95,
};

/** Paga 10, leva 12. */
export const MESES_PAGOS_NO_ANUAL = 10;

/** Só o Exclusive mensal tem teste, de 7 dias. */
export const DIAS_DE_TESTE = 7;
export const PLANO_COM_TESTE: NomeDoPlano = "exclusive";

export function precoAnual(plano: NomeDoPlano): number {
  return Math.round(PRECOS_MENSAIS[plano] * MESES_PAGOS_NO_ANUAL * 100) / 100;
}

// Com centavos: os preços são quebrados de propósito, e arredondar R$ 49,92
// para R$ 50 mostraria outro preço.
const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
});

export function formatarPreco(valor: number): string {
  return brl.format(valor);
}
