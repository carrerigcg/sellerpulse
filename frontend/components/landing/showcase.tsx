import Link from "next/link";

import { BrowserFrame } from "./browser-frame";

/**
 * Seção 3 — as três análises, com prints reais de `/demo`, `/demo/produtos`
 * e `/demo/clientes` (capturados da própria demonstração rodando local
 * contra o seller semeado `is_demo = true`). Nenhum número aqui é
 * fabricado: é o mesmo dado que qualquer visitante vê ao clicar em "ver
 * tela completa".
 *
 * Cada tela tem dois recortes (`desktop`/`mobile`, ver `browser-frame.tsx`
 * pro porquê de dois arquivos em vez de um só encolhido por CSS).
 * Largura/altura é a dimensão real de cada arquivo em `public/landing/` —
 * o Next usa isso pra reservar o espaço e evitar CLS. As alturas variam
 * entre telas porque cada uma tem uma quantidade diferente de conteúdo.
 */

const TELAS = [
  {
    titulo: "Executive",
    pergunta: "Quanto sobrou de verdade este mês, depois da comissão do Mercado Livre?",
    desktop: { src: "/landing/demo-executive.png", width: 1104, height: 556 },
    mobile: { src: "/landing/demo-executive-mobile.png", width: 602, height: 757 },
    href: "/demo",
  },
  {
    titulo: "Produtos",
    pergunta: "Quais produtos sustentam o faturamento — e quais só ocupam espaço?",
    desktop: { src: "/landing/demo-produtos.png", width: 1104, height: 706 },
    mobile: { src: "/landing/demo-produtos-mobile.png", width: 602, height: 744 },
    href: "/demo/produtos",
  },
  {
    titulo: "Clientes",
    pergunta: "Quem compra de novo, e quem já foi embora sem avisar?",
    desktop: { src: "/landing/demo-clientes.png", width: 1104, height: 940 },
    mobile: { src: "/landing/demo-clientes-mobile.png", width: 602, height: 1200 },
    href: "/demo/clientes",
  },
] as const;

export function Showcase() {
  return (
    <section className="border-t border-line bg-surface/50 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Três telas, três perguntas respondidas.
          </h2>
          <p className="mt-4 text-lg text-muted">
            Nada aqui é maquete — são as telas reais, com dados de demonstração
            navegáveis agora, sem cadastro.
          </p>
        </div>

        <div className="mt-16 space-y-20 sm:mt-20 sm:space-y-24">
          {TELAS.map((tela, i) => (
            <div
              key={tela.titulo}
              className="grid gap-6 lg:grid-cols-5 lg:items-center lg:gap-12"
            >
              <div className={`lg:col-span-2 ${i % 2 ? "lg:order-2" : ""}`}>
                <span className="text-sm font-semibold uppercase tracking-wide text-accent">
                  {tela.titulo}
                </span>
                <p className="mt-3 text-xl font-medium leading-snug text-ink">
                  {tela.pergunta}
                </p>
                <Link
                  href={tela.href}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
                >
                  Ver tela completa →
                </Link>
              </div>
              <div className={`lg:col-span-3 ${i % 2 ? "lg:order-1" : ""}`}>
                <BrowserFrame
                  desktop={tela.desktop}
                  mobile={tela.mobile}
                  alt={`Tela de ${tela.titulo} do SellerPulse, com dados de demonstração`}
                />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-16 flex flex-wrap items-center gap-x-6 gap-y-4 border-t border-line pt-10 sm:mt-20">
          <Link
            href="/signup"
            className="rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-white transition hover:bg-accent-hover"
          >
            Criar conta grátis
          </Link>
          <Link href="/demo" className="text-sm font-semibold text-ink hover:text-accent">
            ou continue explorando a demonstração →
          </Link>
        </div>
      </div>
    </section>
  );
}
