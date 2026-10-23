import { totalizarFluxo } from "@/components/analytics/executive-totals";
import { SemPedidosNoPeriodo } from "@/components/analytics/sem-pedidos-no-periodo";
import { ResumoDaLoja } from "@/components/resumo/resumo-da-loja";
import {
  getAbcPareto,
  getCustos,
  getFluxoFinanceiro,
  getRfmScores,
  janelaAnterior,
  mensagemDeFalhaAoCarregar,
} from "@/lib/api";
import { coberturaDoFluxo } from "@/lib/cobertura";
import { periodoDoResumo, periodoPadrao } from "@/lib/periodo";
import {
  hrefDoFinanceiro,
  montaTarefas,
  montaVeredito,
  rodapeDasTarefas,
  valorOuNulo,
  type LinksDoResumo,
} from "@/lib/resumo";

import { DisparaDelta } from "./delta";

/**
 * Resumo — a porta de entrada: "estou ganhando dinheiro?" e "o que eu faço
 * agora?", em frases. Desenho em `docs/specs/2026-10-23-resumo-da-loja-design.md`.
 *
 * O Executive que morava aqui é o Financeiro, em `/dashboard/financeiro`.
 * `DisparaDelta` ficou: é a porta de entrada que sincroniza ao entrar.
 *
 * `allSettled` porque só o fluxo é indispensável. Sem uma das outras fontes a
 * tarefa dela some e o rodapé avisa — melhor que derrubar a tela inteira.
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

  // Sem o fluxo anterior a comparação mentiria por omissão: os dois derrubam.
  const falha = [fluxo, anterior].find(
    (r): r is PromiseRejectedResult => r.status === "rejected",
  );
  const erro = falha ? mensagemDeFalhaAoCarregar(falha.reason) : null;

  const dias = valorOuNulo(fluxo) ?? [];
  const diasAnteriores = valorOuNulo(anterior) ?? [];
  const links: LinksDoResumo = { base: "/dashboard", periodo, periodoClientes };
  const resultado = montaTarefas({
    custos: valorOuNulo(custos),
    abc: valorOuNulo(abc),
    rfm: valorOuNulo(rfm),
    links,
  });

  return (
    <>
      <DisparaDelta />
      <ResumoDaLoja
        legenda={periodo.legenda}
        erro={erro}
        semVendas={dias.length === 0}
        vazio={<SemPedidosNoPeriodo mensagem="Nenhuma venda nos últimos 30 dias." />}
        veredito={montaVeredito({
          atual: totalizarFluxo(dias),
          anterior: diasAnteriores.length > 0 ? totalizarFluxo(diasAnteriores) : null,
          coberturaAtual: coberturaDoFluxo(dias),
          coberturaAnterior: diasAnteriores.length > 0 ? coberturaDoFluxo(diasAnteriores) : null,
        })}
        tarefas={resultado.tarefas}
        rodape={rodapeDasTarefas(resultado)}
        hrefFinanceiro={hrefDoFinanceiro(links)}
      />
    </>
  );
}
