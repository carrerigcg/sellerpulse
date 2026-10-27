import Link from "next/link";

import { BrowserFrame } from "./browser-frame";

/**
 * Seção "Da análise à ação" — onde as features novas entram.
 *
 * O ENQUADRAMENTO É A REGRA, não o estilo: cada item começa pela DOR, na voz
 * do vendedor, e a resposta vem pronta ao lado. Nenhum item se chama "Custo
 * de produto" ou "Exportação" — nome de funcionalidade transforma a seção num
 * catálogo, que é exatamente o que ela existe para não ser. Quem decidiu
 * assim foi o dono do produto, em voz alta: ninguém paga porque a ferramenta
 * tem funções boas, paga porque a dor foi entendida e a saída já está pronta.
 *
 * Por que uma seção nova em vez de somar telas ao `Showcase`: lá são as três
 * análises, e cada uma responde uma PERGUNTA. Custo, diagnóstico e exportação
 * não são perguntas — são o que a pessoa faz depois de ver a resposta. Somar
 * tudo lá daria cinco blocos simétricos e nenhum deles com peso.
 *
 * O print é da seção real de `/demo/produtos`, recortada pelo elemento
 * `#desempenho-anuncios` (ver `scripts/captura-prints.mjs`). Os números são
 * da demonstração navegável.
 *
 * Dois recortes, via `BrowserFrame`, pela razão que aquele componente já
 * documenta: esta é uma TABELA densa, e encolher o recorte de 1136px até
 * caber nos ~340px de um celular transforma as linhas num borrão cinza. Foi
 * exatamente o que apareceu na primeira versão desta seção. As dimensões
 * abaixo são as reais dos arquivos; mudar o recorte em
 * `captura-prints.mjs` exige mudar aqui, ou o Next reserva o espaço errado e
 * a página pula ao carregar.
 */

const DECISOES = [
  {
    dor: "“Esse anúncio é visto e não vende.”",
    resposta:
      "O SellerPulse separa os seus anúncios em quatro situações, comparando cada um com a mediana da sua própria loja — não com um número de internet, porque conversão boa de capacete não é conversão boa de cabo USB. E diz qual ação cabe em cada situação: mexer no anúncio, ou dar visibilidade a ele.",
    // A ressalva é argumento de venda, não rodapé: é ela que separa este
    // produto de um painel que carimba diagnóstico em cima de três visitas.
    ressalva:
      "Quando um anúncio não teve visita suficiente para a conta significar alguma coisa, ele diz isso — em vez de inventar um diagnóstico.",
  },
  {
    dor: "“Não sei quanto sobra de verdade.”",
    resposta:
      "Você informa quanto te custa cada produto, uma vez. A partir daí, cada venda nova desconta esse custo, e a margem deixa de ser receita menos comissão e passa a ser o que sobra de cada venda depois de pagar o produto.",
    ressalva:
      "E a tela mostra quanto da sua receita já tem custo informado, para você saber o quanto confiar na conta antes de decidir em cima dela.",
  },
  {
    dor: "“Preciso desses números fora daqui.”",
    resposta:
      "Toda tabela sai em CSV que abre no Excel sem quebrar acento nem embaralhar coluna, com um glossário explicando o que cada campo significa e como ele foi calculado.",
    ressalva: "Dá para baixar uma tabela de cada vez, ou todas de uma vez.",
  },
] as const;

export function Acoes() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <div className="max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
          Da análise à ação
        </p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Saber o número é metade. A outra metade é saber o que fazer com ele.
        </h2>
        <p className="mt-4 text-lg text-muted">
          Relatório bonito que não muda nenhuma decisão é só trabalho a mais. Estas
          três são as decisões que o SellerPulse já entrega prontas.
        </p>
      </div>

      <div className="mt-14 grid gap-10 lg:grid-cols-5 lg:gap-14">
        <div className="space-y-10 lg:col-span-2">
          {DECISOES.map((d) => (
            <div key={d.dor}>
              <p className="text-lg font-medium leading-snug text-ink">{d.dor}</p>
              <p className="mt-2 text-muted">{d.resposta}</p>
              <p className="mt-2 text-sm text-muted/80">{d.ressalva}</p>
            </div>
          ))}
        </div>

        <div className="lg:col-span-3">
          <BrowserFrame
            desktop={{ src: "/landing/demo-funil.png", width: 1136, height: 820 }}
            mobile={{ src: "/landing/demo-funil-mobile.png", width: 594, height: 900 }}
            alt="Seção Desempenho dos anúncios na demonstração: conversão mediana da loja, visitas do período, e uma tabela classificando cada anúncio entre visto e rejeitado, converte e falta ser visto, campeão e cauda."
          />
          <p className="mt-3 text-sm text-muted">
            Tela real da demonstração, com dados navegáveis agora —{" "}
            <Link
              href="/demo/produtos#desempenho-anuncios"
              className="font-medium text-accent hover:underline"
            >
              abrir sem cadastro
            </Link>
            .
          </p>
        </div>
      </div>
    </section>
  );
}
