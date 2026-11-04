"use client";

import Link from "next/link";
import { useState } from "react";

import { Alert, AuthShell, PageTitle, PrimaryButton, TextField } from "@/components/auth-ui";
import { registraErroDeAuth } from "@/lib/auth-errors";
import { linkDeEmail } from "@/lib/contato";
import { type MensagemDoEnvio, mensagemDoEnvio } from "@/lib/recuperacao";
import { createClient } from "@/lib/supabase/client";

/**
 * Pedir o link para criar uma senha nova.
 *
 * O link do e-mail vai para `/redefinir-senha` pelo modelo do e-mail no painel
 * do Supabase (spec, decisão 3), e não por um `redirectTo` daqui.
 */
export default function EsqueciSenhaPage() {
  const [email, setEmail] = useState("");
  const [resposta, setResposta] = useState<MensagemDoEnvio | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setResposta(null);
    setEnviando(true);
    try {
      const { error } = await createClient().auth.resetPasswordForEmail(email.trim());
      if (error) registraErroDeAuth("recuperacao", error);
      setResposta(mensagemDoEnvio(error));
    } catch (erro) {
      registraErroDeAuth("recuperacao:excecao", erro);
      setResposta(
        mensagemDoEnvio(erro instanceof Error ? erro : { message: String(erro) }),
      );
    }
    setEnviando(false);
  }

  return (
    <AuthShell panel={<PainelEsqueci />}>
      <PageTitle
        title="Esqueceu a senha?"
        subtitle="Digite o e-mail da sua conta. Enviamos um link para você criar uma senha nova."
      />
      <form onSubmit={enviar} className="mt-8 space-y-4">
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
        />
        {resposta && (
          <Alert tone={resposta.tom}>
            {resposta.texto}
            {resposta.contato && (
              <>
                {" "}
                <a
                  href={linkDeEmail("Esqueci a senha")}
                  className="font-medium underline"
                >
                  Falar com a gente
                </a>
              </>
            )}
          </Alert>
        )}
        <PrimaryButton disabled={enviando}>
          {enviando ? "Enviando..." : "Enviar o link"}
        </PrimaryButton>
      </form>
      <p className="mt-8 text-sm text-muted">
        Lembrou?{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          Voltar para entrar
        </Link>
      </p>
    </AuthShell>
  );
}

function PainelEsqueci() {
  return (
    <>
      <h2 className="text-3xl font-semibold leading-tight tracking-tight">
        Acontece. <span className="text-accent">Seus dados continuam aqui.</span>
      </h2>
      <p className="mt-4 text-muted">
        Trocar a senha não mexe nos seus pedidos, custos nem na conexão com o Mercado
        Livre. Quem usa o app autenticador ainda confirma o código antes da senha nova.
      </p>
    </>
  );
}
