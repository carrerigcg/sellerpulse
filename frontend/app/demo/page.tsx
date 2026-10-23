import { connection } from "next/server";

import { totalizarFluxo } from "@/components/analytics/executive-totals";
import { ResumoDaLoja } from "@/components/resumo/resumo-da-loja";
import { janelaAnterior } from "@/lib/api";
import { coberturaDoFluxo } from "@/lib/cobertura";
import {
  getDemoAbcPareto,
  getDemoCustos,
  getDemoFluxoFinanceiro,
  getDemoRfmScores,
} from "@/lib/demo";
import { periodoDoResumo, periodoPadrao } from "@/lib/periodo";
import {
  hrefDoFinanceiro,
  montaTarefas,
  montaVeredito,
  rodapeDasTarefas,
  valorOuNulo,
  type LinksDoResumo,
} from "@/lib/resumo";

/**
 * Resumo da demonstração pública — o mesmo do dashboard, com os getters da
 * demo. É a primeira tela de quem clica "Ver demonstração" na vitrine.
 *
 * `connection()` antes de tudo: esta página não lê `searchParams` nem cookie,
 * e os fetches da demo têm cache de uma hora (`lib/demo.ts`). Sem isto o Next
 * pode pré-renderizá-la no build, com "os últimos 30 dias" congelados no dia
 * do deploy.
 */
export default async function DemoResumoPage() {
  await connection();

  const periodo = periodoDoResumo();
  const periodoClientes = periodoPadrao();
  const [antDe, antAte] = janelaAnterior(periodo.de, periodo.ate);

  const [fluxo, anterior, abc, custos, rfm] = await Promise.allSettled([
    getDemoFluxoFinanceiro(periodo.de, periodo.ate),
    getDemoFluxoFinanceiro(antDe, antAte),
    getDemoAbcPareto(periodo.de, periodo.ate),
    getDemoCustos(periodo.de, periodo.ate),
    getDemoRfmScores(periodoClientes.de, periodoClientes.ate),
  ]);

  const erro = [fluxo, anterior].some((r) => r.status === "rejected")
    ? "Não foi possível carregar a demonstração agora. Tente de novo em instantes."
    : null;

  const dias = valorOuNulo(fluxo) ?? [];
  const diasAnteriores = valorOuNulo(anterior) ?? [];
  const links: LinksDoResumo = { base: "/demo", periodo, periodoClientes };
  const resultado = montaTarefas({
    custos: valorOuNulo(custos),
    abc: valorOuNulo(abc),
    rfm: valorOuNulo(rfm),
    links,
  });

  return (
    <ResumoDaLoja
      legenda={periodo.legenda}
      erro={erro}
      semVendas={dias.length === 0}
      vazio={
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-muted">
          Nenhuma venda nos últimos 30 dias da demonstração.
        </p>
      }
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
  );
}
