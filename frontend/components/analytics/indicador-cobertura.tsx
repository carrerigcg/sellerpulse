import Link from "next/link";

import type { Cobertura } from "@/lib/cobertura";

/**
 * O aviso que acompanha toda tela que mostra margem.
 *
 * A regra: nunca esconder o número por estar incompleto, e nunca mostrá-lo
 * como se estivesse completo. Esconder faria a tela parecer quebrada para
 * quem nunca preencheu nada; mostrar sem a marca é o mesmo percentual de
 * custo chutado que foi removido em outubro de 2026, só que mais sutil.
 *
 * Quatro estados, e dois deles não renderizam nada:
 *
 * - sem receita no período: não há o que cobrir, e acusar falta de custo num
 *   período sem venda seria ruído.
 * - 100%: a margem está completa. Avisar seria barulho sobre nada.
 * - 0%: a margem não considera custo de produto nenhum — é o estado de quem
 *   ainda não usou a feature, e o aviso leva à tela de Custos.
 * - 1 a 99%: o número com a porcentagem ao lado, sempre.
 *
 * `href` ausente (a demonstração) mostra o aviso sem o atalho: o texto
 * continua verdadeiro, e não há tela de Custos para onde mandar quem não tem
 * conta.
 */
export function IndicadorCobertura({
  cobertura,
  semCusto,
  href,
}: {
  cobertura: Cobertura;
  /** Quantos produtos ainda não têm custo informado. */
  semCusto?: number;
  /** Destino do atalho para preencher custos. Omitido = sem atalho. */
  href?: string;
}) {
  if (cobertura.semReceita || cobertura.completa) return null;

  const pendentes =
    semCusto && semCusto > 0
      ? ` ${semCusto} ${semCusto === 1 ? "produto sem custo" : "produtos sem custo"}.`
      : "";

  return (
    <p className="mt-3 rounded-lg bg-highlight-soft px-3 py-2 text-xs leading-relaxed text-ink">
      {cobertura.vazia ? (
        <>
          Esta margem <strong className="font-medium">não considera o custo dos produtos</strong> —
          nenhum foi informado ainda.
        </>
      ) : (
        <>
          Custo informado para{" "}
          <strong className="font-medium tabular">{cobertura.pct}%</strong> da receita do período.
          {pendentes}
        </>
      )}{" "}
      {href && (
        <Link href={href} className="font-medium text-accent underline-offset-2 hover:underline">
          Informar custos
        </Link>
      )}
    </p>
  );
}
