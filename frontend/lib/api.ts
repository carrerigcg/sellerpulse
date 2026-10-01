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
  /**
   * receita_bruta − taxas_ml − frete. Não existe mais um `custo_estimado`
   * (55% da receita chutados) nem o `liquido` que saía dele — ver o
   * comentário no topo de `src/metrics.py`.
   */
  margem_contribuicao: number;
};

export type ClasseAbc = "A" | "B" | "C";

export type AbcLinha = {
  sku: string;
  titulo: string;
  receita: number;
  receita_pct: number;
  receita_acumulada_pct: number;
  classe: ClasseAbc;
};

/** Rótulo bruto de `src/segmentation.py` (Fase 2, congelado) — não traduzir aqui. */
export type SegmentoRfm =
  | "Champions"
  | "Loyal"
  | "At Risk"
  | "New"
  | "Hibernating"
  | "Others";

export type RfmLinha = {
  buyer_id: number;
  recency_dias: number;
  frequency: number;
  monetary: number;
  r_score: number;
  f_score: number;
  m_score: number;
  segmento: SegmentoRfm;
};

/**
 * Linha do pivot de cohort: `mes_lancamento` fixo + uma chave por mês
 * corrente ("YYYY-MM"), dinâmica conforme a janela consultada. Onde o mês
 * corrente é anterior ao de lançamento (produto não existia ainda), o
 * backend manda `null` (era `NaN` no pandas) — diferente de um mês com
 * receita zero, que vem como `0`. Ver `cohort_produto` em
 * `backend/analytics/segmentation_pg.py`.
 */
export type CohortLinha = {
  mes_lancamento: string;
  [mesCorrente: string]: string | number | null;
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

export function getAbcPareto(dateFrom: string, dateTo: string) {
  return buscar<AbcLinha[]>("/segmentation/abc", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}

export function getRfmScores(dateFrom: string, dateTo: string) {
  return buscar<RfmLinha[]>("/segmentation/rfm", {
    date_from: dateFrom,
    date_to: dateTo,
  });
}

export function getCohortProduto(dateFrom: string, dateTo: string) {
  return buscar<CohortLinha[]>("/segmentation/cohort", {
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
