import type { Cobertura } from "@/lib/cobertura";

/**
 * O aviso do frete que ainda não foi buscado — par do `IndicadorCobertura`.
 *
 * Mesma regra, outra causa. O custo de produto falta porque o vendedor não
 * informou, e o aviso leva à tela de Custos. O frete falta porque a colheita
 * no Mercado Livre ainda não terminou: um envio por chamada, depois de cada
 * sincronização. Não há o que o vendedor fazer, então não há atalho — só a
 * marca de que a margem ainda está maior do que a real.
 *
 * Sem receita ou com o frete todo buscado, não renderiza nada.
 */
export function IndicadorFrete({ cobertura }: { cobertura: Cobertura }) {
  if (cobertura.semReceita || cobertura.completa) return null;

  return (
    <p className="mt-3 rounded-lg bg-highlight-soft px-3 py-2 text-xs leading-relaxed text-ink">
      {cobertura.vazia ? (
        <>
          Esta margem <strong className="font-medium">ainda não desconta o frete</strong> — ele está
          sendo buscado no Mercado Livre, envio por envio.
        </>
      ) : (
        <>
          Frete buscado para{" "}
          <strong className="font-medium tabular">{cobertura.pct}%</strong> da receita do período. O
          resto ainda está sendo buscado no Mercado Livre, e até lá a margem aparece maior do que a
          real.
        </>
      )}
    </p>
  );
}
