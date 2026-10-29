import { createClient } from "@/lib/supabase/client";

/**
 * Chamadas de conexão com o Mercado Livre, para uso em Client Components.
 *
 * Diferente de `lib/api.ts` (Server Components, token vindo do cookie no
 * servidor), aqui o token vem do cliente do browser — a tela de conectar é
 * interativa: botão, polling do progresso, desconectar.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL!;

export type StatusJob = {
  id: number;
  kind: "backfill" | "delta" | "visitas" | "frete";
  status: "queued" | "running" | "done" | "failed";
  fase: string | null;
  processados: number;
  total: number;
  erro: string | null;
  warnings: string[];
};

export type StatusSync = {
  conectado: boolean;
  apelido: string | null;
  ultima_sincronizacao: string | null;
  historico_completo: boolean;
  /** O plano deixa sincronizar fora da diária agendada? */
  sincroniza_sob_demanda: boolean;
  job: StatusJob | null;
};

async function autorizacao(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  if (!session) throw new Error("Sem sessão");
  return { Authorization: `Bearer ${session.access_token}` };
}

export async function iniciarConexao(): Promise<string> {
  const resposta = await fetch(`${BASE}/ml/connect/start`, {
    method: "POST",
    headers: await autorizacao(),
  });
  if (!resposta.ok) throw new Error("Não foi possível iniciar a conexão");
  return (await resposta.json()).url as string;
}

export async function statusSincronizacao(): Promise<StatusSync> {
  const resposta = await fetch(`${BASE}/ml/sync/status`, {
    headers: await autorizacao(),
    cache: "no-store",
  });
  if (!resposta.ok) throw new Error("Não foi possível carregar o status");
  return resposta.json();
}

export async function sincronizar(motivo: "manual" | "login") {
  const resposta = await fetch(`${BASE}/ml/sync?motivo=${motivo}`, {
    method: "POST",
    headers: await autorizacao(),
  });
  // 409 = sem conta conectada. É estado esperado, não falha.
  if (!resposta.ok && resposta.status !== 409) {
    throw new Error("Não foi possível sincronizar");
  }
  return resposta.json();
}

export async function desconectar(): Promise<void> {
  const resposta = await fetch(`${BASE}/ml/connection`, {
    method: "DELETE",
    headers: await autorizacao(),
  });
  if (!resposta.ok) throw new Error("Não foi possível desconectar");
}

/** Registra o aceite da versão dos termos que a tela mostrou. */
export async function aceitarTermos(versao: string): Promise<void> {
  const resposta = await fetch(`${BASE}/conta/aceite`, {
    method: "POST",
    headers: { ...(await autorizacao()), "Content-Type": "application/json" },
    body: JSON.stringify({ versao }),
  });
  if (resposta.status === 409) {
    throw new Error("Os termos mudaram enquanto a página estava aberta. Recarregue e leia de novo.");
  }
  if (!resposta.ok) throw new Error("Não foi possível registrar o aceite. Tente de novo.");
}
