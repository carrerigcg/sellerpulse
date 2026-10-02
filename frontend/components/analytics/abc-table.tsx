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
    // colateral. Declarada, ela fica no código em vez de herdada por acidente.
    // `overflow-x-auto` explícito: `overflow-y-auto` já forçava o eixo X pra
    // `auto` por regra da spec, então a rolagem lateral existia por efeito
    // colateral. Declarada, ela fica no código em vez de herdada por acidente
    // — e abaixo de `sm` ela deixa de ser o caminho normal pra virar rede de
    // segurança, pras telas ainda menores que 375.
    <div className="mt-4 max-h-[28rem] overflow-x-auto overflow-y-auto rounded-lg border border-line">
      {/* `table-fixed` abaixo de `sm` porque a largura automática era o
          problema: o Título reservava 320px dos 325 disponíveis (o teto do
          `max-w-xs`) mesmo truncando, e empurrava Receita e Classe pra fora
          da tela. Com larguras proporcionais as quatro colunas cabem, e o
          Título passa a quebrar em duas ou três linhas em vez de truncar.
          A troca é deliberada: altura é barata num celular, largura não.
          `sm:table-auto` devolve o dimensionamento automático no desktop. */}
      <table className="w-full table-fixed text-left text-sm sm:table-auto">
        <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-muted">
          <tr>
            {/* Porcentagens medidas, não chutadas, sobre os 325px úteis em
                375. O piso de cada coluna é o maior pedaço indivisível mais
                os 24px de padding: "Classe" 72px (a palavra não quebra, e a
                etiqueta A/B/C é menor que ela), "184.320" 76px. O Título leva
                a maior fatia porque é o único texto de verdade aqui — com 104px
                cabem palavras como "Masculina" sem partir no meio. O SKU leva
                a menor porque quebrar um identificador em duas ou três linhas
                custa pouco: ele continua inteiro e legível. 22+30+25+23 = 100. */}
            <th className="w-[22%] px-3 py-2 font-medium sm:w-auto">SKU</th>
            <th className="w-[30%] px-3 py-2 font-medium sm:w-auto">Título</th>
            <th className="w-[25%] px-3 py-2 font-medium text-right sm:w-auto">Receita</th>
            {/* Escondidas no celular pra que Receita e Classe — o que a tela
                existe pra mostrar — caibam sem rolar de lado. O selo A/B/C já
                diz o mesmo que as duas porcentagens, em uma coluna só. */}
            <th className="hidden px-3 py-2 font-medium text-right sm:table-cell">% receita</th>
            <th className="hidden px-3 py-2 font-medium text-right sm:table-cell">% acumulado</th>
            <th className="w-[23%] px-3 py-2 font-medium sm:w-auto">Classe</th>
          </tr>
        </thead>
        <tbody>
          {abc.map((linha) => (
            <tr key={linha.sku} className="border-t border-line">
              {/* O SKU é um token só ("MLB-4471239988"): sem `break-words`
                  ele não teria onde quebrar e estouraria a coluna estreita. */}
              <td className="break-words px-3 py-2 text-muted">{linha.sku}</td>
              {/* Repetir o SKU como título é o que confunde: a coluna ao lado
                  já o mostra. Trocar pelo rótulo diz por que o nome falta. */}
              {/* O truncamento só vale a partir de `sm`, onde a coluna tem
                  largura de sobra. No celular o título quebra em linhas —
                  é o que permite a coluna ser estreita sem virar "Kit 3 Ca…".
                  `break-words` cobre SKU-título sem espaço, que não teria
                  onde quebrar e estouraria a célula estreita. */}
              <td className="break-words px-3 py-2 sm:max-w-xs sm:truncate">
                {anuncioFoiRemovido(linha) ? <AnuncioRemovidoPill /> : linha.titulo}
              </td>
              {/* Sem `break-words` aqui, de propósito: com ele uma receita de
                  7 dígitos quebrava DENTRO do número ("R$ 1.299.45" / "0"),
                  que não é feio, é errado — lido rápido vira outro valor. Sem
                  ele a quebra só acontece no espaço depois do "R$", e um valor
                  raro de 7 dígitos avança alguns pixels em vez de mentir. */}
              <td className="tabular px-3 py-2 text-right">{brl.format(linha.receita)}</td>
              <td className="tabular hidden px-3 py-2 text-right sm:table-cell">
                {pct.format(linha.receita_pct)}%
              </td>
              <td className="tabular hidden px-3 py-2 text-right sm:table-cell">
                {pct.format(linha.receita_acumulada_pct)}%
              </td>
              <td className="px-3 py-2">
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
