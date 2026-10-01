import Link from "next/link";

/**
 * Seção 5 — "feito para o Mercado Livre", tratado como vantagem. Esta é a
 * versão longa da linha discreta do herói: lá é uma frase de seis palavras
 * acima do título, aqui é o argumento inteiro. Ver decisão 5 da spec —
 * enquadrado como especialidade, nunca como selo de limitação.
 */

const VANTAGENS = [
  {
    titulo: "Taxas do Mercado Livre",
    texto:
      "Cada categoria tem uma comissão diferente. Ela já entra no cálculo da margem, sem você procurar tabela nenhuma.",
  },
  {
    // Aqui havia um card de "Frete" prometendo que o custo de envio entrava na
    // conta. Nao entrava: o `shipping_cost` que o ML manda no pedido vem null, e
    // o valor que aparece em `payments[].shipping_cost` e o frete que o COMPRADOR
    // pagou, nao custo do vendedor. Descoberto na primeira ingestao real. Volta
    // quando a API de shipments estiver integrada de verdade.
    titulo: "Histórico completo, sem digitar nada",
    texto:
      "Ao conectar, os últimos 6 meses de pedidos entram sozinhos — produtos e compradores já identificados.",
  },
  {
    titulo: "Cancelamentos e devoluções",
    texto: "Pedido cancelado não é receita. As reversões saem do resultado sozinhas.",
  },
] as const;

export function MlFocus() {
  return (
    <section className="border-y border-line bg-accent-soft/60 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
            Foco, não limite
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Feito para o Mercado Livre.
          </h2>
          <p className="mt-4 text-lg text-muted">
            Uma ferramenta que só precisa entender uma plataforma já chega sabendo a
            comissão de cada categoria e a regra de cancelamento — sem formulário de
            configuração, sem mapear categoria por categoria.
          </p>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-3">
          {VANTAGENS.map((v) => (
            <div key={v.titulo} className="rounded-xl border border-line bg-bg p-6 shadow-sm">
              <h3 className="text-base font-semibold text-ink">{v.titulo}</h3>
              <p className="mt-2 text-sm text-muted">{v.texto}</p>
            </div>
          ))}
        </div>

        <div className="mt-14">
          <Link
            href="/signup"
            className="rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-white transition hover:bg-accent-hover"
          >
            Criar conta grátis
          </Link>
        </div>
      </div>
    </section>
  );
}
