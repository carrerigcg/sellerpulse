/**
 * A conversa de exemplo da seção "Pergunte ao Claude" na vitrine. Spec
 * `2026-11-25-vitrine-mcp-e-heroi`, seção 3.
 *
 * Os números saem do fluxo da loja de demonstração pela MESMA conta do Resumo
 * (`montaVeredito`), e nunca de valores escritos à mão: a demo se regenera
 * toda semana, e um número fixo aqui divergiria do `/demo` em silêncio. Sem
 * dado, a resposta não mostra número nenhum, nem velho nem zero.
 */
import { totalizarFluxo } from "../components/analytics/executive-totals";
import type { FluxoDia } from "./api";
import { coberturaDoFluxo } from "./cobertura";
import { montaVeredito, type ParteDaConta } from "./resumo";

export const PERGUNTA_DA_CONVERSA = "Quanto sobrou das minhas vendas nos últimos 30 dias?";

/** Sem algarismo nenhum, nem o "30": sem dado, a resposta não exibe número. */
export const SEM_NUMEROS =
  "Na sua conta, a resposta vem com a sobra dos últimos trinta dias e cada parte da conta: vendas, comissão do Mercado Livre, frete e custo dos produtos.";

export type RespostaDaConversa = {
  frase: string;
  linhas: ParteDaConta[] | null;
  fecho: string | null;
};

export function respostaDaConversa(
  dias: readonly FluxoDia[] | null,
  anteriores: readonly FluxoDia[] | null,
): RespostaDaConversa {
  if (!dias || dias.length === 0) return { frase: SEM_NUMEROS, linhas: null, fecho: null };
  const temAnterior = !!anteriores && anteriores.length > 0;
  const veredito = montaVeredito({
    atual: totalizarFluxo([...dias]),
    anterior: temAnterior ? totalizarFluxo([...anteriores]) : null,
    coberturaAtual: coberturaDoFluxo(dias),
    coberturaAnterior: temAnterior ? coberturaDoFluxo(anteriores) : null,
  });
  return { frase: veredito.sobra, linhas: veredito.partes, fecho: veredito.lembrete };
}
