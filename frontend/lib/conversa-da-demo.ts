/**
 * A conversa de exemplo da seção "Pergunte ao Claude" na vitrine. Spec
 * `2026-11-25-vitrine-mcp-e-heroi`, seção 3.
 *
 * Os números saem do fluxo da loja de demonstração pela MESMA função do Resumo
 * (`vereditoDoFluxo`), e nunca de valores escritos à mão: a demo se regenera
 * toda semana, e um número fixo aqui divergiria do `/demo` em silêncio. Os
 * avisos de custo e frete faltando vêm junto, porque a seção promete que a IA
 * "diz quando falta dado". Sem dado, a resposta não mostra número nenhum.
 */
import type { FluxoDia } from "./api";
import { vereditoDoFluxo, type ParteDaConta } from "./resumo";

export const PERGUNTA_DA_CONVERSA = "Quanto sobrou das minhas vendas nos últimos 30 dias?";

/** Sem algarismo nenhum, nem o "30": sem dado, a resposta não exibe número. */
export const SEM_NUMEROS =
  "Na sua conta, a resposta vem com a sobra dos últimos trinta dias e cada parte da conta: vendas, comissão do Mercado Livre, frete e custo dos produtos.";

export type RespostaDaConversa = {
  frase: string;
  linhas: ParteDaConta[] | null;
  /** Custo ou frete faltando: a sobra mostrada é maior que a real. */
  avisos: string[];
  fecho: string | null;
};

export function respostaDaConversa(
  dias: readonly FluxoDia[] | null,
  anteriores: readonly FluxoDia[] | null,
): RespostaDaConversa {
  if (!dias || dias.length === 0) {
    return { frase: SEM_NUMEROS, linhas: null, avisos: [], fecho: null };
  }
  const veredito = vereditoDoFluxo(dias, anteriores ?? []);
  return {
    frase: veredito.sobra,
    linhas: veredito.partes,
    avisos: [veredito.avisoCobertura, veredito.avisoFrete].filter((a): a is string => a !== null),
    fecho: veredito.lembrete,
  };
}
