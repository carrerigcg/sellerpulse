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

                São três colunas no celular, não quatro: 283px não comportam
                quatro incluindo texto livre. Com quatro, a conta fechava e a
                leitura não — o SKU saía picado em "MLB1/0000/0" e o título
                quebrava no meio das palavras ("seguranç/a"). É o mesmo erro
                que a coluna de Receita evita ao não quebrar dentro do número,
                só que menos perigoso.

                Quem sai é o SKU, porque é identificador de máquina: no
                celular a pergunta é "qual produto, quanto rendeu, é A ou C?",
                e quem responde "qual produto" é o título. No desktop ele
                volta, que lá sobra espaço.

                Pisos medidos com dado real e `px-2`: Receita 85px
                ("R$ 138.747" numa linha) e Classe 62px (a palavra do
                cabeçalho não quebra). Sobra ~130px pro Título — perto de 16
                caracteres por linha, o bastante pra quebrar só nos espaços.
                Daí 46/31/23 = 100. */}
            <th className="hidden px-2 py-2 font-medium sm:table-cell sm:px-3">SKU</th>
            <th className="w-[46%] px-2 py-2 font-medium sm:w-auto sm:px-3">Título</th>
            <th className="w-[31%] px-2 py-2 font-medium text-right sm:w-auto sm:px-3">
              Receita
            </th>
            {/* Escondidas no celular pra que Receita e Classe — o que a tela
                existe pra mostrar — caibam sem rolar de lado. O selo A/B/C já
                diz o mesmo que as duas porcentagens, em uma coluna só. */}
            <th className="hidden px-3 py-2 font-medium text-right sm:table-cell">% receita</th>
            <th className="hidden px-3 py-2 font-medium text-right sm:table-cell">% acumulado</th>
            <th className="w-[23%] px-2 py-2 font-medium sm:w-auto sm:px-3">Classe</th>
          </tr>
        </thead>
        <tbody>
          {abc.map((linha) => (
            <tr key={linha.sku} className="border-t border-line">
              {/* Escondido no celular — ver o comentário no cabeçalho. Aqui
                  ele não leva `break-words`: na largura do desktop o SKU cabe
                  inteiro, e deixar a quebra disponível só convidaria a picar
                  o identificador se a coluna apertasse. */}
              <td className="hidden px-2 py-2 text-muted sm:table-cell sm:px-3">{linha.sku}</td>
              {/* Repetir o SKU como título é o que confunde: a coluna ao lado
                  já o mostra. Trocar pelo rótulo diz por que o nome falta. */}
              {/* O truncamento só vale a partir de `sm`, onde a coluna tem
                  largura de sobra. No celular o título quebra em linhas —
                  é o que permite a coluna ser estreita sem virar "Kit 3 Ca…".
                  `break-words` cobre SKU-título sem espaço, que não teria
                  onde quebrar e estouraria a célula estreita. */}
              {/* `title` porque a partir de `sm` esta célula trunca com
                  reticências, e aí o nome do produto fica inacessível. Com a
                  sidebar a tabela perdeu largura na faixa de 1280 a 1400 — em
                  1280, 7 dos 47 títulos passaram a truncar, contra nenhum
                  antes. Truncar é o comportamento desejado; perder o texto
                  não é. De 1440 pra cima nada trunca, como antes. */}
              <td
                title={linha.titulo}
                className="break-words px-2 py-2 sm:max-w-xs sm:truncate sm:px-3"
              >
                {anuncioFoiRemovido(linha) ? (
                  <>
                    <AnuncioRemovidoPill />
                    {/* Nessas linhas o título É o SKU, então a pílula ocupa o
                        lugar do nome e, com a coluna SKU escondida, a linha
                        ficaria sem identificador nenhum no celular. O SKU
                        embaixo da pílula resolve sem inventar coluna — e some
                        a partir de `sm`, onde a coluna SKU volta. */}
                    <span className="mt-1 block text-xs text-muted sm:hidden">{linha.sku}</span>
                  </>
                ) : (
                  linha.titulo
                )}
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
