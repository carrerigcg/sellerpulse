"use client";

import { useState } from "react";

import type { AbcLinha, FluxoDia, RfmLinha } from "@/lib/api";
import { INTERVALO_ENTRE_DOWNLOADS, baixaTexto, espera } from "@/lib/baixar-arquivo";
import { COLUNAS_ABC, COLUNAS_FLUXO, COLUNAS_RFM } from "@/lib/colunas-export";
import { montaCsv, nomeDoArquivo } from "@/lib/csv";

import { ExportButton } from "./export-button";
import { IconeExportar } from "../nav/icones";

/**
 * Os três cartões de exportação, mais o "baixar tudo".
 *
 * Client Component inteiro porque o "baixar tudo" precisa de estado. Note que
 * aqui dentro as funções são livres: a regra de que função não atravessa a
 * fronteira RSC vale para o que vem como *prop* de um Server Component, e o
 * que vem de fora aqui é só dado (as três listas e as duas datas).
 *
 * Um só botão laranja na tela, o "baixar tudo". Os três dos cartões são
 * discretos de propósito: com quatro botões de ação da mesma cor, nenhum é a
 * ação principal.
 */
export function PainelExportacao({
  fluxo,
  abc,
  rfm,
  de,
  ate,
  demo = false,
}: {
  fluxo: readonly FluxoDia[];
  abc: readonly AbcLinha[];
  rfm: readonly RfmLinha[];
  de: string;
  ate: string;
  /** `true` acrescenta `demo` ao nome do arquivo. O dado é de um vendedor sintético. */
  demo?: boolean;
}) {
  const [baixandoTudo, setBaixandoTudo] = useState(false);

  // `tela` repete os mesmos nomes usados pelos botões das telas de análise,
  // para que o arquivo da mesma tabela tenha o mesmo nome, venha de onde vier.
  const nome = (tela: string) => nomeDoArquivo(demo ? `demo-${tela}` : tela, de, ate);

  const tabelas = [
    {
      chave: "executive",
      titulo: "Fluxo financeiro",
      descricao: "Uma linha por dia, com receita, comissão, frete e margem.",
      linhas: fluxo.length,
      colunas: COLUNAS_FLUXO.length,
      botao: (
        <ExportButton
          linhas={fluxo}
          colunas={COLUNAS_FLUXO}
          tela={demo ? "demo-executive" : "executive"}
          de={de}
          ate={ate}
          rotulo="Baixar"
          cheio
        />
      ),
      monta: () => montaCsv(fluxo, COLUNAS_FLUXO),
    },
    {
      chave: "produtos",
      titulo: "Produtos",
      descricao: "Um produto por linha, com a classe ABC e a fatia da receita.",
      linhas: abc.length,
      colunas: COLUNAS_ABC.length,
      botao: (
        <ExportButton
          linhas={abc}
          colunas={COLUNAS_ABC}
          tela={demo ? "demo-produtos" : "produtos"}
          de={de}
          ate={ate}
          rotulo="Baixar"
          cheio
        />
      ),
      monta: () => montaCsv(abc, COLUNAS_ABC),
    },
    {
      chave: "clientes",
      titulo: "Clientes",
      descricao: "Um comprador por linha, com os scores RFM e o segmento.",
      linhas: rfm.length,
      colunas: COLUNAS_RFM.length,
      botao: (
        <ExportButton
          linhas={rfm}
          colunas={COLUNAS_RFM}
          tela={demo ? "demo-clientes" : "clientes"}
          de={de}
          ate={ate}
          rotulo="Baixar"
          cheio
        />
      ),
      monta: () => montaCsv(rfm, COLUNAS_RFM),
    },
  ];

  const comDados = tabelas.filter((t) => t.linhas > 0);
  const totalDeLinhas = comDados.reduce((soma, t) => soma + t.linhas, 0);

  async function baixarTudo() {
    setBaixandoTudo(true);
    try {
      for (const tabela of comDados) {
        baixaTexto(tabela.monta(), nome(tabela.chave));
        // Intervalo entre os três: ver INTERVALO_ENTRE_DOWNLOADS. Sem ele, a
        // rajada pode entregar só o último arquivo.
        await espera(INTERVALO_ENTRE_DOWNLOADS);
      }
    } finally {
      setBaixandoTudo(false);
    }
  }

  return (
    <>
      <section className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-surface p-5">
        <div>
          <h2 className="text-sm font-semibold">Baixar as três tabelas</h2>
          <p className="mt-0.5 text-xs text-muted">
            {comDados.length === 0
              ? "Nenhuma das tabelas tem dados neste período."
              : `${comDados.length} ${
                  comDados.length === 1 ? "arquivo" : "arquivos"
                } · ${totalDeLinhas.toLocaleString("pt-BR")} linhas no total`}
          </p>
        </div>
        <button
          type="button"
          onClick={baixarTudo}
          disabled={comDados.length === 0 || baixandoTudo}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-accent"
        >
          <IconeExportar />
          {baixandoTudo ? "Baixando…" : "Baixar tudo"}
        </button>
      </section>

      {/* Na primeira vez o navegador pede permissão de downloads múltiplos.
          Avisar antes evita que o pedido pareça defeito. */}
      {comDados.length > 1 && (
        <p className="mt-2 text-xs text-muted">
          São {comDados.length} arquivos separados, um por tabela. Na primeira vez o
          navegador pode pedir permissão para baixar vários de uma vez.
        </p>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tabelas.map((tabela) => (
          <section key={tabela.chave} className="rounded-xl border border-line p-5">
            <h3 className="text-sm font-semibold">{tabela.titulo}</h3>
            <p className="mt-1 text-xs text-muted">{tabela.descricao}</p>
            <p className="mt-3 text-xs text-muted tabular">
              {tabela.linhas === 0
                ? "Sem dados no período"
                : `${tabela.linhas.toLocaleString("pt-BR")} ${
                    tabela.linhas === 1 ? "linha" : "linhas"
                  } · ${tabela.colunas} colunas`}
            </p>
            <div className="mt-4">{tabela.botao}</div>
          </section>
        ))}
      </div>
    </>
  );
}
