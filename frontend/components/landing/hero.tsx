import Image from "next/image";
import Link from "next/link";

import { HeroVideo } from "./hero-video";

/**
 * Seção 1 — herói. Fundo escuro de propósito: a cor da marca (laranja e
 * amarelo) é literalmente a cor do gráfico do vídeo, e o resto do site é de
 * base branca — o contraste entre os dois é o que faz o herói parecer um
 * recorte, não um erro de tema. Ver `frontend/app/globals.css` para os
 * tokens; nenhum deles ganha variante escura, então o escuro aqui é
 * local a esta seção, não um modo.
 *
 * Três camadas de fundo, nessa ordem: `--sp-bg` como cor de fallback no
 * `<section>`, o poster (`next/image`, sempre presente, com `priority`
 * porque é o maior elemento acima da dobra) e o vídeo (`HeroVideo`, opt-in
 * no cliente). Página correta em qualquer ponto dessa cadeia.
 *
 * O painel atrás do texto usa `bg-ink/80` com `backdrop-blur` em vez de só
 * um gradiente por cima do vídeo inteiro: a imagem é "visualmente barulhenta"
 * (barras e linhas laranja/amarelo num grid quase preto), e texto branco
 * direto sobre uma barra clara do gráfico não bate contraste. Um painel
 * escuro sólido atrás do bloco de texto garante leitura em qualquer frame
 * do vídeo, não só no frame do poster — `ink` (#0f172a) a 80% sobre a cor
 * mais clara do vídeo (o amarelo `#facc15`) ainda fecha acima de 4.5:1 pra
 * texto branco, o pior caso realista.
 */
export function Hero() {
  return (
    <section className="relative isolate overflow-hidden bg-ink">
      <div className="absolute inset-0 -z-10">
        <Image
          src="/hero/heroi.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover opacity-90"
        />
        <HeroVideo />
        <div className="absolute inset-0 bg-gradient-to-t from-ink via-ink/60 to-ink/20" />
      </div>

      <div className="mx-auto flex min-h-[85vh] max-w-6xl flex-col justify-center px-4 py-20 sm:px-6 sm:py-28">
        <div className="max-w-2xl rounded-2xl bg-ink/80 p-6 backdrop-blur-md sm:p-10">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/70">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-highlight" aria-hidden />
            Feito para o Mercado Livre
          </p>

          <h1 className="mt-4 text-4xl font-semibold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-6xl">
            O lucro da sua loja, <span className="text-accent">calculado</span> — não
            estimado.
          </h1>

          <p className="mt-6 text-lg text-white/80">
            Receita, produtos e clientes a partir dos seus pedidos reais no Mercado
            Livre. Taxa, frete e cancelamento já entram na conta.
          </p>

          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href="/signup"
              className="rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent/30 transition hover:bg-accent-hover"
            >
              Criar conta grátis
            </Link>
            <Link
              href="/demo"
              className="rounded-lg border border-white/30 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              Ver demonstração
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
