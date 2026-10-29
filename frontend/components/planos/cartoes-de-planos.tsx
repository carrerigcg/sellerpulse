import {
  EMAIL_DE_CONTATO,
  WHATSAPP_DE_CONTATO,
  linkDeEmail,
  linkDeWhatsapp,
} from "@/lib/contato";

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
 * `preco` fica `null` até o preço ser decidido: o cartão diz "Sob consulta",
 * e não um número que ninguém escolheu.
 */

type Plano = {
  nome: string;
  /** Por mês, em reais. `null` = ainda não definido. */
  preco: number | null;
  chamada: string;
  itens: string[];
  depois?: { titulo: string; itens: string[] };
  destaque?: boolean;
};

const PLANOS: Plano[] = [
  {
    nome: "Essencial",
    preco: null,
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
    nome: "Exclusive",
    preco: null,
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
    nome: "Premium",
    preco: null,
    chamada: "Para quem quer o máximo do produto e alguém do lado.",
    itens: ["Tudo do Exclusive", "Gerente de conta dedicado"],
    depois: {
      titulo: "Chegando antes do lançamento",
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
  return (
    <div className="grid gap-6 md:grid-cols-3 md:items-stretch">
      {PLANOS.map((plano) => (
        <CartaoDoPlano key={plano.nome} plano={plano} />
      ))}
    </div>
  );
}

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

function CartaoDoPlano({ plano }: { plano: Plano }) {
  const mensagem = `Olá! Quero contratar o plano ${plano.nome} do SellerPulse.`;
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
      <p className="mt-4">
        {plano.preco === null ? (
          <span className="text-lg font-semibold">Sob consulta</span>
        ) : (
          <>
            <span className="text-3xl font-semibold tracking-tight">{brl.format(plano.preco)}</span>
            <span className="text-sm text-muted">/mês</span>
          </>
        )}
      </p>

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
        {WHATSAPP_DE_CONTATO && (
          <a
            href={linkDeWhatsapp(WHATSAPP_DE_CONTATO, mensagem)}
            target="_blank"
            rel="noopener noreferrer"
            className={`rounded-lg px-4 py-2 text-center text-sm font-medium transition ${
              plano.destaque
                ? "bg-accent text-white hover:bg-accent-hover"
                : "border border-line hover:bg-surface"
            }`}
          >
            Quero o {plano.nome} pelo WhatsApp
          </a>
        )}
        <a
          href={linkDeEmail(`Quero o plano ${plano.nome}`)}
          className={`rounded-lg px-4 py-2 text-center text-sm font-medium transition ${
            plano.destaque && !WHATSAPP_DE_CONTATO
              ? "bg-accent text-white hover:bg-accent-hover"
              : "border border-line hover:bg-surface"
          }`}
        >
          {WHATSAPP_DE_CONTATO ? "Ou por e-mail" : `Quero o ${plano.nome}`}
        </a>
        <span className="sr-only">E-mail: {EMAIL_DE_CONTATO}</span>
      </div>
    </section>
  );
}
