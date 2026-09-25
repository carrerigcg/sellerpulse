"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Wordmark } from "@/components/brand";
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
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password: senha,
    });
    if (error) {
      // Mensagem genérica de propósito: distinguir "email não existe" de
      // "senha errada" entrega ao atacante quais emails estão cadastrados.
      setErro("Email ou senha incorretos.");
      setCarregando(false);
      return;
    }
    router.push("/dashboard");
    router.refresh();
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
      setErro("Não foi possível conectar com o Google. Tente de novo.");
      setCarregando(false);
    }
  }

  return (
    <main className="flex min-h-screen">
      {/* ---------- formulário ---------- */}
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <Link href="/" className="inline-block">
            <Wordmark className="text-xl" />
          </Link>

          <h1 className="mt-10 text-3xl font-semibold tracking-tight">Entrar</h1>
          <p className="mt-2 text-sm text-muted">
            Acesse os dados da sua conta do Mercado Livre.
          </p>

          <form onSubmit={entrarComSenha} className="mt-8 space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </div>

            <div>
              <label htmlFor="senha" className="block text-sm font-medium">
                Senha
              </label>
              <input
                id="senha"
                type="password"
                autoComplete="current-password"
                required
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </div>

            {erro && (
              <p
                role="alert"
                className="rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative"
              >
                {erro}
              </p>
            )}

            <button
              type="submit"
              disabled={carregando}
              className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-60"
            >
              {carregando ? "Entrando..." : "Entrar"}
            </button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-line" />
            <span className="text-xs text-muted">ou</span>
            <span className="h-px flex-1 bg-line" />
          </div>

          <button
            type="button"
            onClick={entrarComGoogle}
            disabled={carregando}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-4 py-2.5 text-sm font-medium transition hover:bg-surface disabled:opacity-60"
          >
            <GoogleIcon />
            Continuar com Google
          </button>

          <p className="mt-8 text-sm text-muted">
            Ainda não tem conta?{" "}
            <Link href="/signup" className="font-medium text-accent hover:underline">
              Criar conta
            </Link>
          </p>
        </div>
      </div>

      {/* ---------- painel lateral ----------
          Fundo em laranja MUITO diluído (--sp-accent-soft) em vez de laranja
          cheio: metade da tela preenchida com a cor saturada brigaria com o
          pedido de "sutil". O laranja forte aparece só em pontos pequenos —
          a marca, o traço do gráfico. O amarelo entra uma vez, como
          preenchimento de barra, nunca como texto. */}
      <aside className="hidden w-1/2 flex-col justify-center bg-accent-soft px-16 lg:flex">
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            Seus números do Mercado Livre,{" "}
            <span className="text-accent">sem planilha.</span>
          </h2>
          <p className="mt-4 text-muted">
            Receita, custos e lucro por dia. Curva ABC dos produtos. Segmentação
            dos compradores. Tudo calculado a partir dos seus pedidos reais.
          </p>

          <PreviaKpi />
        </div>
      </aside>
    </main>
  );
}

/** Prévia do tipo de cartão que o usuário vai ver no dashboard. */
function PreviaKpi() {
  return (
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

      {/* Barras: a última em amarelo para destacar o período corrente.
          Amarelo aqui é preenchimento de forma sólida — uso legível. */}
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
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.65l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9l3.66-2.84z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 1.46 14.97.5 12 .5A11 11 0 0 0 2.18 7.05l3.66 2.84c.87-2.6 3.3-4.14 6.16-4.14z"
      />
    </svg>
  );
}
