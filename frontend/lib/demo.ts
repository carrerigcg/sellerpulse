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
    // Sem Authorization — a demo não tem sessão.
    //
    // Uma hora de cache, e a razão não é economia: o backend roda no plano
    // gratuito do Render, que hiberna após ~15 min sem tráfego. Sem cache,
    // o primeiro visitante depois de uma pausa esperava ~25s o serviço
    // acordar antes de ver qualquer coisa — justamente o visitante que
    // chega frio, pelo link. Uma hora cobre a janela de hibernação, então
    // a demo responde na hora e nem acorda o Render.
    //
    // Cachear aqui é seguro porque a resposta é a MESMA pra todo mundo: um
    // seller sintético e fixo, sem sessão e sem `seller_id` de ninguém. Em
    // `lib/api.ts` o `no-store` continua, e tem que continuar — lá a
    // resposta é de um vendedor específico, e servir a de um pro outro
    // mostraria o faturamento alheio.
    //
    // Erro transitório não envenena o cache: o Next só grava resposta com
    // status 200 (ver `res.status === 200 &&` em
    // `next/dist/server/lib/patch-fetch.js`), então a página de "acordando"
    // do Render passa direto e a próxima visita tenta de novo.
    next: { revalidate: 3600 },
  });

  if (!resposta.ok) {
    throw new ApiError(resposta.status, `Falha ao buscar ${caminho}`);
  }

  // Um 200 que não é JSON é resposta de intermediário (página de espera,
  // portal de rede), não do nosso backend. Falhar aqui dá erro legível em
  // vez de um SyntaxError no meio do `.json()`.
  const tipo = resposta.headers.get("content-type") ?? "";
  if (!tipo.includes("application/json")) {
    throw new ApiError(resposta.status, `Resposta não-JSON em ${caminho}`);
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

/**
 * Janela padrão da demonstração: os últimos 90 dias, igual às telas
 * autenticadas.
 *
 * Isto já foi fixo em julho/2026, e a cicatriz vale registrar. O vendedor da
 * demo é sintético e seus pedidos paravam em 31/07/2026, então uma janela
 * ancorada em `hoje` escorregava para fora do dado conforme o tempo passava.
 * Em 01/10 os últimos 90 dias pegavam só julho, enquanto o "período anterior"
 * pegava abril a julho inteiros — e os três cartões da Executive exibiam
 * −54,7%. A conta estava certa; a leitura era de um negócio em colapso, na
 * única tela feita para atrair cliente.
 *
 * Fixar a janela tratava o sintoma. A causa foi resolvida no backend: o
 * seller de demonstração é regenerado no boot sempre que sua venda mais
 * recente passa de 7 dias, com 26 semanas de histórico terminando em hoje
 * (`backend/demo_refresh.py`). Com o dado sempre corrente, a janela relativa
 * volta a ser a certa — e passa a ser a MESMA do dashboard, que é o ponto:
 * a vitrine mostra o produto, não uma versão especial dele.
 *
 * Continua vivendo aqui, e não repetida nas três páginas, porque era assim
 * que estava antes e três cópias divergem.
 */
export function periodoPadraoDaDemo() {
  const hoje = new Date();
  const noventaDiasAtras = new Date(hoje);
  noventaDiasAtras.setDate(hoje.getDate() - 90);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { de: fmt(noventaDiasAtras), ate: fmt(hoje) };
}
