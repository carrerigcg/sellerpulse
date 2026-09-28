"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  desconectar,
  iniciarConexao,
  sincronizar,
  statusSincronizacao,
  type StatusJob,
  type StatusSync,
} from "@/lib/ml";

/**
 * Tela de conexão com o Mercado Livre: conectar, acompanhar o progresso da
 * sincronização (inicial ou incremental) e desconectar.
 *
 * Fica sob app/dashboard/ de propósito — herda o guard de sessão do layout
 * do dashboard em vez de duplicar a checagem de usuário aqui.
 */

const MENSAGENS_ERRO: Record<string, string> = {
  recusado: "Você cancelou a autorização no Mercado Livre.",
  state: "A autorização expirou. Tente conectar de novo.",
  troca: "O Mercado Livre recusou a autorização. Tente de novo.",
  perfil: "Conectamos, mas não conseguimos ler seus dados de vendedor.",
  "ja-conectada": "Essa conta do Mercado Livre já está ligada a outro cadastro.",
};

export default function ConectarPage() {
  // useSearchParams exige um boundary de Suspense no build de produção
  // (senão `next build` falha) — o conteúdo real fica num componente filho
  // pra que este boundary funcione.
  return (
    <Suspense fallback={<p className="mt-8 text-sm text-muted">Carregando…</p>}>
      <ConectarConteudo />
    </Suspense>
  );
}

