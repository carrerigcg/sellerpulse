/**
 * O que ficou fora da receita — e o que fecha a conta contra o Mercado Livre.
 *
 * O "vendas brutas" do painel do ML soma tudo o que foi vendido, inclusive o
 * que foi cancelado ou devolvido depois. A nossa "Receita bruta" conta só o
 * que continua pago. Sem esta frase, quem compara os dois painéis vê R$ 5 mil
 * de diferença e conclui que o nosso número está errado. Com ela, a diferença
 * vira a prova de que ele está certo.
 * Ver docs/specs/2026-10-28-receita-vs-vendas-brutas-design.md.
 */

/** Total de pedidos cancelados ou devolvidos da janela (`/metrics/cancelamentos`). */
export type Cancelamentos = { pedidos: number; valor: number };

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/**
 * `null` quando não há o que dizer: período sem cancelamento, ou a busca
 * falhou. A frase é apoio — sem ela a tela fica menos clara, mas nada fica
 * errado, então a falha não pode derrubar a tela.
 */
export function fraseDosCancelamentos(c: Cancelamentos | null): string | null {
  if (!c || c.pedidos <= 0) return null;
  const pedidos =
    c.pedidos === 1
      ? "1 pedido cancelado ou devolvido"
      : `${c.pedidos} pedidos cancelados ou devolvidos`;
  return (
    `Fora da receita: ${brl.format(c.valor)} em ${pedidos} no período. ` +
    "O “vendas brutas” do Mercado Livre soma esse valor à receita."
  );
}
