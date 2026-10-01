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
export function anuncioRemovido(linha: AbcLinha): boolean {
  return linha.titulo === linha.sku;
}

/**
 * Entra no lugar do título repetido. Fica no mesmo registro visual da classe
 * C (`bg-surface text-muted border border-line`), que é o tom mais apagado
 * já existente; `whitespace-nowrap` impede que as duas palavras quebrem a
 * célula da tabela na largura de celular.
 */
export function AnuncioRemovidoPill() {
  return (
    <span className="inline-block whitespace-nowrap rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-muted">
      anúncio removido
    </span>
  );
}
