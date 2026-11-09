/**
 * No lugar de uma tela que é de uma conta só (Custos, Conectar) quando o
 * painel está na soma das contas. O backend recusa essas rotas na visão
 * somada (409 `visao-somada`): gravar um custo ou desconectar na soma não
 * diria em qual conta. Spec `docs/specs/2026-11-06-premium-varias-contas-design.md`.
 */
export function EscolhaUmaConta({ motivo }: { motivo: string }) {
  return (
    <section className="mt-8 rounded-xl border border-line bg-surface p-5">
      <h2 className="text-sm font-semibold">Esta tela é de uma conta só</h2>
      <p className="mt-1 text-sm text-muted">
        {motivo} Escolha a conta do Mercado Livre no seletor do topo do painel.
      </p>
    </section>
  );
}
