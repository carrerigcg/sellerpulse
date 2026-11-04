"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert, AuthShell, PageTitle, PrimaryButton, TextField } from "@/components/auth-ui";
import { registraErroDeAuth } from "@/lib/auth-errors";
import { linkDeEmail } from "@/lib/contato";
import { codigoValido, faltaOCodigo } from "@/lib/duas-etapas";
import {
  MIN_SENHA,
  mensagemDaSenhaNova,
  motivoDoLinkInvalido,
  tokenDeRecuperacao,
} from "@/lib/recuperacao";
import { createClient } from "@/lib/supabase/client";

type Etapa =
  | { nome: "conferindo" }
  | { nome: "link-invalido"; motivo: string }
  | { nome: "codigo"; fator: string }
  | { nome: "senha" };

const FALHA_INESPERADA = "Algo deu errado do nosso lado. Tente de novo em instantes.";

/** O que o leitor de tela ouve quando a etapa muda. */
function anuncioDa(etapa: Etapa): string {
  if (etapa.nome === "link-invalido") return etapa.motivo;
  if (etapa.nome === "codigo") return "Confirme o código do app autenticador.";
  if (etapa.nome === "senha") return "Link conferido. Crie uma senha nova.";
  return "";
}

/**
 * Criar a senha nova, a partir do link do e-mail.
 *
 * Fora do matcher do `proxy.ts`: quem chega aqui ainda não tem sessão. Só o
 * código do link abre a troca; uma sessão já aberta não basta, senão alguém
 * num computador destravado trocaria a senha do dono (spec, decisão 4).
 */
