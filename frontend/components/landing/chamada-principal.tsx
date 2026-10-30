import Link from "next/link";

import { vitrineComVendasAbertas } from "@/lib/vendas";

/**
 * O botão principal das seções da vitrine. Com as vendas fechadas, leva à
 * demonstração: criar conta só levaria a pessoa a "as vendas abrem em breve".
 * Quem usa esconde o link secundário para a demo quando as vendas estão fechadas,
 * para a seção não ter dois botões iguais.
 */
export function ChamadaPrincipal({ className }: { className: string }) {
  return vitrineComVendasAbertas() ? (
    <Link href="/signup" className={className}>
      Criar conta grátis
    </Link>
  ) : (
    <Link href="/demo" className={className}>
      Ver demonstração
    </Link>
  );
}
