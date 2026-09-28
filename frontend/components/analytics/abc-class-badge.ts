import type { ClasseAbc } from "@/lib/api";

/**
 * Classe A/B/C é ordinal — uma fronteira acumulada, não uma categoria solta.
 * Por isso usa uma única família de cor (accent) em três intensidades já
 * tokenizadas, em vez de três matizes diferentes: A sólido, B no tom suave
 * já existente (`accent-soft`), C neutro. Nenhum hex novo.
 *
 * Usado pelos cartões de classe e pela tabela de produtos, nas duas versões
 * (autenticada e demo) — daí viver isolado do componente que o usa primeiro.
 */
export function abcClassBadgeClass(classe: ClasseAbc): string {
  switch (classe) {
    case "A":
      return "bg-accent text-white";
    case "B":
      return "bg-accent-soft text-accent";
    case "C":
      return "bg-surface text-muted border border-line";
  }
}
