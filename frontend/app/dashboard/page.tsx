import Link from "next/link";
import type { ReactNode } from "react";

import { ResumoDaLoja } from "@/components/resumo/resumo-da-loja";
import {
  ApiError,
  getAbcPareto,
  getCustos,
  getFluxoFinanceiro,
  getRfmScores,
  janelaAnterior,
} from "@/lib/api";
import { periodoDoResumo, periodoPadrao } from "@/lib/periodo";
import { montaResumo } from "@/lib/resumo";

import { DisparaDelta } from "./delta";

/**
 * Resumo — a porta de entrada: "estou ganhando dinheiro?" e "o que eu faço
 * agora?", em frases. Desenho em `docs/specs/2026-10-23-resumo-da-loja-design.md`.
 *
 * O Executive que morava aqui é o Financeiro, em `/dashboard/financeiro`.
 * `DisparaDelta` ficou: é a porta de entrada que sincroniza ao entrar.
 *
 * `allSettled` porque só o fluxo é indispensável. O que fazer com cada
 * resultado mora em `montaResumo`, onde o vitest alcança; aqui fica só a
 * busca e o texto que depende do contexto.
 */
export default async function ResumoPage() {
  const periodo = periodoDoResumo();
  const periodoClientes = periodoPadrao();
  const [antDe, antAte] = janelaAnterior(periodo.de, periodo.ate);

  const [fluxo, anterior, abc, custos, rfm] = await Promise.allSettled([
    getFluxoFinanceiro(periodo.de, periodo.ate),
    getFluxoFinanceiro(antDe, antAte),
    getAbcPareto(periodo.de, periodo.ate),
    getCustos(periodo.de, periodo.ate),
    getRfmScores(periodoClientes.de, periodoClientes.ate),
  ]);

  const resumo = montaResumo({
    fluxo,
    anterior,
    abc,
    custos,
    rfm,
    links: { base: "/dashboard", periodo, periodoClientes },
  });

  return (
    <>
      <DisparaDelta />
      <ResumoDaLoja
        legenda={periodo.legenda}
        erro={resumo.erroNoFluxo && mensagemDeErro(resumo.erroNoFluxo.motivo)}
        semVendas={resumo.semVendas}
        vazio={<SemVendasNoResumo />}
        veredito={resumo.veredito}
        tarefas={resumo.tarefas}
        rodape={resumo.rodape}
        hrefFinanceiro={resumo.hrefFinanceiro}
      />
    </>
  );
}

/**
 * A mensagem de `mensagemDeFalhaAoCarregar` ("O backend está no ar?") serve às
 * telas de detalhe; na porta de entrada, para quem não sabe o que é backend,
 * ela só assusta. Sessão expirada ganha o caminho de volta, não só o aviso.
 */
function mensagemDeErro(motivo: unknown): ReactNode {
  if (motivo instanceof ApiError && motivo.status === 401) {
    return (
      <>
        Sua sessão expirou.{" "}
        <Link href="/login" className="font-medium underline">
          Entrar de novo
        </Link>
        .
      </>
    );
  }
  return "Não foi possível carregar o resumo agora. Tente de novo em instantes.";
}

/**
 * Vazio do Resumo, e não o `SemPedidosNoPeriodo` das outras telas: aquele
 * manda conectar a conta, e com uma janela de 30 dias o vazio também atinge
 * quem já conectou e só ficou um mês sem vender — ou quem ainda está na
 * importação inicial.
 */
function SemVendasNoResumo() {
  return (
    <div className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 leading-relaxed">
      <p>Nenhuma venda nos últimos 30 dias.</p>
      <p className="mt-2 text-muted">
        Se você acabou de conectar a conta, as vendas aparecem aqui quando a importação terminar.{" "}
        <Link href="/dashboard/financeiro" className="text-accent underline hover:text-accent-hover">
          Ver os últimos 3 meses
        </Link>
        {" · "}
        <Link href="/dashboard/conectar" className="text-accent underline hover:text-accent-hover">
          Conectar uma conta do Mercado Livre
        </Link>
      </p>
    </div>
  );
}