export default function RedefinirSenhaPage() {
  const router = useRouter();
  const [etapa, setEtapa] = useState<Etapa>({ nome: "conferindo" });
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const conteudo = useRef<HTMLDivElement>(null);
  // O código do link vale uma vez, e o efeito roda duas vezes em
  // desenvolvimento: a segunda conferência daria "link já usado".
  const conferiu = useRef(false);

  useEffect(() => {
    if (conferiu.current) return;
    conferiu.current = true;
    const token = tokenDeRecuperacao(window.location.search);
    // O código sai da barra de endereço: não fica no histórico nem vaza
    // para outro site pelo Referer.
    window.history.replaceState(null, "", window.location.pathname);
    (async () => {
      if (!token) {
        setEtapa({
          nome: "link-invalido",
          motivo: "Este endereço não tem um link de recuperação válido.",
        });
        return;
      }
      try {
        const supabase = createClient();
        const { error } = await supabase.auth.verifyOtp({ token_hash: token, type: "recovery" });
        if (error) {
          registraErroDeAuth("recuperacao:link", error);
          setEtapa({ nome: "link-invalido", motivo: motivoDoLinkInvalido(error) });
          return;
        }
        // Com o app autenticador ativo, o Supabase só troca a senha depois do
        // código: o e-mail sozinho não pode levar a conta.
        const { data: nivel } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
        if (!faltaOCodigo(nivel)) {
          setEtapa({ nome: "senha" });
          return;
        }
        const { data, error: erroFatores } = await supabase.auth.mfa.listFactors();
        const fator = data?.totp.find((f) => f.status === "verified")?.id;
        if (erroFatores || !fator) {
          setEtapa({
            nome: "link-invalido",
            motivo: "Não foi possível preparar a verificação agora. Peça um link novo.",
          });
          return;
        }
        setEtapa({ nome: "codigo", fator });
      } catch (e) {
        registraErroDeAuth("recuperacao:link:excecao", e);
        setEtapa({ nome: "link-invalido", motivo: FALHA_INESPERADA });
      }
    })();
  }, []);

  // A etapa nova desmonta o botão que tinha o foco: leva o teclado ao campo
  // da etapa nova, ou ao título quando não há campo. O efeito roda depois de
  // a etapa nova estar no DOM.
  useEffect(() => {
    if (etapa.nome === "conferindo") return;
    const alvo =
      conteudo.current?.querySelector<HTMLElement>("input") ??
      conteudo.current?.querySelector<HTMLElement>("h1");
    if (alvo?.tagName === "H1") alvo.tabIndex = -1;
    alvo?.focus();
  }, [etapa.nome]);

  async function confirmarCodigo(e: React.FormEvent) {
    e.preventDefault();
    if (etapa.nome !== "codigo") return;
    setErro(null);
    const digitos = codigoValido(codigo);
    if (!digitos) {
      setErro("O código tem 6 números. Confira no app e tente de novo.");
      return;
    }
    setCarregando(true);
    try {
      const { error } = await createClient().auth.mfa.challengeAndVerify({
        factorId: etapa.fator,
        code: digitos,
      });
      if (error) {
        registraErroDeAuth("recuperacao:codigo", error);
        setErro("Código incorreto ou vencido. Use o código que está no app agora.");
      } else {
        setEtapa({ nome: "senha" });
      }
    } catch (e) {
      registraErroDeAuth("recuperacao:codigo:excecao", e);
      setErro(FALHA_INESPERADA);
    }
    setCarregando(false);
  }

  async function salvarSenha(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    if (senha.length < MIN_SENHA) {
      setErro(`A senha precisa ter pelo menos ${MIN_SENHA} caracteres.`);
      return;
    }
    setCarregando(true);
    try {
      const { error } = await createClient().auth.updateUser({ password: senha });
      if (!error) {
        router.push("/dashboard");
        router.refresh();
        return;
      }
      registraErroDeAuth("recuperacao:senha", error);
      setErro(mensagemDaSenhaNova(error));
    } catch (e) {
      registraErroDeAuth("recuperacao:senha:excecao", e);
      setErro(FALHA_INESPERADA);
    }
    setCarregando(false);
  }

  return (
    <AuthShell panel={<PainelRedefinir />}>
      <p role="status" className="sr-only">
        {anuncioDa(etapa)}
      </p>
      <div ref={conteudo}>
        {etapa.nome === "conferindo" && (
          <PageTitle title="Conferindo o link..." subtitle="Só um instante." />
        )}

        {etapa.nome === "link-invalido" && (
          <>
            <PageTitle title="Este link não vale" subtitle={etapa.motivo} />
            <p className="mt-8 text-sm">
              <Link href="/esqueci-senha" className="font-medium text-accent hover:underline">
                Pedir um link novo
              </Link>
            </p>
          </>
        )}

        {etapa.nome === "codigo" && (
          <>
            <PageTitle
              title="Confirme que é você"
              subtitle="Sua conta usa o app autenticador. Digite o código de 6 números antes de criar a senha nova."
            />
            <form onSubmit={confirmarCodigo} className="mt-8 space-y-4">
              <TextField
                id="codigo"
                label="Código"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={codigo}
                onChange={setCodigo}
              />
              {erro && <Alert tone="erro">{erro}</Alert>}
              <PrimaryButton disabled={carregando}>
                {carregando ? "Confirmando..." : "Confirmar"}
              </PrimaryButton>
            </form>
            <p className="mt-8 text-sm text-muted">
              Perdeu o acesso ao app?{" "}
              <a
                href={linkDeEmail("Perdi o acesso ao app autenticador")}
                className="font-medium text-accent hover:underline"
              >
                Fale com a gente
              </a>
              .
            </p>
          </>
        )}

        {etapa.nome === "senha" && (
          <>
            <PageTitle
              title="Crie uma senha nova"
              subtitle="Depois de salvar, você entra direto no painel."
            />
            <form onSubmit={salvarSenha} className="mt-8 space-y-4">
              <TextField
                id="senha"
                label="Senha nova"
                type="password"
                autoComplete="new-password"
                value={senha}
                onChange={setSenha}
                minLength={MIN_SENHA}
                hint={`Mínimo de ${MIN_SENHA} caracteres.`}
              />
              {erro && <Alert tone="erro">{erro}</Alert>}
              <PrimaryButton disabled={carregando}>
                {carregando ? "Salvando..." : "Salvar a senha nova"}
              </PrimaryButton>
            </form>
          </>
        )}
      </div>
    </AuthShell>
  );
}

function PainelRedefinir() {
  return (
    <>
      <h2 className="text-3xl font-semibold leading-tight tracking-tight">
        Senha nova, <span className="text-accent">mesma conta.</span>
      </h2>
      <p className="mt-4 text-muted">
        Seus pedidos, custos e a conexão com o Mercado Livre continuam como estavam.
      </p>
    </>
  );
}
