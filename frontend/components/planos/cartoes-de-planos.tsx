import Link from "next/link";

import { WHATSAPP_DE_CONTATO, linkDeEmail, linkDeWhatsapp } from "@/lib/contato";
import type { NomeDoPlano } from "@/lib/plano";
import {
  DIAS_DE_TESTE,
  PLANO_COM_TESTE,
  PRECOS_DEPOIS_DO_LANCAMENTO,
  PRECOS_MENSAIS,
  descontoDeLancamento,
  economiaMensal,
  formatarPreco,
  precoAnual,
} from "@/lib/precos";

/**
 * Os três planos, em cartões. Usado pela página `/planos` e pela seção de
 * preços da vitrine: um só lugar, para as duas nunca prometerem coisas
 * diferentes.
 *
 * O que cada plano libera de verdade é decidido no backend
 * (`backend/planos.py`). Esta lista descreve aquilo; mudar uma sem a outra é
 * prometer o que o produto não entrega. O Exclusive é o recomendado e o mais
 * destacado, no centro (spec `docs/specs/2026-10-28-planos-e-acesso-design.md`).
 *
 * Os preços moram em `lib/precos.ts`, que o backend confere contra o que ele
 * cobra. "Assinar" leva à contratação (`/assinar`); o contato fica para quem
 * quer tirar dúvida antes.
 *
 * Promoção de lançamento: o preço de depois aparece riscado, como ÂNCORA, ao
 * lado do de agora, com o desconto e a economia em reais. O riscado é dito
 * como o preço depois do lançamento, nunca como um "de" que já foi cobrado
 * (ver `PRECOS_DEPOIS_DO_LANCAMENTO`).
 */

type Plano = {
  chave: NomeDoPlano;
  nome: string;
  chamada: string;
  itens: string[];
  depois?: { titulo: string; itens: string[] };
  destaque?: boolean;
};

const PLANOS: Plano[] = [
  {
    chave: "essencial",
    nome: "Essencial",
    chamada: "Para saber quanto sobra de cada venda.",
    itens: [
      "Resumo da loja",
      "Financeiro: margem, comissão, frete e cancelamentos",
      "Custo dos produtos",
      "Curva ABC: os 10 produtos que mais faturam",
      "Histórico de 3 meses",
      "Atualização diária",
      "Suporte por e-mail",
    ],
  },
  {
    chave: "exclusive",
    nome: "Exclusive",
    chamada: "O painel inteiro, para decidir com a loja toda à vista.",
    destaque: true,
    itens: [
      "Tudo do Essencial",
      "Curva ABC completa",
      "Anúncios vistos que não vendem",
      "Clientes: quem compra de novo e quem está sumindo",
      "Cohort de lançamento",
      "Exportar para planilha",
      "Histórico de 6 meses",
      "Sincronizar na hora",
      "Suporte prioritário",
    ],
  },
  {
    chave: "premium",
    nome: "Premium",
    chamada: "Para quem quer o máximo do produto e alguém do lado.",
    itens: ["Tudo do Exclusive", "Gerente de conta dedicado"],
    depois: {
      titulo: "Em construção para o Premium",
      itens: [
        "Pergunte sobre a sua loja a uma IA (Claude, ChatGPT)",
        "Alertas de margem negativa e anúncio parado",
        "Várias contas do Mercado Livre num painel só",
        "Histórico de 12 meses",
      ],
    },
  },
];

export function CartoesDePlanos() {
  const maiorDesconto = Math.max(...PLANOS.map((p) => descontoDeLancamento(p.chave)));
  return (
    <>
      {/* A promessa de manter o preço é verdade pelo jeito que a cobrança
          funciona: a assinatura mensal no Asaas guarda o valor do dia em que
          foi criada, e um aumento só vale para quem assina depois. Ela NÃO
          vale para o anual (pagamento único, que se recontrata pelo preço do
          dia) nem para a troca de plano (que usa a tabela vigente) — por isso
          o texto diz "mensal" e "mesmo plano". */}
      <div className="mb-8 rounded-xl border border-accent/40 bg-accent-soft px-4 py-3 text-sm text-ink">
        <span className="font-semibold">Preço de lançamento:</span> até {maiorDesconto}% a menos
        para quem assina agora. No plano mensal, você mantém este preço enquanto continuar no
        mesmo plano.
      </div>
      <div className="grid gap-6 md:grid-cols-3 md:items-stretch">
        {PLANOS.map((plano) => (
          <CartaoDoPlano key={plano.nome} plano={plano} />
        ))}
      </div>
    </>
  );
}

