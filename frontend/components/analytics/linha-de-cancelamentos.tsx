import { fraseDosCancelamentos, type Cancelamentos } from "@/lib/cancelamentos";

/**
 * A linha que fecha a conta contra o "vendas brutas" do Mercado Livre.
 *
 * Informação, não alerta: a receita está certa, só mede outra coisa que o
 * painel do ML. Por isso o tom neutro, e não o amarelo dos avisos de
 * cobertura, que dizem que a margem está incompleta.
 */
export function LinhaDeCancelamentos({ cancelamentos }: { cancelamentos: Cancelamentos | null }) {
  const frase = fraseDosCancelamentos(cancelamentos);
  if (!frase) return null;
  return <p className="tabular mt-3 text-xs leading-relaxed text-muted">{frase}</p>;
}
