import type { AbcLinha } from "@/lib/api";

/**
 * O backend monta o título com `COALESCE(ic.title, oi.item_id)`: quando o
 * anúncio foi apagado no Mercado Livre não sobra linha em `items_cache`, e o
 * título cai no próprio item_id. Logo `titulo === sku` identifica exatamente
 * essas linhas — não é heurística, é o único jeito de os dois campos serem
 * iguais. Detectar aqui no front evita um campo novo na API só para dizer
 * algo que o dado já diz.
 *
 * O caso é normal, não é erro: o pedido aconteceu, a receita é real, só o
 * anúncio não existe mais. Daí o rótulo neutro — sem laranja (que neste
 * produto significa ação) e sem cor de alerta.
 */
export function anuncioFoiRemovido(linha: AbcLinha): boolean {
  return linha.titulo === linha.sku;
}

/** Texto do rótulo, num lugar só — a pílula e o tooltip usam o mesmo. */
const ROTULO = "anúncio removido";

/** Frase inteira no `title`: explica sem ocupar espaço nenhum na tela. */
const EXPLICACAO = "Este anúncio não existe mais no Mercado Livre. A venda e a receita são reais.";

/**
 * Entra no lugar do título repetido NA TABELA, onde o fundo é branco e a
 * borda da pílula de fato a delimita.
 *
 * O `whitespace-nowrap` agora só vale a partir de `sm`. Ele existia pra
 * impedir que as duas palavras quebrassem, mas desde que a coluna Título
 * passou a ter largura proporcional no celular (ver `abc-table.tsx`) ele
 * virava o problema: medida inteira a pílula ocupa 139px contra os ~91px da
 * coluna, e sem poder quebrar ela estourava a célula. No celular ela quebra
 * em duas linhas; da borda pra cima nada muda.
 *
 * Não serve pro tooltip do Pareto: lá o container já é `bg-surface`, então o
 * preenchimento da pílula fica na mesma cor do fundo (contraste 1,00:1) e
 * sobra só a borda, que lida como artefato de renderização. Ali usa-se
 * `TextoAnuncioRemovido`.
 */
export function AnuncioRemovidoPill() {
  return (
    <span
      title={EXPLICACAO}
      className="inline-block break-words rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-muted sm:whitespace-nowrap"
    >
      {ROTULO}
    </span>
  );
}

/** A mesma informação sem a pílula, pra quando o fundo já é `bg-surface`. */
export function TextoAnuncioRemovido() {
  return (
    <p title={EXPLICACAO} className="text-muted">
      {ROTULO}
    </p>
  );
}
