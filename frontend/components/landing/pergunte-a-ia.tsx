import { Suspense } from "react";

import { janelaAnterior } from "@/lib/api";
import { PERGUNTA_DA_CONVERSA, SEM_NUMEROS, respostaDaConversa } from "@/lib/conversa-da-demo";
import { getDemoFluxoFinanceiro } from "@/lib/demo";
import { periodoDoResumo } from "@/lib/periodo";

import { AparecerAoRolar } from "./aparece-ao-rolar";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const GARANTIAS = [
  "Só leitura: a IA vê os números, não mexe na sua conta.",
  "Passo a passo de conexão dentro do painel.",
  "Responde com os mesmos números das telas, e diz quando falta dado.",
];

// Cada item é uma função no ar (spec 2026-11-17-premium-de-volta-a-venda).
const PREMIUM = [
  { icone: "!", titulo: "Alertas no Resumo", texto: "Produto vendendo com prejuízo e anúncio que parou de vender, logo na primeira tela." },
  { icone: "3", titulo: "Até 3 contas", texto: "Cada conta do Mercado Livre separada, e a soma das três numa tela só." },
  { icone: "12", titulo: "12 meses de histórico", texto: "Um ano inteiro de vendas no painel, em vez de seis meses." },
  { icone: "6h", titulo: "Atualiza a cada 6 horas", texto: "Os números do dia chegam sem você precisar sincronizar." },
];

/**
 * "Pergunte ao Claude sobre a sua loja" — o MCP do Premium na vitrine, entre
 * "o que você faz com o que viu" (Acoes) e "como começar" (HowItWorks). Spec
 * `2026-11-25-vitrine-mcp-e-heroi`, seção 3.
 *
 * Só o Claude é citado: no ChatGPT o conector só existe nos planos
 * empresariais (mesma regra do cartão do Premium). A conversa usa a loja de
 * demonstração, nunca dado de vendedor.
 */
export function PergunteAIa() {
  return (
    <section id="ia" className="scroll-mt-20 border-t border-line py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid items-center gap-12 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-accent">
              Inteligência artificial
              <span className="rounded-full border border-accent/30 bg-accent-soft px-2.5 py-0.5 tracking-normal text-accent-hover">
                Premium
              </span>
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              Pergunte ao Claude sobre a sua loja.
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-muted">
              Conecte o SellerPulse ao Claude e pergunte em português, do jeito que você pergunta a
              um sócio: quanto sobrou, o que está parado, quem vale reconquistar.
            </p>
            <p className="mt-3 text-lg leading-relaxed text-muted">
              A IA não chuta: ela consulta os mesmos números do seu painel, calculados a partir dos
              seus pedidos reais.
            </p>
            <ul role="list" className="mt-6 space-y-3">
              {GARANTIAS.map((g) => (
                <li key={g} className="flex gap-3 text-ink">
                  <span aria-hidden="true" className="font-bold text-accent">
                    ✓
                  </span>
                  {g}
                </li>
              ))}
            </ul>
          </div>

          <AparecerAoRolar className="rounded-2xl border border-line bg-surface p-5 shadow-xl shadow-ink/10">
            <p className="text-sm text-muted">Claude · conectado ao SellerPulse</p>
            <p className="etapa-da-conversa ml-auto mt-4 w-fit max-w-[85%] rounded-2xl bg-line/60 px-4 py-2.5 text-ink">
              {PERGUNTA_DA_CONVERSA}
            </p>
            <p className="etapa-da-conversa mt-4 text-sm text-muted [transition-delay:600ms]">
              Consultou{" "}
              {/* Fundo tingido: o muted cai abaixo de 4,5:1 aqui, o slate-600 não. */}
              <code className="rounded bg-line/60 px-1.5 py-0.5 text-slate-600">fluxo_financeiro</code> no
              SellerPulse
            </p>
            {/* O fallback é a resposta sem números, na mesma etapa da conversa: sem
                JavaScript ele nunca é trocado, e uma espera eterna mentiria. */}
            <Suspense
              fallback={
                <p className="etapa-da-conversa mt-3 leading-relaxed text-ink [transition-delay:1200ms]">
                  {SEM_NUMEROS}
                </p>
              }
            >
              <RespostaDaDemo />
            </Suspense>
            <p className="etapa-da-conversa mt-4 text-xs text-muted [transition-delay:1800ms]">
              Exemplo com a loja de demonstração.
            </p>
          </AparecerAoRolar>
        </div>

        <ul
          role="list"
          className="mt-16 grid gap-6 rounded-2xl border border-line bg-surface/60 p-6 sm:grid-cols-2 lg:grid-cols-4"
        >
          {PREMIUM.map((p) => (
            <li key={p.titulo}>
              <span
                aria-hidden="true"
                className="grid h-9 w-9 place-items-center rounded-lg bg-accent-soft font-bold text-accent-hover"
              >
                {p.icone}
              </span>
              <p className="mt-3 font-semibold text-ink">{p.titulo}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted">{p.texto}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Busca a demo; com o Render frio isso leva ~25 s, por isso mora no Suspense. */
async function RespostaDaDemo() {
  const periodo = periodoDoResumo();
  const [antDe, antAte] = janelaAnterior(periodo.de, periodo.ate);
  const [atual, anterior] = await Promise.allSettled([
    getDemoFluxoFinanceiro(periodo.de, periodo.ate),
    getDemoFluxoFinanceiro(antDe, antAte),
  ]);
  const r = respostaDaConversa(
    atual.status === "fulfilled" ? atual.value : null,
    anterior.status === "fulfilled" ? anterior.value : null,
  );

  return (
    <div className="etapa-da-conversa mt-3 leading-relaxed text-ink [transition-delay:1200ms]">
      <p>{r.frase}</p>
      {r.linhas && (
        <table className="mt-2 text-sm">
          <tbody>
            {r.linhas.map((l, i) => (
              <tr key={l.rotulo}>
                <td className="py-0.5 pr-6">{l.rotulo}</td>
                <td className="tabular py-0.5 text-right">
                  {/* Ausência não é zero: sem valor, a nota no lugar do número.
                      Com valor parcial, a nota junto, senão o número parece completo. */}
                  {l.valor === null
                    ? (l.nota ?? "não informado")
                    : `${i === 0 ? "" : "− "}${brl.format(l.valor)}${l.nota ? ` (${l.nota})` : ""}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {r.avisos.map((a) => (
        <p key={a} className="mt-2">
          {a}
        </p>
      ))}
      {r.fecho && <p className="mt-2">{r.fecho}</p>}
    </div>
  );
}
