import { GlossarioColunas } from "@/components/analytics/glossario-colunas";
import { PainelExportacao } from "@/components/analytics/painel-exportacao";
import { mensagemDeFalhaAoCarregar, getAbcPareto, getFluxoFinanceiro, getRfmScores, type AbcLinha, type FluxoDia, type RfmLinha } from "@/lib/api";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Aba Exportar — as três tabelas em CSV, com tutorial e glossário.
 *
 * A página é fina de propósito: busca as três tabelas e passa para os mesmos
 * componentes que `/demo/exportar` usa. A única diferença entre as duas é de
 * onde vem o dado — aqui `lib/api.ts`, lá `lib/demo.ts`.
 *
 * Busca as três de uma vez porque os três cartões mostram a contagem de
 * linhas antes do clique: um cartão que diz "38 linhas" é informação, um que
 * diz "baixar" e vem vazio é uma pegadinha.
 */

export default async function ExportarPage({
  searchParams,
}: PageProps<"/dashboard/exportar">) {
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
      getFluxoFinanceiro(de, ate),
      getAbcPareto(de, ate),
      getRfmScores(de, ate),
    ]);
  } catch (e) {
    erro = mensagemDeFalhaAoCarregar(e);
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
        <PainelExportacao fluxo={fluxo} abc={abc} rfm={rfm} de={de} ate={ate} />
      )}

      {/* O glossário aparece mesmo com erro ou sem dado: é documentação, e
          serve a quem veio justamente entender o arquivo. */}
      <GlossarioColunas />
    </>
  );
}
