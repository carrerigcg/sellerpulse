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

import { CABECALHO_DA_CONTA, COOKIE_DA_CONTA, valorDoCookie } from "@/lib/contas";
import { corpoDoCusto } from "@/lib/custo-informado";
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

/** O custo é da conta aberta: sem isto, salvaria na principal com outra conta na tela. */
function cabecalhos(autorizacao: string): Record<string, string> {
  const conta = valorDoCookie(document.cookie, COOKIE_DA_CONTA);
  return { Authorization: autorizacao, ...(conta ? { [CABECALHO_DA_CONTA]: conta } : {}) };
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
  if (resposta.status === 401) {
    // Mesma distinção de `mensagemDeFalhaAoCarregar`: falta o código do app,
    // não a sessão.
    const corpo = await resposta.json().catch(() => null);
    if (corpo?.detail?.codigo === "segundo-fator") {
      throw new Error(
        "Esta sessão ainda não passou pelo código do app autenticador. Saia e entre de novo.",
      );
    }
    throw new Error("Sua sessão expirou. Entre de novo.");
  }
  if (resposta.status === 404) throw new Error("Produto não encontrado na sua conta.");
  if (resposta.status === 422) throw new Error("Valor inválido.");
  throw new Error("Não foi possível salvar agora.");
}

/**
 * Grava o custo com vigência a partir de hoje. Com `retroativo`, ele também
 * cobre as vendas anteriores que estão sem custo — só elas.
 */
export async function salvaCusto(
  sku: string,
  custoUnitario: number,
  retroativo: boolean,
): Promise<void> {
  const resposta = await fetch(url(sku), {
    method: "PUT",
    headers: { ...cabecalhos(await autorizacao()), "Content-Type": "application/json" },
    body: JSON.stringify(corpoDoCusto(custoUnitario, retroativo)),
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
    headers: cabecalhos(await autorizacao()),
  });
  if (!resposta.ok) await falha(resposta);
}
