import { GlossarioColunas } from "@/components/analytics/glossario-colunas";
import { PainelExportacao } from "@/components/analytics/painel-exportacao";
import type { AbcLinha, FluxoDia, RfmLinha } from "@/lib/api";
import { getDemoAbcPareto, getDemoFluxoFinanceiro, getDemoRfmScores } from "@/lib/demo";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Exportar da demonstração pública — mesmo conteúdo de `/dashboard/exportar`,
 * dados de `/demo/*`. O painel e o glossário vêm de `components/analytics/`,
 * os mesmos componentes da tela autenticada.
 *
 * `demo` entra no nome do arquivo (`sellerpulse-demo-clientes-….csv`): o
 * conteúdo é de um vendedor sintético, e quem baixar daqui precisa saber
 * disso ao reabrir o arquivo uma semana depois. A ressalva não vai DENTRO do
 * CSV — uma linha acima do cabeçalho desloca todas as colunas no Excel.
 */

export default async function DemoExportarPage({
  searchParams,
}: PageProps<"/demo/exportar">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let fluxo: FluxoDia[] = [];
  let abc: AbcLinha[] = [];
  let rfm: RfmLinha[] = [];
  let erro: string | null = null;

  try {
    [fluxo, abc, rfm] = await Promise.all([
      getDemoFluxoFinanceiro(de, ate),
      getDemoAbcPareto(de, ate),
      getDemoRfmScores(de, ate),
    ]);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  return (
    <>
      <CabecalhoDeTela
        titulo="Exportar"
        subtitulo="Leve as tabelas para a planilha, e entenda o que cada coluna quer dizer."
        de={de}
        ate={ate}
        tela="exportar"
        temDados={!erro && fluxo.length + abc.length + rfm.length > 0}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          {erro}
        </p>
      ) : (
        <PainelExportacao fluxo={fluxo} abc={abc} rfm={rfm} de={de} ate={ate} demo />
      )}

      <GlossarioColunas demo />
    </>
  );
}
