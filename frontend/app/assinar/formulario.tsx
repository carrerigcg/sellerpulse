"use client";

import { useEffect, useState } from "react";

import { contratar } from "@/lib/ml";
import { NOMES_DOS_PLANOS, PLANOS_A_VENDA, type NomeDoPlano } from "@/lib/plano";
import {
  DIAS_DE_TESTE,
  PLANO_COM_TESTE,
  PRECOS_DEPOIS_DO_LANCAMENTO,
  PRECOS_MENSAIS,
  formatarPreco,
  precoAnual,
} from "@/lib/precos";

type Ciclo = "mensal" | "anual";

/**
 * O formulário da contratação. Só strings atravessam a fronteira do servidor;
 * os preços vêm de `lib/precos.ts` aqui mesmo, e são só o que se MOSTRA — o
 * valor cobrado sai do backend.
 *
 * Sem nome, CPF/CNPJ ou endereço: quem pede os dados de cobrança é a página
 * do Asaas, e o SellerPulse não os recebe nem de passagem.
 */
export function FormularioDeAssinatura({
  planoInicial,
  versao,
}: {
  planoInicial: NomeDoPlano;
  versao: string;
}) {
  const [plano, setPlano] = useState<NomeDoPlano>(planoInicial);
  const [ciclo, setCiclo] = useState<Ciclo>("mensal");
  const [aceito, setAceito] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const comTeste = ciclo === "mensal" && plano === PLANO_COM_TESTE;

  // Quem volta do Asaas pelo "voltar" do navegador pode receber esta página
  // restaurada da memória, com o botão travado em "Abrindo o pagamento…".
  useEffect(() => {
    function aoVoltar(evento: PageTransitionEvent) {
      if (evento.persisted) setEnviando(false);
    }
    window.addEventListener("pageshow", aoVoltar);
    return () => window.removeEventListener("pageshow", aoVoltar);
  }, []);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      const link = await contratar({
        plano,
        ciclo,
        versao_dos_termos: versao,
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
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {PLANOS_A_VENDA.map((p) => (
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
                <span className="font-medium text-ink">{formatarPreco(PRECOS_MENSAIS[p])}</span>/mês
                <span className="block">
                  depois do lançamento: <s>{formatarPreco(PRECOS_DEPOIS_DO_LANCAMENTO[p])}</s>
                </span>
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

      <p className="text-xs text-muted">
        Os dados de cobrança (nome, CPF ou CNPJ, endereço e cartão) você preenche na página
        do Asaas, no próximo passo.
      </p>

      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          required
          checked={aceito}
          onChange={(e) => setAceito(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-accent"
        />
        <span>
          Li e aceito os{" "}
          <a href="/termos" target="_blank" rel="noopener noreferrer" className="font-medium text-accent underline">
            Termos de Uso
          </a>{" "}
          e a{" "}
          <a href="/privacidade" target="_blank" rel="noopener noreferrer" className="font-medium text-accent underline">
            Política de Privacidade
          </a>{" "}
          do SellerPulse.
        </span>
      </label>

      {erro && (
        <p role="alert" className="rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
          {erro}
        </p>
      )}

      <button
        type="submit"
        // Habilitado mesmo sem o aceite marcado: com o botão desabilitado, o
        // navegador nunca diz o que falta. O `required` da caixa faz isso.
        disabled={enviando}
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
