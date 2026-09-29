/**
 * Cliente da API do SellerPulse (FastAPI) para a demonstração pública.
 *
 * Espelha `lib/api.ts`, mas contra `/demo/*` — sem sessão, sem header
 * `Authorization`. É um arquivo separado, e não `lib/api.ts` com uma flag
 * "sem auth", de propósito: um cliente autenticado que *pode* deixar de
 * anexar o token é um refactor de distância de vazar o token de um usuário
 * de verdade numa chamada pública. Aqui não existe token pra vazar — o
 * arquivo inteiro não sabe o que é uma sessão do Supabase.
 *
 * `seller_id` nunca é parâmetro: o backend resolve pelo `DEMO_SELLER_ID` do
 * servidor (`backend/routers/demo.py`) e ignora qualquer coisa que o
 * cliente mande.
 */

import type { AbcLinha, CohortLinha, FluxoDia, RfmLinha } from "@/lib/api";
import { ApiError } from "@/lib/api";

const BASE = process.env.NEXT_PUBLIC_API_URL!;

async function buscarDemo<T>(caminho: string, params: Record<string, string>): Promise<T> {
  const query = new URLSearchParams(params).toString();
  const resposta = await fetch(`${BASE}${caminho}?${query}`, {
    // Sem Authorization — a demo não tem sessão. O `Cache-Control: public`
    // que o backend já manda é quem decide o cache; aqui só evitamos que o
    // Next guarde uma resposta de erro transiente como se fosse definitiva.
    cache: "no-store",
  });

  if (!resposta.ok) {
    throw new ApiError(resposta.status, `Falha ao buscar ${caminho}`);
  }
  return resposta.json();
}

export function getDemoFluxoFinanceiro(dateFrom: string, dateTo: string) {
  return buscarDemo<FluxoDia[]>("/demo/fluxo-financeiro", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}

export function getDemoAbcPareto(dateFrom: string, dateTo: string) {
  return buscarDemo<AbcLinha[]>("/demo/abc", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}

export function getDemoRfmScores(dateFrom: string, dateTo: string) {
  return buscarDemo<RfmLinha[]>("/demo/rfm", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}

export function getDemoCohortProduto(dateFrom: string, dateTo: string) {
  return buscarDemo<CohortLinha[]>("/demo/cohort", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}
