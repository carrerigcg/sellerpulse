"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, AuthShell, PageTitle } from "@/components/auth-ui";
import {
  destinoDoRetorno,
  nomeDoCliente,
  type SituacaoDoPlano,
  situacaoDoPlano,
} from "@/lib/conexoes-ia";
import { recursosDoLogin } from "@/lib/ml";
import { createClient } from "@/lib/supabase/client";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "invalido" }
  | {
      tipo: "pronto";
      id: string;
      cliente: string;
      email: string;
      retorno: { host: string | null; conhecido: boolean };
      plano: SituacaoDoPlano;
    };

const BOTAO =
  "inline-flex min-h-11 w-full items-center justify-center rounded-lg px-4 text-sm font-medium disabled:opacity-60";

/**
 * Autorizar um cliente de IA (o Claude) a ler a loja pelo MCP.
 *
 * O Supabase manda para cá com `?authorization_id=` (Authorization Path
 * configurado no painel dele). O `proxy.ts` exige o login antes e devolve
 * para cá. Spec: docs/specs/2026-11-09-premium-mcp-conta-real-design.md,
 * decisão 14.
 *
 * O nome do cliente quem escolhe é quem o registrou, e o registro é aberto:
 * qualquer um registra um "Claude". Por isso a tela mostra para onde o acesso
 * vai (o endereço de retorno), e avisa quando não é um aplicativo conhecido.
 */
export default function ConsentimentoPage() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [decidindo, setDecidindo] = useState<"autorizar" | "recusar" | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("authorization_id");
    (async () => {
      const supabase = createClient();
      const [detalhes, recursos] = await Promise.all([
        id ? supabase.auth.oauth.getAuthorizationDetails(id) : null,
        recursosDoLogin(),
      ]);
      const data = detalhes?.data;
      if (!id || detalhes?.error || !data) {
        setEstado({ tipo: "invalido" });
        return;
      }
      // Já autorizado antes: o Supabase devolve só para onde voltar.
      if (!("authorization_id" in data)) {
        window.location.href = data.redirect_url;
        return;
      }
      setEstado({
        tipo: "pronto",
        id,
        cliente: nomeDoCliente(data.client?.name),
        email: data.user?.email ?? "",
        retorno: destinoDoRetorno(data.redirect_uri),
        plano: situacaoDoPlano(recursos),
      });
    })().catch(() => setEstado({ tipo: "invalido" }));
  }, []);

  async function decide(autoriza: boolean) {
    if (estado.tipo !== "pronto") return;
    setErro(null);
    setDecidindo(autoriza ? "autorizar" : "recusar");
    const supabase = createClient();
    const { data, error } = autoriza
      ? await supabase.auth.oauth.approveAuthorization(estado.id, { skipBrowserRedirect: true })
      : await supabase.auth.oauth.denyAuthorization(estado.id, { skipBrowserRedirect: true });
    if (error || !data) {
      setDecidindo(null);
      setErro("Não foi possível concluir agora. Volte ao aplicativo e tente conectar de novo.");
      return;
    }
    window.location.href = data.redirect_url;
  }

  return (
    <AuthShell panel={<Painel />}>
      {estado.tipo === "carregando" && (
        <p className="mt-10 text-sm text-muted" role="status">
          Carregando…
        </p>
      )}

      {estado.tipo === "invalido" && (
        <>
          <PageTitle
            title="Link de autorização inválido"
            subtitle="Ele pode ter vencido ou já ter sido usado."
          />
          <p className="mt-6 text-sm">
            Volte ao aplicativo de IA e peça para conectar o SellerPulse de novo.
          </p>
        </>
      )}

      {estado.tipo === "pronto" && (
        <>
          <PageTitle
            title={`Conectar ${estado.cliente}`}
            subtitle="Um aplicativo de IA quer ler os números da sua loja."
          />

          <dl className="mt-6 space-y-2 rounded-lg border border-line p-3 text-sm">
            {estado.email && (
              <div>
                <dt className="text-xs text-muted">Sua conta no SellerPulse</dt>
                <dd className="break-all">{estado.email}</dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-muted">O acesso vai para</dt>
              <dd className="break-all font-medium">
                {estado.retorno.host ?? "endereço desconhecido"}
              </dd>
            </div>
          </dl>

          {!estado.retorno.conhecido && (
            <div className="mt-4">
              <Alert tone="erro">
                Este endereço não é do Claude nem do ChatGPT. Só autorize se foi você quem
                configurou essa conexão. Na dúvida, recuse.
              </Alert>
            </div>
          )}

          {estado.plano === "liberado" && (
            <div className="mt-6 space-y-3 text-sm">
              <p>
                <strong>{estado.cliente}</strong> vai poder consultar o faturamento, a margem,
                os produtos e os clientes das suas contas do Mercado Livre no SellerPulse.
              </p>
              <p>
                Ele só lê: não altera custos, anúncios, nem a sua assinatura. Você desconecta
                quando quiser em{" "}
                <Link href="/dashboard/seguranca" className="font-medium text-accent hover:underline">
                  Conta e segurança
                </Link>
                .
              </p>
            </div>
          )}

          {estado.plano === "fora-do-plano" && (
            <div className="mt-6 space-y-3 text-sm">
              <p>
                A conexão com a IA faz parte do plano <strong>Premium</strong>, e o seu plano
                atual não inclui.
              </p>
              <p>
                <Link
                  href="/dashboard/assinatura"
                  className="font-medium text-accent hover:underline"
                >
                  Ver os planos
                </Link>
              </p>
            </div>
          )}

          {estado.plano === "sem-resposta" && (
            <div className="mt-6 space-y-3 text-sm">
              <p>
                Não foi possível conferir o seu plano agora. O servidor pode estar iniciando:
                espere alguns segundos e recarregue a página.
              </p>
              <button
                type="button"
                onClick={() => window.location.reload()}
                className={`${BOTAO} border border-line hover:bg-surface`}
              >
                Recarregar
              </button>
            </div>
          )}

          {erro && (
            <div className="mt-4">
              <Alert tone="erro">{erro}</Alert>
            </div>
          )}

          {estado.plano !== "sem-resposta" && (
            <div className="mt-8 space-y-3">
              {estado.plano === "liberado" && (
                <button
                  type="button"
                  disabled={decidindo !== null}
                  onClick={() => decide(true)}
                  className={`${BOTAO} bg-accent text-white hover:bg-accent-hover`}
                >
                  {decidindo === "autorizar" ? "Conectando…" : "Autorizar"}
                </button>
              )}
              <button
                type="button"
                disabled={decidindo !== null}
                onClick={() => decide(false)}
                className={`${BOTAO} border border-line hover:bg-surface`}
              >
                {decidindo === "recusar"
                  ? "Recusando…"
                  : estado.plano === "liberado"
                    ? "Recusar"
                    : "Voltar sem conectar"}
              </button>
            </div>
          )}
        </>
      )}
    </AuthShell>
  );
}

function Painel() {
  return (
    <>
      <h2 className="text-2xl font-semibold tracking-tight">Pergunte à IA sobre a sua loja</h2>
      <p className="mt-3 text-sm text-muted">
        Quanto faturou no mês, quais produtos sustentam a loja, quem parou de comprar: o
        assistente responde com os números do SellerPulse, os mesmos do painel.
      </p>
    </>
  );
}
