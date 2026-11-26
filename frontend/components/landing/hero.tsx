import Link from "next/link";
import { ChamadaPrincipal } from "@/components/landing/chamada-principal";
import { vitrineComVendasAbertas } from "@/lib/vendas";

import { FundoAnimado } from "./fundo-animado";
import { TextoDoHeroi } from "./texto-do-heroi";

/**
 * Seção 1 — herói. Fundo escuro de propósito: a cor da marca (laranja e
 * amarelo) é literalmente a cor do gráfico do fundo, e o resto do site é de
 * base branca — o contraste entre os dois é o que faz o herói parecer um
 * recorte, não um erro de tema. Ver `frontend/app/globals.css` para os
 * tokens; nenhum deles ganha variante escura, então o escuro aqui é
 * local a esta seção, não um modo.
 *
 * Duas camadas de fundo (spec `2026-11-25-vitrine-mcp-e-heroi`, seção 1): o
 * degradê radial do `<section>`, em CSS, que é o que fica sem JavaScript, e
 * por cima o canvas (`FundoAnimado`), que desenha a grade, as barras e a
 * linha da sobra. Página correta em qualquer ponto dessa cadeia.
 *
 * O painel atrás do texto usa `bg-ink/80` com `backdrop-blur` em vez de só
 * um gradiente por cima do fundo inteiro: o desenho é "visualmente barulhento"
 * (barras e linhas laranja/amarelo num grid quase preto), e texto branco
 * direto sobre uma barra clara do gráfico não bate contraste. Um painel
 * escuro sólido atrás do bloco de texto garante leitura em qualquer quadro
 * da animação — `ink` (#0f172a) a 80% sobre a cor mais clara do desenho (o
 * amarelo `#facc15`) ainda fecha acima de 4.5:1 pra texto branco, o pior
 * caso realista.
 */
export function Hero() {
  return (
    <section className="relative isolate overflow-hidden bg-[radial-gradient(ellipse_at_72%_35%,#3a1a08,#0b0f1a_70%)]">
      <div className="absolute inset-0 -z-10">
        <FundoAnimado />
        <div className="absolute inset-0 bg-gradient-to-r from-ink/60 to-transparent" />
      </div>

      <div className="mx-auto flex min-h-[85vh] max-w-6xl flex-col justify-center px-4 py-20 sm:px-6 sm:py-28">
        <div className="max-w-2xl rounded-2xl bg-ink/80 p-6 backdrop-blur-md sm:p-10">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/70">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-highlight" aria-hidden />
            Feito para o Mercado Livre
          </p>

          {/* A H1 nomeia QUATRO capacidades no subtítulo, nunca uma; e o
              subtítulo põe a lacuna no Mercado Livre, não em quem lê. O texto
              mora em `lib/escrita.ts` (motivo completo na spec de 2026-10-20). */}
          <TextoDoHeroi />

          <div className="mt-8 flex flex-wrap gap-4">
            <ChamadaPrincipal className="rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent/30 transition hover:bg-accent-hover" />
            {vitrineComVendasAbertas() && (
              <Link
                href="/demo"
                className="rounded-lg border border-white/30 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Ver demonstração
              </Link>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