function CartaoDoPlano({ plano }: { plano: Plano }) {
  const mensagem = `Olá! Tenho uma dúvida sobre o plano ${plano.nome} do SellerPulse.`;
  const temTeste = plano.chave === PLANO_COM_TESTE;
  return (
    <section
      className={`relative flex flex-col rounded-2xl border p-6 ${
        plano.destaque
          ? "order-first border-accent bg-accent-soft shadow-lg md:order-none md:-my-3 md:py-9"
          : "border-line bg-bg"
      }`}
    >
      {plano.destaque && (
        <span className="absolute -top-3 left-6 rounded-full bg-accent px-3 py-1 text-xs font-semibold text-white">
          Recomendado
        </span>
      )}
      <h3 className="text-xl font-semibold">{plano.nome}</h3>
      <p className="mt-1 text-sm text-muted">{plano.chamada}</p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {/* O rótulo fica VISÍVEL: sem ele, o riscado se lê como um "de" que
            já foi cobrado, e é exatamente isso que o CDC (art. 37) proíbe. */}
        <span className="text-xs text-muted">
          depois do lançamento: <s>{formatarPreco(PRECOS_DEPOIS_DO_LANCAMENTO[plano.chave])}</s>
        </span>
        <span className="rounded-full border border-positive/40 bg-positive/10 px-2 py-0.5 text-xs font-semibold text-ink">
          −{descontoDeLancamento(plano.chave)}%
        </span>
      </div>
      <p>
        <span className="text-3xl font-semibold tracking-tight">
          {formatarPreco(PRECOS_MENSAIS[plano.chave])}
        </span>
        <span className="text-sm text-muted">/mês</span>
      </p>
      <p className="mt-1 text-xs text-muted">
        Preço de lançamento: {formatarPreco(economiaMensal(plano.chave))} a menos por mês
      </p>
      <p className="mt-1 text-xs text-muted">
        ou {formatarPreco(precoAnual(plano.chave))} por ano (2 meses grátis)
      </p>
      {temTeste && (
        <p className="mt-2 inline-flex w-fit rounded-full border border-accent px-2.5 py-0.5 text-xs font-semibold text-accent">
          {DIAS_DE_TESTE} dias grátis no mensal
        </p>
      )}

      <ul className="mt-5 flex-1 space-y-2 text-sm">
        {plano.itens.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden className="text-accent">
              ✓
            </span>
            {item}
          </li>
        ))}
      </ul>

      {plano.depois && (
        <div className="mt-5 border-t border-line pt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {plano.depois.titulo}
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-muted">
            {plano.depois.itens.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 flex flex-col gap-2">
        <Link
          href={`/assinar?plano=${plano.chave}`}
          className={`rounded-lg px-4 py-2 text-center text-sm font-medium transition ${
            plano.destaque
              ? "bg-accent text-white hover:bg-accent-hover"
              : "border border-line hover:bg-surface"
          }`}
        >
          {temTeste ? `Testar ${DIAS_DE_TESTE} dias grátis` : `Assinar o ${plano.nome}`}
        </Link>
        <a
          href={
            WHATSAPP_DE_CONTATO
              ? linkDeWhatsapp(WHATSAPP_DE_CONTATO, mensagem)
              : linkDeEmail(`Dúvida sobre o plano ${plano.nome}`)
          }
          target={WHATSAPP_DE_CONTATO ? "_blank" : undefined}
          rel={WHATSAPP_DE_CONTATO ? "noopener noreferrer" : undefined}
          className="inline-flex min-h-11 items-center justify-center text-xs text-muted underline hover:text-accent"
        >
          Tirar dúvidas {WHATSAPP_DE_CONTATO ? "no WhatsApp" : "por e-mail"}
        </a>
      </div>
    </section>
  );
}
