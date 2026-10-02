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
    // Em linha única o formulário mede 400px e, numa tela de 375, o "Aplicar"
    // era cortado ao meio — o seletor virava decoração, porque dava pra mudar
    // as datas e não dava pra aplicar. Com `flex-wrap` o botão desce inteiro
    // pra linha de baixo quando não cabe. `w-full` no celular pra que os dois
    // campos dividam a linha em medidas iguais em vez de dependerem do
    // encolhimento; `sm:w-auto` devolve a largura natural no desktop.
    <form className="flex w-full flex-wrap items-end gap-2 sm:w-auto">
      {/* NÃO troque `basis-2/5` por `flex-1` nem tire a base achando que o
          `flex-wrap` sozinho resolve — o defeito que isso traz de volta não
          aparece em medição.

          Com os três itens na mesma linha os campos caem pra 120px e o
          `<input type="date">` corta o ano na tela ("04/07/202"), mas
          reporta `scrollWidth` 118 contra 120 de largura: o controle nativo
          esconde o próprio excesso por dentro, então nenhuma verificação de
          overflow acusa nada. Só a captura de tela pega. Os ~151px de que
          ele precisa pra mostrar a data inteira são a medida que vale.

          `basis-2/5` é o que força a quebra: com 40% de base cada, os dois
          campos mais o botão não cabem numa linha, o botão desce e as datas
          crescem pra 160px. `grow` em vez de `flex-1` porque `flex-1` zera o
          `basis` e desfaria exatamente essa conta. `min-w-0` + `w-full` no
          input porque a largura intrínseca do campo de data ignora o
          encolhimento do flex sozinha. */}
      <label className="min-w-0 grow basis-2/5 text-xs text-muted sm:grow-0 sm:basis-auto">
        De
        <input
          type="date"
          name="de"
          defaultValue={de}
          className="mt-1 block w-full rounded-lg border border-line px-2.5 py-1.5 text-sm outline-none focus:border-accent sm:w-auto"
        />
      </label>
      <label className="min-w-0 grow basis-2/5 text-xs text-muted sm:grow-0 sm:basis-auto">
        Até
        <input
          type="date"
          name="ate"
          defaultValue={ate}
          className="mt-1 block w-full rounded-lg border border-line px-2.5 py-1.5 text-sm outline-none focus:border-accent sm:w-auto"
        />
      </label>
      <button
        type="submit"
        className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-hover"
      >
        Aplicar
      </button>
    </form>
  );
}
