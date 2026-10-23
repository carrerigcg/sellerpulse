import { connection } from "next/server";

import { ResumoDaLoja } from "@/components/resumo/resumo-da-loja";
import { janelaAnterior } from "@/lib/api";
import {
  getDemoAbcPareto,
  getDemoCustos,
  getDemoFluxoFinanceiro,
  getDemoRfmScores,
} from "@/lib/demo";
import { periodoDoResumo, periodoPadrao } from "@/lib/periodo";
import { montaResumo } from "@/lib/resumo";

/**
 * Resumo da demonstração pública — o mesmo do dashboard, com os getters da
 * demo. É a primeira tela de quem clica "Ver demonstração" na vitrine.
 *
 * `connection()` antes de tudo: esta página não lê `searchParams` nem cookie,
 * e os fetches da demo têm cache de uma hora (`lib/demo.ts`). Medido: sem
 * isto o build a torna estática com revalidação de 1h, e "os últimos 30 dias"
 * ficam atrasados até a próxima revalidação — na virada do dia, no dia errado.
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

  const resumo = montaResumo({
    fluxo,
    anterior,
    abc,
    custos,
    rfm,
    links: { base: "/demo", periodo, periodoClientes },
  });

  return (
    <ResumoDaLoja
      legenda={periodo.legenda}
      erro={
        resumo.erroNoFluxo &&
        "Não foi possível carregar a demonstração agora. Tente de novo em instantes."
      }
      semVendas={resumo.semVendas}
      vazio={
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-muted">
          Nenhuma venda nos últimos 30 dias da demonstração.
        </p>
      }
      veredito={resumo.veredito}
      tarefas={resumo.tarefas}
      rodape={resumo.rodape}
      hrefFinanceiro={resumo.hrefFinanceiro}
    />
  );
}
