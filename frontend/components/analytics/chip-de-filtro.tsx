/**
 * Chip de filtro de lista — Desempenho dos anúncios e a tabela de compradores.
 *
 * `aria-pressed` porque as duas listas podem abrir já filtradas, vindas de um
 * cartão do Resumo: quem usa leitor de tela precisa ouvir que está vendo só
 * uma parte.
 */
export function ChipDeFiltro({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={ativo}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${
        ativo
          ? "border-accent bg-accent-soft font-medium text-accent-hover"
          : "border-line text-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
