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
import { createClient } from "@/lib/supabase/client";

const MIN_SENHA = 6;

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [confirmePorEmail, setConfirmePorEmail] = useState(false);
  const router = useRouter();

  async function criarConta(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    const supabase = createClient();
    const { data, error } = await supabase.auth.signUp({
      email,
      password: senha,
      options: { emailRedirectTo: `${window.location.origin}/login` },
    });

    if (error) {
      setErro(traduzErroDeCadastro(error.message));
      setCarregando(false);
      return;
    }

    // Com confirmação de email ativa (padrão do Supabase), o signUp devolve
    // usuário mas NÃO devolve sessão. Redirecionar pro /dashboard aqui faria
    // o middleware devolver pro /login — o usuário veria um pisca-pisca sem
    // explicação. Então mostramos o estado de "confirme seu email".
    if (!data.session) {
      setConfirmePorEmail(true);
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

  if (confirmePorEmail) {
    return (
      <AuthShell panel={<PainelSignup />}>
        <PageTitle
          title="Confirme seu email"
          subtitle={`Enviamos um link para ${email}.`}
        />
        <p className="mt-6 text-sm text-muted">
          Clique no link para ativar sua conta. Se não encontrar, confira a
          caixa de spam.
        </p>
        <p className="mt-8 text-sm text-muted">
          <Link href="/login" className="font-medium text-accent hover:underline">
            Voltar para o login
          </Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell panel={<PainelSignup />}>
      <PageTitle
        title="Criar conta"
        subtitle="Leva um minuto. Você conecta o Mercado Livre depois."
      />

      <form onSubmit={criarConta} className="mt-8 space-y-4">
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
          autoComplete="new-password"
          minLength={MIN_SENHA}
          value={senha}
          onChange={setSenha}
          hint={`Mínimo de ${MIN_SENHA} caracteres.`}
        />
        {erro && <Alert tone="erro">{erro}</Alert>}
        <PrimaryButton disabled={carregando}>
          {carregando ? "Criando conta..." : "Criar conta"}
        </PrimaryButton>
      </form>

      <Divider label="ou" />

      <GoogleButton onClick={entrarComGoogle} disabled={carregando}>
        Continuar com Google
      </GoogleButton>

      <p className="mt-8 text-sm text-muted">
        Já tem conta?{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          Entrar
        </Link>
      </p>
    </AuthShell>
  );
}

/**
 * Traduz as mensagens do Supabase Auth, que vêm em inglês.
 *
 * Repassar `error.message` direto mostraria textos como
 * `Email address "x@y.dev" is invalid` para um usuário brasileiro. A lista
 * cobre os casos que dão pra acionar pelo formulário; o resto cai num texto
 * genérico — melhor do que vazar jargão do provedor de auth.
 */
function traduzErroDeCadastro(mensagem: string): string {
  const m = mensagem.toLowerCase();
  if (m.includes("already registered") || m.includes("already been registered"))
    return "Esse email já tem conta. Tente entrar.";
  if (m.includes("invalid") && m.includes("email"))
    return "Esse email não parece válido. Confira e tente de novo.";
  if (m.includes("password") && m.includes("should be at least"))
    return `A senha precisa ter pelo menos ${MIN_SENHA} caracteres.`;
  if (m.includes("weak password"))
    return "Senha muito fraca. Use algo mais difícil de adivinhar.";
  if (m.includes("rate limit") || m.includes("too many"))
    return "Muitas tentativas seguidas. Espere um minuto e tente de novo.";
  return "Não foi possível criar a conta. Tente de novo em instantes.";
}

/**
 * Painel do cadastro: lista o que a pessoa ganha, em vez de repetir o cartão
 * de KPI do login. As duas telas compartilham a casca, não o conteúdo — senão
 * navegar entre elas pareceria que a página não mudou.
 */
function PainelSignup() {
  const analises = [
    {
      titulo: "Executive",
      texto: "Receita, custos e lucro líquido por dia, com variação sobre o período anterior.",
    },
    {
      titulo: "Produtos",
      texto: "Ranking por receita, curva ABC de Pareto e cohort por mês de lançamento.",
    },
    {
      titulo: "Clientes",
      texto: "Segmentação RFM dos compradores: quem volta, quem sumiu, quem vale mais.",
    },
  ];

  return (
    <>
      <h2 className="text-3xl font-semibold leading-tight tracking-tight">
        Três análises prontas,{" "}
        <span className="text-accent">a partir dos seus pedidos.</span>
      </h2>
      <p className="mt-4 text-muted">
        Você conecta a conta do Mercado Livre e o SellerPulse calcula o resto.
      </p>

      <ul className="mt-10 space-y-3">
        {analises.map(({ titulo, texto }) => (
          <li
            key={titulo}
            className="rounded-xl border border-line bg-bg p-4 shadow-sm"
          >
            <div className="flex items-center gap-2.5">
              {/* Marcador em amarelo: preenchimento sólido, sem texto em cima. */}
              <span className="h-2 w-2 shrink-0 rounded-full bg-highlight" />
              <span className="text-sm font-semibold">{titulo}</span>
            </div>
            <p className="mt-1.5 pl-[18px] text-sm text-muted">{texto}</p>
          </li>
        ))}
      </ul>
    </>
  );
}
