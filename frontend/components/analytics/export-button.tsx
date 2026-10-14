"use client";

import { baixaTexto } from "@/lib/baixar-arquivo";
import { montaCsv, nomeDoArquivo, type Coluna } from "@/lib/csv";

import { IconeExportar } from "../nav/icones";

/**
 * Botão que baixa uma tabela como CSV.
 *
 * Client Component porque precisa de `onClick` e das APIs de download do
 * navegador. As linhas chegam como props a partir do Server Component da
 * página — dado puro atravessa a fronteira RSC; função, não. (Já custou uma
 * página quebrada neste projeto, com `lint` e `build` passando.)
 *
 * O arquivo é montado aqui, no navegador, a partir do dado que a página já
 * carregou: nenhum endpoint novo, nenhuma dependência, nenhuma memória no
 * Render — que tem 512 MB e hiberna.
 *
 * Usado em dois contextos, e é por isso que `rotulo` e `cheio` existem: no
 * cabeçalho das seções das três telas de análise, discreto e com largura
 * natural; e dentro dos cartões da aba Exportar, ocupando a largura do
 * cartão. O padrão é o primeiro, para que as três telas que já o usavam não
 * mudem de aparência.
 */
export function ExportButton<T>({
  linhas,
  colunas,
  tela,
  de,
  ate,
  rotulo = "Exportar",
  cheio = false,
}: {
  linhas: readonly T[];
  colunas: readonly Coluna<T>[];
  /** Vira parte do nome do arquivo: "produtos", "clientes", "executive". */
  tela: string;
  de: string;
  ate: string;
  rotulo?: string;
  /** `true` ocupa a largura do contêiner e centraliza o conteúdo. */
  cheio?: boolean;
}) {
  function baixar() {
    baixaTexto(montaCsv(linhas, colunas), nomeDoArquivo(tela, de, ate));
  }

  return (
    <button
      type="button"
      onClick={baixar}
      disabled={linhas.length === 0}
      title={
        linhas.length === 0
          ? "Nada para exportar neste período"
          : `Baixar ${linhas.length} linhas em CSV`
      }
      className={`inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted ${
        cheio ? "w-full justify-center" : ""
      }`}
    >
      <IconeExportar />
      {rotulo}
    </button>
  );
}
