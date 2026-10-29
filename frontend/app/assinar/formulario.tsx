"use client";

import { useState } from "react";

import { contratar } from "@/lib/ml";
import { NOMES_DOS_PLANOS, type NomeDoPlano } from "@/lib/plano";
import {
  DIAS_DE_TESTE,
  PLANO_COM_TESTE,
  PRECOS_MENSAIS,
  formatarPreco,
  precoAnual,
} from "@/lib/precos";

type Ciclo = "mensal" | "anual";

const PLANOS: NomeDoPlano[] = ["essencial", "exclusive", "premium"];

/**
 * O formulário da contratação. Só strings atravessam a fronteira do servidor;
 * os preços vêm de `lib/precos.ts` aqui mesmo, e são só o que se MOSTRA — o
 * valor cobrado sai do backend.
 *
 * O CPF/CNPJ vai para o Asaas, que exige o dado para cobrar, e não fica
 * guardado no SellerPulse.
 */
export function FormularioDeAssinatura({
  planoInicial,
  email,
  versao,
}: {
  planoInicial: NomeDoPlano;
  email: string;
  versao: string;
}) {
  const [plano, setPlano] = useState<NomeDoPlano>(planoInicial);
  const [ciclo, setCiclo] = useState<Ciclo>("mensal");
  const [nome, setNome] = useState("");
  const [documento, setDocumento] = useState("");
  const [emailDeCobranca, setEmailDeCobranca] = useState(email);
  const [aceito, setAceito] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const comTeste = ciclo === "mensal" && plano === PLANO_COM_TESTE;

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      const link = await contratar({
        plano,
        ciclo,
        versao_dos_termos: versao,
        nome,
        cpf_cnpj: documento,
        email: emailDeCobranca,
      });
      // Página do Asaas: navegação inteira, não do roteador do Next.
      window.location.assign(link);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível abrir o pagamento.");
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="mt-6 space-y-6">
      <fieldset>
        <legend className="text-sm font-semibold">Plano</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          {PLANOS.map((p) => (
            <label
              key={p}
              className={`flex cursor-pointer flex-col rounded-lg border px-3 py-2 text-sm ${
                plano === p ? "border-accent bg-accent-soft" : "border-line"
              }`}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name="plano"
                  value={p}
                  checked={plano === p}
                  onChange={() => setPlano(p)}
                  className="accent-accent"
                />
                <span className="font-medium">{NOMES_DOS_PLANOS[p]}</span>
              </span>
              <span className="mt-1 text-xs text-muted">
                {formatarPreco(PRECOS_MENSAIS[p])}/mês
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-semibold">Pagamento</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <label
            className={`flex cursor-pointer gap-2 rounded-lg border px-3 py-2 text-sm ${
              ciclo === "mensal" ? "border-accent bg-accent-soft" : "border-line"
            }`}
          >
            <input
              type="radio"
              name="ciclo"
              checked={ciclo === "mensal"}
              onChange={() => setCiclo("mensal")}
              className="mt-0.5 accent-accent"
            />
            <span>
              <span className="font-medium">Mensal, no cartão</span>
              <span className="block text-xs text-muted">
                {formatarPreco(PRECOS_MENSAIS[plano])} por mês, renova sozinho
              </span>
            </span>
          </label>
          <label
            className={`flex cursor-pointer gap-2 rounded-lg border px-3 py-2 text-sm ${
              ciclo === "anual" ? "border-accent bg-accent-soft" : "border-line"
            }`}
          >
            <input
              type="radio"
              name="ciclo"
              checked={ciclo === "anual"}
              onChange={() => setCiclo("anual")}
              className="mt-0.5 accent-accent"
            />
            <span>
              <span className="font-medium">Anual, Pix ou cartão</span>
              <span className="block text-xs text-muted">
                {formatarPreco(precoAnual(plano))} de uma vez: 12 meses pelo preço de 10
              </span>
            </span>
          </label>
        </div>
        {comTeste && (
          <p className="mt-2 rounded-lg bg-highlight-soft px-3 py-2 text-xs text-ink">
            {DIAS_DE_TESTE} dias grátis: o cartão é cadastrado agora e a primeira cobrança é só no{" "}
            {DIAS_DE_TESTE + 1}º dia. Cancelando antes, você não paga nada.
          </p>
        )}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold">Dados para a cobrança</legend>
        <Campo rotulo="Nome ou razão social" valor={nome} muda={setNome} autoComplete="name" />
        <Campo
          rotulo="CPF ou CNPJ"
          valor={documento}
          muda={setDocumento}
          inputMode="numeric"
          ajuda="Exigido pelo Asaas para emitir a cobrança. Não fica guardado no SellerPulse."
        />
        <Campo
          rotulo="E-mail para a cobrança"
          valor={emailDeCobranca}
          muda={setEmailDeCobranca}
          tipo="email"
          autoComplete="email"
        />
      </fieldset>

      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={aceito}
          onChange={(e) => setAceito(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-accent"
        />
        <span>Li e aceito os Termos de Uso e a Política de Privacidade do SellerPulse.</span>
      </label>

      {erro && (
        <p role="alert" className="rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}
        </p>
      )}

      <button
        type="submit"
        disabled={!aceito || enviando || !nome || !documento || !emailDeCobranca}
        className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
      >
        {enviando
          ? "Abrindo o pagamento…"
          : comTeste
            ? `Começar os ${DIAS_DE_TESTE} dias grátis`
            : "Ir para o pagamento"}
      </button>
    </form>
  );
}

function Campo({
  rotulo,
  valor,
  muda,
  tipo = "text",
  ajuda,
  autoComplete,
  inputMode,
}: {
  rotulo: string;
  valor: string;
  muda: (v: string) => void;
  tipo?: string;
  ajuda?: string;
  autoComplete?: string;
  inputMode?: "numeric";
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{rotulo}</span>
      <input
        type={tipo}
        value={valor}
        onChange={(e) => muda(e.target.value)}
        required
        autoComplete={autoComplete}
        inputMode={inputMode}
        className="mt-1 block w-full rounded-lg border border-line bg-bg px-3 py-2 outline-none focus:border-accent"
      />
      {ajuda && <span className="mt-1 block text-xs text-muted">{ajuda}</span>}
    </label>
  );
}
