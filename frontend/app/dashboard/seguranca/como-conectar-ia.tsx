"use client";

import { useState } from "react";

import { ENDERECO_DO_MCP } from "@/lib/conexoes-ia";

const EXEMPLOS = [
  "Quanto faturei nos últimos 15 dias?",
  "Quais produtos sustentam a minha loja?",
  "Quem comprava e parou de comprar?",
];

/**
 * O passo a passo de conectar um assistente de IA, dentro de Conexões de IA.
 *
 * Os nomes de menu do Claude saíram da ajuda oficial (conferida em
 * 2026-11-17). Abre sozinho quando ainda não há conexão: é quando o vendedor
 * precisa dele; depois vira consulta, recolhido.
 */
export function ComoConectarIa({ aberto }: { aberto: boolean }) {
  return (
    <details open={aberto} className="group mt-4 rounded-lg border border-line">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 text-sm font-medium [&::-webkit-details-marker]:hidden">
        Como conectar o Claude ou o ChatGPT
        <span aria-hidden className="text-muted transition-transform group-open:rotate-180">
          ▾
        </span>
      </summary>

      <div className="space-y-5 border-t border-line px-4 py-4 text-sm">
        <p className="text-muted">
          Função do plano <strong className="text-ink">Premium</strong>. A IA só lê os
          números da loja: não altera custos, anúncios nem a assinatura.
        </p>

        <div>
          <p className="font-medium">Endereço do conector</p>
          <EnderecoComCopiar />
        </div>

        <div>
          <p className="font-medium">No Claude</p>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5">
            <li>
              Abra <strong>Personalizar &gt; Conectores</strong>, clique em <strong>+</strong> e
              em <strong>Adicionar conector personalizado</strong>.
            </li>
            <li>
              Dê o nome <strong>SellerPulse</strong>, cole o endereço acima e siga até{" "}
              <strong>Adicionar</strong>.
            </li>
            <li>
              Clique em <strong>Conectar</strong>. Abre a tela do SellerPulse: entre na sua conta,
              digite o código do app autenticador, se tiver, e clique em{" "}
              <strong>Autorizar</strong>.
            </li>
            <li>
              Numa conversa, clique no <strong>+</strong>, depois em <strong>Conectores</strong>,
              e ligue o SellerPulse.
            </li>
          </ol>
          <p className="mt-2 text-xs text-muted">
            O plano grátis do Claude aceita um conector personalizado. Nos planos Team e
            Enterprise, quem adiciona é o administrador da organização.
          </p>
        </div>

        <div>
          <p className="font-medium">No ChatGPT</p>
          <p className="mt-2">
            Conector personalizado existe nos planos Business, Enterprise e Edu. Em{" "}
            <strong>Plugins</strong>, clique em <strong>+</strong> e adicione um servidor MCP
            personalizado com o endereço acima. A autorização é a mesma tela do SellerPulse.
          </p>
        </div>

        <div>
          <p className="font-medium">Depois, é só perguntar</p>
          <ul className="mt-2 space-y-1 text-muted">
            {EXEMPLOS.map((e) => (
              <li key={e}>“{e}”</li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}

function EnderecoComCopiar() {
  const [copiado, setCopiado] = useState<boolean | null>(null);

  async function copia() {
    try {
      await navigator.clipboard.writeText(ENDERECO_DO_MCP);
      setCopiado(true);
    } catch {
      setCopiado(false);
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <code className="min-w-0 break-all rounded bg-surface px-2 py-1.5 text-xs">
        {ENDERECO_DO_MCP}
      </code>
      <button
        type="button"
        onClick={copia}
        className="inline-flex min-h-11 items-center rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface"
      >
        Copiar
      </button>
      <span role="status" className="text-xs text-muted">
        {copiado === true && "Copiado."}
        {copiado === false && "Não deu para copiar: selecione o endereço e copie à mão."}
      </span>
    </div>
  );
}
