"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { abrirConta } from "@/lib/ml";

/**
 * A conta escolhida não abre mais: foi removida, ou o plano deixou de ter
 * várias contas. O backend recusa (`conta-invalida`) em vez de mostrar a
 * principal no lugar, e aqui a escolha é apagada para o painel voltar à
 * principal, dizendo o porquê.
 */
export function VoltaParaPrincipal() {
  const router = useRouter();
  useEffect(() => {
    abrirConta({ id: "", principal: true });
    router.refresh();
  }, [router]);

  return (
    <p className="mt-8 px-4 text-sm text-muted">
      A conta do Mercado Livre que estava aberta não está mais disponível. Voltando para a conta
      principal…
    </p>
  );
}
