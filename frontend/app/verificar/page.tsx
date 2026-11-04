"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, AuthShell, PageTitle, PrimaryButton, TextField } from "@/components/auth-ui";
import { linkDeEmail } from "@/lib/contato";
import { codigoValido, faltaOCodigo } from "@/lib/duas-etapas";
import { destinoDepoisDoLogin } from "@/lib/proximo";
import { createClient } from "@/lib/supabase/client";

/**
 * A segunda etapa do login, para quem ativou o app autenticador.
 *
 * Fora do matcher do `proxy.ts` de propósito: ele manda para cá justamente a
 * sessão que ainda não passou pelo código. Quem chega sem sessão, ou sem o
 * app ativo, segue para onde ia.
 */
export default function VerificarPage() {
  const router = useRouter();
  const [fator, setFator] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    (async () => {
      const { data: nivel } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
      if (!faltaOCodigo(nivel)) {
        router.replace(nivel ? destinoDepoisDoLogin() : "/login");
        return;
      }
      const { data } = await supabase.auth.mfa.listFactors();
      setFator(data?.totp.find((f) => f.status === "verified")?.id ?? null);
    })();
  }, [router]);

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    const digitos = codigoValido(codigo);
    if (!digitos) {
      setErro("O código tem 6 números. Confira no app e tente de novo.");
      return;
    }
    if (!fator) return;
    setCarregando(true);
    const supabase = createClient();
    const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: fator, code: digitos });
    if (error) {
      setErro("Código incorreto ou vencido. Use o código que está no app agora.");
      setCarregando(false);
      return;
    }
    router.push(destinoDepoisDoLogin());
    router.refresh();
  }

  async function sair() {
    await createClient().auth.signOut();
    router.push("/login");
  }

  return (
    <AuthShell panel={<PainelVerificar />}>
      <PageTitle
        title="Confirme que é você"
        subtitle="Digite o código de 6 números do seu app autenticador."
      />
      <form onSubmit={confirmar} className="mt-8 space-y-4">
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
        <PrimaryButton disabled={carregando || !fator}>
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
        </a>{" "}
        ou{" "}
        <button type="button" onClick={sair} className="font-medium text-accent hover:underline">
          entre com outra conta
        </button>
        .
      </p>
    </AuthShell>
  );
}

function PainelVerificar() {
  return (
    <>
      <h2 className="text-3xl font-semibold leading-tight tracking-tight">
        Senha certa. <span className="text-accent">Falta o código.</span>
      </h2>
      <p className="mt-4 text-muted">
        Você ativou a verificação em duas etapas: sem o código do seu celular, a senha
        sozinha não abre a conta.
      </p>
    </>
  );
}
