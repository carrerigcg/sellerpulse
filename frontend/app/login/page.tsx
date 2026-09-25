"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  Alert,
  AuthShell,
  Divider,
  GoogleButton,
  PageTitle,
  PrimaryButton,
  TextField,
} from "@/components/auth-ui";
import { mensagemDeLogin, registraErroDeAuth } from "@/lib/auth-errors";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const router = useRouter();

  async function entrarComSenha(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password: senha,
      });
      if (error) {
        registraErroDeAuth("login", error);
        setErro(mensagemDeLogin(error));
        setCarregando(false);
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } catch (e) {
      // signInWithPassword normalmente devolve o erro em vez de lançar, mas
      // uma falha na criação do cliente (env var ausente, por exemplo) estoura
      // aqui — e sem este catch a tela ficaria travada em "Entrando...".
      registraErroDeAuth("login:excecao", e);
      setErro(mensagemDeLogin(e instanceof Error ? e : new Error(String(e))));
      setCarregando(false);
    }
  }

  async function entrarComGoogle() {
    setErro(null);
    setCarregando(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/dashboard` },
    });
    if (error) {
      registraErroDeAuth("login:google", error);
      setErro("Não foi possível conectar com o Google. Tente de novo.");
      setCarregando(false);
    }
  }

  return (
    <AuthShell panel={<PainelLogin />}>
      <PageTitle
        title="Entrar"
        subtitle="Acesse os dados da sua conta do Mercado Livre."
      />

      <form onSubmit={entrarComSenha} className="mt-8 space-y-4">
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
        />
        <TextField
          id="senha"
          label="Senha"
          type="password"
          autoComplete="current-password"
          value={senha}
          onChange={setSenha}
        />
        {erro && <Alert tone="erro">{erro}</Alert>}
        <PrimaryButton disabled={carregando}>
          {carregando ? "Entrando..." : "Entrar"}
        </PrimaryButton>
      </form>

      <Divider label="ou" />

      <GoogleButton onClick={entrarComGoogle} disabled={carregando}>
        Continuar com Google
      </GoogleButton>

      <p className="mt-8 text-sm text-muted">
        Ainda não tem conta?{" "}
        <Link href="/signup" className="font-medium text-accent hover:underline">
          Criar conta
        </Link>
      </p>
    </AuthShell>
  );
}

/** Prévia do tipo de cartão que o usuário vai ver no dashboard. */
function PainelLogin() {
  return (
    <>
      <h2 className="text-3xl font-semibold leading-tight tracking-tight">
        Seus números do Mercado Livre,{" "}
        <span className="text-accent">sem planilha.</span>
      </h2>
      <p className="mt-4 text-muted">
        Receita, custos e lucro por dia. Curva ABC dos produtos. Segmentação dos
        compradores. Tudo calculado a partir dos seus pedidos reais.
      </p>

      <div className="mt-10 rounded-xl border border-line bg-bg p-5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            Receita bruta
          </span>
          <span className="rounded-full bg-positive/10 px-2 py-0.5 text-xs font-medium text-positive">
            +12,4%
          </span>
        </div>
        <p className="tabular mt-2 text-3xl font-semibold">R$ 358.074</p>
        <p className="mt-1 text-xs text-muted">últimos 90 dias</p>

        {/* A última barra em amarelo marca o período corrente. Amarelo como
            preenchimento sólido é uso legível; em texto ou traço fino não
            atingiria contraste. */}
        <div className="mt-5 flex h-16 items-end gap-1.5">
          {[38, 52, 45, 61, 49, 70, 58, 76].map((altura, i, arr) => (
            <div
              key={i}
              style={{ height: `${altura}%` }}
              className={`flex-1 rounded-sm ${
                i === arr.length - 1 ? "bg-highlight" : "bg-accent/25"
              }`}
            />
          ))}
        </div>
      </div>
    </>
  );
}
