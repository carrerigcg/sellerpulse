import { createClient } from "@/lib/supabase/server";

/**
 * Cliente da API do SellerPulse (FastAPI), para uso em Server Components.
 *
 * O token vem da sessão do Supabase e vai no header Authorization. Quem
 * valida a assinatura é o backend (`backend/auth.py`), e é ele também que
 * resolve o `seller_id` a partir do `sub` do token — o frontend nunca envia
 * seller_id, justamente pra que um cliente malicioso não possa pedir os
 * dados de outro vendedor.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL!;

export type FluxoDia = {
  date: string;
  receita_bruta: number;
  taxas_ml: number;
  frete: number;
  custo_estimado: number;
  liquido: number;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

async function buscar<T>(caminho: string, params: Record<string, string>): Promise<T> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) throw new ApiError(401, "Sem sessão");

  const query = new URLSearchParams(params).toString();
  const resposta = await fetch(`${BASE}${caminho}?${query}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
    // Dado de vendedor muda a cada ingestão e é específico do usuário —
    // cachear no servidor arriscaria servir número de um seller pra outro.
    cache: "no-store",
  });

  if (!resposta.ok) {
    throw new ApiError(resposta.status, `Falha ao buscar ${caminho}`);
  }
  return resposta.json();
}

export function getFluxoFinanceiro(dateFrom: string, dateTo: string) {
  return buscar<FluxoDia[]>("/metrics/fluxo-financeiro", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}

/** Janela imediatamente anterior, de mesma duração — base para as variações. */
export function janelaAnterior(dateFrom: string, dateTo: string): [string, string] {
  const de = new Date(`${dateFrom}T00:00:00Z`);
  const ate = new Date(`${dateTo}T00:00:00Z`);
  const duracao = ate.getTime() - de.getTime();
  const anteriorDe = new Date(de.getTime() - duracao);
  return [anteriorDe.toISOString().slice(0, 10), dateFrom];
}
