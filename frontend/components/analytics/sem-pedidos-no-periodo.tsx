import Link from "next/link";

/**
 * Estado vazio das telas do dashboard: nada no período, e o atalho para
 * conectar a conta do Mercado Livre.
 *
 * O atalho está aqui porque, para quem acabou de criar conta, "nenhum pedido"
 * quase sempre significa "nenhuma conta conectada" — e o estado vazio é a tela
 * mais provável no começo da vida de um usuário novo.
 *
 * Só no dashboard: a demo tem dado sintético sempre corrente e não oferece
 * conexão de conta.
 */
export function SemPedidosNoPeriodo({ mensagem }: { mensagem: string }) {
  return (
    <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
      {mensagem}{" "}
      <Link href="/dashboard/conectar" className="text-accent underline hover:text-accent-hover">
        Conectar uma conta do Mercado Livre
      </Link>
      .
    </p>
  );
}
