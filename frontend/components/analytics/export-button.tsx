"use client";

import { montaCsv, nomeDoArquivo, type Coluna } from "@/lib/csv";

import { IconeExportar } from "../nav/icones";

/**
 * Botão que baixa a tabela da tela como CSV.
 *
 * Client Component porque precisa de `onClick` e das APIs de download do
 * navegador. As linhas chegam como props a partir do Server Component da
 * página — dado puro atravessa a fronteira RSC; função, não. (Já custou uma
 * página quebrada neste projeto, com `lint` e `build` passando.)
 *
 * O arquivo é montado aqui, no navegador, a partir do dado que a página já
 * carregou: nenhum endpoint novo, nenhuma dependência, nenhuma memória no
 * Render — que tem 512 MB e hiberna.
 */
export function ExportButton<T>({
  linhas,
  colunas,
  tela,
  de,
  ate,
}: {
  linhas: readonly T[];
  colunas: readonly Coluna<T>[];
  /** Vira parte do nome do arquivo: "produtos", "clientes", "executive". */
  tela: string;
  de: string;
  ate: string;
}) {
  function baixar() {
    const csv = montaCsv(linhas, colunas);
    // `text/csv;charset=utf-8` junto com o BOM: os dois dizem a mesma coisa,
    // e o Excel escuta o BOM. O tipo serve ao sistema operacional.
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nomeDoArquivo(tela, de, ate);
    document.body.appendChild(a);
    a.click();
    // Limpeza: sem o revoke, o blob fica preso na memória da aba até ela
    // fechar — e quem exporta dez vezes acumula dez cópias da tabela.
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
      className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted"
    >
      <IconeExportar />
      Exportar
    </button>
  );
}
