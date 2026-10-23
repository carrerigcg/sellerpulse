import Link from "next/link";
import type { ComponentType } from "react";

import { IconeClientes, IconeCustos, IconeProdutos } from "@/components/nav/icones";
import type { ChaveDaTarefa, Tarefa } from "@/lib/resumo";

const ICONE: Record<ChaveDaTarefa, ComponentType<{ className?: string }>> = {
  custos: IconeCustos,
  "visto-e-rejeitado": IconeProdutos,
  "clientes-em-risco": IconeClientes,
};

/**
 * "O que fazer agora". Os botões são de contorno, não laranja: nenhuma tarefa
 * é mais importante que as outras, e a direção visual é um só botão de ação
 * primária por tela.
 */
export function ListaDeTarefas({ tarefas, rodape }: { tarefas: Tarefa[]; rodape: string | null }) {
  return (
    <section aria-labelledby="resumo-tarefas" className="mt-8">
      <h2 id="resumo-tarefas" className="text-lg font-semibold">
        O que fazer agora
      </h2>
      {tarefas.length > 0 && (
        <ul className="mt-3 flex flex-col gap-3">
          {tarefas.map((tarefa) => {
            const Icone = ICONE[tarefa.chave];
            return (
              <li
                key={tarefa.chave}
                className="flex flex-wrap items-center gap-4 rounded-xl border border-line p-4 sm:p-5"
              >
                {/* Só a cor: o ícone já traz `h-5 w-5`, e somar outro tamanho
                    deixaria a ordem do CSS gerado decidir qual vence. */}
                <Icone className="text-accent" />
                <div className="min-w-0 flex-1 basis-60">
                  <p className="font-medium">{tarefa.frase}</p>
                  <p className="mt-1 leading-relaxed text-muted">{tarefa.apoio}</p>
                </div>
                <Link
                  href={tarefa.href}
                  className="inline-flex min-h-11 items-center rounded-lg border border-line px-4 font-medium text-ink transition hover:bg-surface"
                >
                  {tarefa.botao}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {rodape && (
        <p className="mt-3 rounded-lg border border-line bg-surface px-4 py-3 text-muted">{rodape}</p>
      )}
    </section>
  );
}
