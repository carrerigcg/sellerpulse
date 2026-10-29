import { cache } from "react";

import type { Cancelamentos } from "@/lib/cancelamentos";
import { comReceitaSemFrete, type FluxoDiaDaApi } from "@/lib/frete";
import type { Acesso } from "@/lib/plano";
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
  /**
   * Frete que o vendedor pagou, só dos envios já buscados no Mercado Livre.
   * Cada envio conta uma vez, no dia do primeiro pedido — um carrinho é um
   * envio para vários pedidos.
   */
  frete: number;
  /**
   * Receita de vendas cujo frete ainda não foi buscado. É o que torna `frete`
   * honesto, do mesmo jeito que `receita_sem_custo` faz com o custo de
   * produto: enquanto for maior que zero, a margem está maior do que a real.
   */
  receita_sem_frete: number;
  /** Custo de produto informado pelo vendedor, na vigência da data do pedido. */
  custo_produtos: number;
  /**
   * Quanto da receita do dia veio de item SEM custo informado.
   *
   * É o que torna `custo_produtos` honesto: sem esta coluna, quem preencheu
   * 3 de 47 produtos veria a margem quase intacta e concluiria que lucra
   * muito.
   */
  receita_sem_custo: number;
  /**
   * receita_bruta − taxas_ml − frete − custo_produtos. Não existe mais um
   * `custo_estimado` (55% da receita chutados) nem o `liquido` que saía dele
   * — ver o comentário no topo de `src/metrics.py`. O custo de produto que
   * entra aqui é informado pelo vendedor, nunca estimado.
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
  /** Custo informado para este produto, somado nas vendas da janela. */
  custo_produtos: number;
  /** Quanto da receita deste produto veio de venda sem custo informado. */
  receita_sem_custo: number;
  /** Unidades vendidas no período. */
  unidades: number;
  /**
   * Unidades vendidas a partir do primeiro dia de visita colhida da loja —
   * o numerador da conversão. O Mercado Livre só entrega 150 dias de visita,
   * e venda de dia sem visita medida inflaria a taxa. Igual a `unidades`
   * sempre que o período começa depois da colheita.
   */
  unidades_com_visita: number;
  /**
   * Visitas ao anúncio no período.
   *
   * `null` = nunca colhido, que é diferente de `0` = colhido e deu zero. A
   * tela mostra "—" no primeiro caso: zero por cento é uma afirmação, e só
   * se pode fazê-la sobre quem tem visita medida.
   */
  visitas: number | null;
  /**
   * `unidades_com_visita` ÷ visitas, em porcentagem. `null` sem visita para dividir.
   *
   * É uma aproximação declarada: um pedido com três unidades do mesmo item é
   * uma visita que converteu, não três. A métrica honesta seria
   * pedidos ÷ visitas; a útil para quem decide estoque é unidades. Por isso
   * a tela rotula "conversão (unidades)".
   */
  conversao: number | null;
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
 * corrente ("YYYY-MM"), dinâmica conforme a janela consultada. O backend
 * manda `null` (era `NaN` no pandas) em dois casos que o pivot não
 * distingue: mês corrente anterior ao de lançamento (produto não existia
 * ainda) e mês em que o cohort não vendeu nada dentro da janela. Mês sem
 * venda vem como `null`, não como `0`. Ver `cohort_produto` em
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
    /**
     * O `detail.codigo` que o backend manda nas recusas de plano
     * (`sem-plano`, `termos-pendentes`, `fora-do-plano`). `null` nos outros
     * erros.
     */
    public codigo: string | null = null,
  ) {
    super(mensagem);
  }
}

/**
 * O plano não cobre o que se pediu — por exemplo o período anterior da
 * comparação, inteiro antes do histórico do Essencial. Quem chama trata como
 * "indisponível no plano", nunca como zero.
 */
export function foraDoPlano(e: unknown): boolean {
  return e instanceof ApiError && e.codigo === "fora-do-plano";
}

