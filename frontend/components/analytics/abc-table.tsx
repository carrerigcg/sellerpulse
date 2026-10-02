import type { AbcLinha } from "@/lib/api";

import { abcClassBadgeClass } from "./abc-class-badge";
import { AnuncioRemovidoPill, anuncioFoiRemovido } from "./anuncio-removido";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const pct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

/** Tabela por produto — sku, título, receita, participação, classe. */
export function AbcTable({ abc }: { abc: AbcLinha[] }) {
  return (
    // `overflow-x-auto` explícito: `overflow-y-auto` já forçava o eixo X pra
    // `auto` por regra da spec, então a rolagem lateral existia por efeito
    // colateral. Declarada, ela fica no código em vez de herdada por acidente
    // — e abaixo de `sm` ela deixa de ser o caminho normal pra virar rede de
    // segurança, pras telas ainda menores que 375.
    <div className="mt-4 max-h-[28rem] overflow-x-auto overflow-y-auto rounded-lg border border-line">
      {/* `table-fixed` abaixo de `sm` porque a largura automática era o
          problema: o Título reservava 320px (o teto do `max-w-xs`) mesmo
          truncando, e empurrava Receita e Classe pra fora da tela. Com
          larguras proporcionais as quatro colunas cabem, e o Título passa a
          quebrar em duas ou três linhas em vez de truncar. A troca é
          deliberada: altura é barata num celular, largura não.
          `sm:table-auto` devolve o dimensionamento automático no desktop. */}
      <table className="w-full table-fixed text-left text-sm sm:table-auto">
        <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            {/* O orçamento NÃO é a largura útil da página (325px): a tabela
                mora dentro de um cartão com `p-5`, então sobram 283px. Medir
                contra 325 foi o que deixou passar sete receitas cortadas.

                Só duas colunas têm piso de verdade, medido com dado real do
                vendedor de demonstração e `px-2`: Receita 83px ("R$ 138.747"
                numa linha só, e sem `break-words` ela não pode quebrar dentro
                do número) e Classe 59px (a palavra do cabeçalho não quebra, e
                a etiqueta A/B/C é menor que ela). São 142px travados. SKU e
                Título dividem os 141 que sobram, e os dois são elásticos
                porque quebram em linhas. Daí 19/29/30/22 = 100.

                As folgas ficam em 2 ou 3px por coluna, que é exatamente onde
                conta de cabeça passa despercebida: mexer numa porcentagem
                aqui exige medir de novo (maior `scrollWidth` de cada coluna
                contra o `clientWidth`), não estimar. */}
            <th className="w-[19%] px-2 py-2 font-medium sm:w-auto sm:px-3">SKU</th>
            <th className="w-[29%] px-2 py-2 font-medium sm:w-auto sm:px-3">Título</th>
            <th className="w-[30%] px-2 py-2 font-medium text-right sm:w-auto sm:px-3">
              Receita
            </th>
            {/* Escondidas no celular pra que Receita e Classe — o que a tela
                existe pra mostrar — caibam sem rolar de lado. O selo A/B/C já
                diz o mesmo que as duas porcentagens, em uma coluna só. */}
            <th className="hidden px-3 py-2 font-medium text-right sm:table-cell">% receita</th>
            <th className="hidden px-3 py-2 font-medium text-right sm:table-cell">% acumulado</th>
            <th className="w-[22%] px-2 py-2 font-medium sm:w-auto sm:px-3">Classe</th>
          </tr>
        </thead>
        <tbody>
          {abc.map((linha) => (
            <tr key={linha.sku} className="border-t border-line">
              {/* O SKU é um token só ("MLB-4471239988"): sem `break-words`
                  ele não teria onde quebrar e estouraria a coluna estreita. */}
              <td className="break-words px-2 py-2 text-muted sm:px-3">{linha.sku}</td>
              {/* Repetir o SKU como título é o que confunde: a coluna ao lado
                  já o mostra. Trocar pelo rótulo diz por que o nome falta. */}
              {/* O truncamento só vale a partir de `sm`, onde a coluna tem
                  largura de sobra. No celular o título quebra em linhas —
                  é o que permite a coluna ser estreita sem virar "Kit 3 Ca…".
                  `break-words` cobre SKU-título sem espaço, que não teria
                  onde quebrar e estouraria a célula estreita. */}
              <td className="break-words px-2 py-2 sm:max-w-xs sm:truncate sm:px-3">
                {anuncioFoiRemovido(linha) ? <AnuncioRemovidoPill /> : linha.titulo}
              </td>
              {/* Sem `break-words` aqui, de propósito: com ele uma receita de
                  7 dígitos quebrava DENTRO do número ("R$ 1.299.45" / "0"),
                  que não é feio, é errado — lido rápido vira outro valor. Sem
                  ele a quebra só acontece no espaço depois do "R$", e um valor
                  raro de 7 dígitos avança alguns pixels em vez de mentir. */}
              <td className="tabular px-2 py-2 text-right sm:px-3">{brl.format(linha.receita)}</td>
              <td className="tabular hidden px-3 py-2 text-right sm:table-cell">
                {pct.format(linha.receita_pct)}%
              </td>
              <td className="tabular hidden px-3 py-2 text-right sm:table-cell">
                {pct.format(linha.receita_acumulada_pct)}%
              </td>
              <td className="px-2 py-2 sm:px-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${abcClassBadgeClass(linha.classe)}`}
                >
                  {linha.classe}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