function ConectarConteudo() {
  const searchParams = useSearchParams();
  const erroParam = searchParams.get("erro");
  const conectadoParam = searchParams.get("conectado");

  const [status, setStatus] = useState<StatusSync | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [conectando, setConectando] = useState(false);
  const [sincronizando, setSincronizando] = useState(false);
  const [desconectando, setDesconectando] = useState(false);

  const carregarStatus = useCallback(async () => {
    try {
      const dados = await statusSincronizacao();
      setStatus(dados);
      setErro(null);
    } catch {
      setErro(
        "Não foi possível carregar o status da conexão. O backend está no ar?",
      );
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    // Função nomeada declarada dentro do efeito, no padrão que os próprios
    // docs do React recomendam para fetch em efeito — chamar `carregarStatus`
    // (useCallback) direto aqui faz o lint (`react-hooks/set-state-in-effect`)
    // reclamar de setState síncrono dentro do efeito.
    async function carregarNaMontagem() {
      await carregarStatus();
    }
    void carregarNaMontagem();
  }, [carregarStatus]);

  // Faz polling enquanto houver job em andamento, e para assim que ele sair
  // de queued/running. Deixar o intervalo rodando numa aba esquecida
  // acordaria a instância grátis do Render a cada 3s, para sempre, de graça.
  useEffect(() => {
    const statusJob = status?.job?.status;
    if (statusJob !== "queued" && statusJob !== "running") return;

    const intervalo = setInterval(() => {
      void carregarStatus();
    }, 3000);
    return () => clearInterval(intervalo);
  }, [status?.job?.status, carregarStatus]);

  async function conectar() {
    setConectando(true);
    try {
      const url = await iniciarConexao();
      window.location.href = url;
    } catch {
      setErro("Não foi possível iniciar a conexão com o Mercado Livre.");
      setConectando(false);
    }
  }

  async function sincronizarAgora() {
    setSincronizando(true);
    try {
      await sincronizar("manual");
      await carregarStatus();
    } catch {
      setErro("Não foi possível sincronizar agora.");
    } finally {
      setSincronizando(false);
    }
  }

  async function desconectarConta() {
    setDesconectando(true);
    try {
      await desconectar();
      await carregarStatus();
    } catch {
      setErro("Não foi possível desconectar.");
    } finally {
      setDesconectando(false);
    }
  }

  const job = status?.job ?? null;
  const jobAtivo = job !== null && (job.status === "queued" || job.status === "running");

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">
        Conectar Mercado Livre
      </h1>
      <p className="mt-1 text-sm text-muted">
        Ligue sua conta do Mercado Livre para importar seus pedidos.
      </p>

      {erroParam && MENSAGENS_ERRO[erroParam] && (
        <p className="mt-6 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {MENSAGENS_ERRO[erroParam]}
        </p>
      )}
      {conectadoParam === "1" && (
        <p className="mt-6 rounded-lg bg-positive/10 px-4 py-3 text-sm text-positive">
          Conta conectada com sucesso.
        </p>
      )}
      {erro && (
        <p className="mt-6 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      )}

      {carregando ? (
        <p className="mt-8 text-sm text-muted">Carregando status da conexão…</p>
      ) : !status?.conectado ? (
        <section className="mt-8 rounded-xl border border-line p-5">
          <h2 className="text-sm font-semibold">Nenhuma conta conectada</h2>
          <p className="mt-2 text-sm text-muted">
            Ao conectar, importamos os últimos 6 meses de pedidos do Mercado
            Livre. Isso pode levar alguns minutos.
          </p>
          <button
            type="button"
            onClick={conectar}
            disabled={conectando}
            className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          >
            {conectando ? "Redirecionando…" : "Conectar Mercado Livre"}
          </button>
        </section>
      ) : (
        <section className="mt-8 rounded-xl border border-line p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold">
                Conectado como {status.apelido ?? "vendedor"}
              </h2>
              <p className="mt-1 text-xs text-muted">
                Última sincronização:{" "}
                {status.ultima_sincronizacao
                  ? new Date(status.ultima_sincronizacao).toLocaleString("pt-BR")
                  : "Ainda não sincronizado"}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={sincronizarAgora}
                disabled={sincronizando || jobAtivo}
                className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
              >
                {sincronizando ? "Enviando…" : "Sincronizar agora"}
              </button>
              <button
                type="button"
                onClick={desconectarConta}
                disabled={desconectando}
                className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium transition hover:bg-surface disabled:opacity-50"
              >
                {desconectando ? "Desconectando…" : "Desconectar"}
              </button>
            </div>
          </div>

          {status.historico_completo === false && !jobAtivo && (
            <p className="mt-4 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
              A importação inicial não terminou. Os números do dashboard cobrem
              menos que os últimos 6 meses.
            </p>
          )}

          {job && <ProgressoJob job={job} />}
        </section>
      )}
    </div>
  );
}

function ProgressoJob({ job }: { job: StatusJob }) {
  // total === 0 significa "fase sem contagem conhecida ainda" — uma barra
  // parada em 0% pareceria travada, então mostramos uma barra cheia
  // pulsando em vez de um número.
  const pct =
    job.total > 0 ? Math.min(100, Math.round((job.processados / job.total) * 100)) : null;
  const rotuloFase = job.kind === "backfill" ? "Importação inicial" : "Sincronização";

  return (
    <div className="mt-4 border-t border-line pt-4">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          {rotuloFase}
          {job.fase ? ` — ${job.fase}` : ""}
        </span>
        {pct !== null && <span className="tabular">{pct}%</span>}
      </div>

      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface">
        {pct === null ? (
          <div className="h-full w-full animate-pulse rounded-full bg-accent/50" />
        ) : (
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>

      {job.status === "failed" && (
        <p className="mt-3 rounded-lg bg-negative/10 px-3 py-2 text-xs text-negative">
          {job.erro ?? "A sincronização falhou."}
        </p>
      )}
      {job.status === "done" && (
        <p className="mt-3 text-xs text-positive">Sincronização concluída.</p>
      )}

      {job.warnings.length > 0 && (
        <details className="mt-3 text-xs text-muted">
          <summary className="cursor-pointer">
            {job.warnings.length} aviso{job.warnings.length > 1 ? "s" : ""}
          </summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {job.warnings.slice(0, 10).map((aviso, i) => (
              <li key={i}>{aviso}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