/**
 * O que a tela diz quando a carga falha.
 *
 * Cinco telas repetiam este ternário, e uma já tinha divergido: Custos dizia
 * "os produtos". Divergência entre cópias era exatamente o risco previsto, e
 * ele se realizou. `oQue` deixa a variação de Custos explícita na chamada, em
 * vez de escondida numa cópia que ninguém compara com as outras.
 */
export function mensagemDeFalhaAoCarregar(e: unknown, oQue = "os dados"): string {
  return e instanceof ApiError && e.status === 401
    ? "Sua sessão expirou. Entre de novo."
    : `Não foi possível carregar ${oQue}. O backend está no ar?`;
}

async function buscar<T>(caminho: string, params: Record<string, string>): Promise<T> {
  return (await buscarComCabecalhos<T>(caminho, params)).dados;
}

async function buscarComCabecalhos<T>(
  caminho: string,
  params: Record<string, string>,
): Promise<{ dados: T; cabecalhos: Headers }> {
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
    throw new ApiError(resposta.status, `Falha ao buscar ${caminho}`, await codigoDoErro(resposta));
  }
  return { dados: await resposta.json(), cabecalhos: resposta.headers };
}

async function codigoDoErro(resposta: Response): Promise<string | null> {
  try {
    const corpo = await resposta.json();
    return typeof corpo?.detail?.codigo === "string" ? corpo.detail.codigo : null;
  } catch {
    return null;
  }
}

/**
 * O que o vendedor pode acessar. `cache` porque o layout e cada página
 * perguntam a mesma coisa no mesmo render: uma ida ao backend, não várias.
 */
export const getAcesso = cache(() => buscar<Acesso>("/conta/acesso", {}));

export function getCancelamentos(dateFrom: string, dateTo: string) {
  return buscar<Cancelamentos>("/metrics/cancelamentos", { date_from: dateFrom, date_to: dateTo });
}

export function getFluxoFinanceiro(dateFrom: string, dateTo: string) {
  return buscar<FluxoDiaDaApi[]>("/metrics/fluxo-financeiro", {
    date_from: dateFrom,
    date_to: dateTo,
  }).then(comReceitaSemFrete);
}

export function getAbcPareto(dateFrom: string, dateTo: string) {
  return getAbcComCorte(dateFrom, dateTo).then((r) => r.linhas);
}

/**
 * A curva ABC e quantos produtos o plano deixou de fora (`X-Produtos-Ocultos`).
 *
 * No plano sem desempenho dos anúncios, o backend não manda as colunas de
 * visita. Aqui elas viram `null`, "não medido", que é o que todas as telas já
 * sabem mostrar como `—`. Deixá-las `undefined` passaria por `!== null` como
 * se houvesse visita colhida.
 */
export async function getAbcComCorte(
  dateFrom: string,
  dateTo: string,
): Promise<{ linhas: AbcLinha[]; ocultos: number }> {
  const { dados, cabecalhos } = await buscarComCabecalhos<AbcLinha[]>("/segmentation/abc", {
    date_from: dateFrom,
    date_to: dateTo,
  });
  const linhas = dados.map((linha) => ({
    ...linha,
    unidades_com_visita: linha.unidades_com_visita ?? linha.unidades,
    visitas: linha.visitas ?? null,
    conversao: linha.conversao ?? null,
  }));
  return { linhas, ocultos: Number(cabecalhos.get("X-Produtos-Ocultos") ?? 0) };
}

/** Uma linha da tela de Custos: produto vendido na janela + custo vigente hoje. */
export type CustoLinha = {
  sku: string;
  titulo: string;
  classe: ClasseAbc;
  receita: number;
  unidades: number;
  /**
   * `null` = não informado, e isso NÃO é zero.
   *
   * Zero é uma afirmação — "este produto não me custa nada" — e precisa ser
   * digitada. A distinção é a feature inteira: custo ausente não desconta
   * nada e conta como receita descoberta.
   */
  custo_unitario: number | null;
  /** Desde quando o custo acima vale. `null` quando não há custo. */
  vigente_desde: string | null;
};

export function getCustos(dateFrom: string, dateTo: string) {
  return buscar<CustoLinha[]>("/custos", {
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
