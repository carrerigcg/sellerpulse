/**
 * Seletor de janela "de/até", usado por Executive, Produtos e Clientes — nas
 * duas versões, autenticada e pública.
 *
 * É um `<form>` sem `action`: submete GET pra própria URL da página, então
 * funciona igual em `/dashboard/produtos` e em `/demo/produtos` sem precisar
 * saber em qual das duas está. Movido pra cá no Checkpoint 2 da Sprint 3 —
 * era a mesma marcação copiada em três páginas.
 */
export function PeriodPicker({ de, ate }: { de: string; ate: string }) {
  return (
    <form className="flex items-end gap-2">
      <label className="text-xs text-muted">
        De
        <input
          type="date"
          name="de"
          defaultValue={de}
          className="mt-1 block rounded-lg border border-line px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>
      <label className="text-xs text-muted">
        Até
        <input
          type="date"
          name="ate"
          defaultValue={ate}
          className="mt-1 block rounded-lg border border-line px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>
      <button
        type="submit"
        className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-hover"
      >
        Aplicar
      </button>
    </form>
  );
}
