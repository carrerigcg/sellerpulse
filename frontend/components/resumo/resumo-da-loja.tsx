import type { ReactNode } from "react";

import type { Tarefa, Veredito } from "@/lib/resumo";

import { BlocoDinheiro } from "./bloco-dinheiro";
import { ListaDeTarefas } from "./lista-de-tarefas";

/**
 * O Resumo inteiro, igual no dashboard e na demo. Cada página busca com os
 * próprios getters e entrega o resultado pronto; o estado vazio vem de fora
 * porque o do dashboard oferece conectar a conta e o da demo não.
 *
 * Texto base em 16px (o `text-base` do contêiner): é a tela feita para quem
 * tem dificuldade com as outras, e na de Produtos 213 blocos de texto estão
 * em 12px.
 */
export function ResumoDaLoja({
  legenda,
  erro,
  semVendas,
  vazio,
  veredito,
  tarefas,
  rodape,
  hrefFinanceiro,
}: {
  legenda: string;
  /** Nó, e não texto: a sessão expirada leva um link para entrar de novo. */
  erro: ReactNode | null;
  semVendas: boolean;
  vazio: ReactNode;
  veredito: Veredito;
  tarefas: Tarefa[];
  rodape: string | null;
  hrefFinanceiro: string;
}) {
  return (
    <div className="text-base">
      <h1 className="text-2xl font-semibold tracking-tight">Sua loja nos últimos 30 dias</h1>
      <p className="mt-1 text-muted">{legenda}</p>

      {erro ? (
        // Texto em `ink`, com a cor na borda e no fundo: o vermelho de
        // `negative` sobre `negative/10` fica perto de 4,1:1 em 16px, abaixo
        // do mínimo para texto normal.
        <p className="mt-8 rounded-lg border border-negative/40 bg-negative/10 px-4 py-3 text-ink">
          {erro}
        </p>
      ) : semVendas ? (
        vazio
      ) : (
        <>
          <BlocoDinheiro veredito={veredito} hrefFinanceiro={hrefFinanceiro} />
          <ListaDeTarefas tarefas={tarefas} rodape={rodape} />
        </>
      )}
    </div>
  );
}
