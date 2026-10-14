/**
 * Escrita do custo de produto, a partir do navegador.
 *
 * Mora fora de `lib/api.ts` porque aquele arquivo lê a sessão pelo cliente de
 * SERVIDOR (`lib/supabase/server.ts`) e só funciona em Server Component. A
 * tabela de custos salva ao sair do campo, num Client Component, e precisa do
 * cliente de browser.
 *
 * Não existe função de leitura aqui: a lista vem do Server Component da
 * página, como todo o resto do dashboard.
 */

import { createClient } from "@/lib/supabase/client";

const BASE = process.env.NEXT_PUBLIC_API_URL!;

async function autorizacao(): Promise<string> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Sua sessão expirou. Entre de novo para salvar.");
  return `Bearer ${session.access_token}`;
}

/**
 * `encodeURIComponent` no SKU, sempre.
 *
 * O `item_id` do Mercado Livre é alfanumérico na prática, mas ele entra aqui
 * como segmento de caminho a partir de dado que veio do banco. Interpolar sem
 * escapar é como se monta uma URL que aponta para outro recurso.
 */
function url(sku: string): string {
  return `${BASE}/custos/${encodeURIComponent(sku)}`;
}

async function falha(resposta: Response): Promise<never> {
  if (resposta.status === 401) throw new Error("Sua sessão expirou. Entre de novo.");
  if (resposta.status === 404) throw new Error("Produto não encontrado na sua conta.");
  if (resposta.status === 422) throw new Error("Valor inválido.");
  throw new Error("Não foi possível salvar agora.");
}

/** Grava o custo com vigência a partir de hoje. */
export async function salvaCusto(sku: string, custoUnitario: number): Promise<void> {
  const resposta = await fetch(url(sku), {
    method: "PUT",
    headers: { Authorization: await autorizacao(), "Content-Type": "application/json" },
    body: JSON.stringify({ custo_unitario: custoUnitario }),
  });
  if (!resposta.ok) await falha(resposta);
}

/**
 * Remove a vigência de hoje — o que o campo esvaziado significa.
 *
 * Não apaga histórico: o custo de ontem continua valendo para os pedidos de
 * ontem. Esvaziar o campo desfaz o que foi digitado hoje, nada além.
 */
export async function removeCusto(sku: string): Promise<void> {
  const resposta = await fetch(url(sku), {
    method: "DELETE",
    headers: { Authorization: await autorizacao() },
  });
  if (!resposta.ok) await falha(resposta);
}
