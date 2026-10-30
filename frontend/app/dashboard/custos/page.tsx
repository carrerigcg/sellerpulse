import { TabelaCustos } from "@/components/analytics/tabela-custos";
import { AvisoDeHistorico } from "@/components/planos/cadeado";
import { getAcesso, mensagemDeFalhaAoCarregar, getCustos, type CustoLinha } from "@/lib/api";
import { coberturaInformada } from "@/lib/cobertura";
import { hojeNoFusoDoVendedor, periodoPadrao } from "@/lib/periodo";
import { historicoCortado, inicioDoHistorico } from "@/lib/plano";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Tela de Custos — onde o vendedor informa quanto cada produto custa a ele.
 *
 * É o que faz a margem de contribuição passar a ser verdade. Até esta tela
 * existir, o número era `receita − comissão − frete`: faltava o maior custo
 * variável de todos, o da mercadoria, então não era uma margem parcial — era
 * uma margem errada para mais.
 *
 * A janela serve para escolher QUAIS produtos aparecem (os vendidos no
 * período) e com que receita, não para escolher a vigência. O alcance do
 * custo no tempo é a opção da própria tabela: de hoje em diante, ou também
 * nas vendas anteriores sem custo — nunca reescrevendo período informado
 * (docs/specs/2026-10-28-custo-retroativo-design.md). Por isso os textos
 * desta página não prometem nem um nem outro: quem diz é a opção.
 */

export default async function CustosPage({ searchParams }: PageProps<"/dashboard/custos">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  const acesso = await getAcesso().catch(() => null);
  const hoje = hojeNoFusoDoVendedor();
  const inicio = acesso && historicoCortado(acesso, de, hoje) ? inicioDoHistorico(acesso, hoje) : null;

  let linhas: CustoLinha[] = [];
  let erro: string | null = null;

  try {
    linhas = await getCustos(de, ate);
  } catch (e) {
    erro = mensagemDeFalhaAoCarregar(e, "os produtos");
  }

  const cobertura = coberturaInformada(linhas);
  const comCusto = linhas.filter((l) => l.custo_unitario !== null).length;

  const temDados = !erro && linhas.length > 0;

  return (
    <>
      <CabecalhoDeTela
        titulo="Custos"
        subtitulo="Quanto cada produto custa a você. É o que falta para a margem ser a margem."
        de={de}
        ate={ate}
        tela="custos"
        temDados={temDados}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : !temDados ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum produto vendido neste período. Escolha uma janela com vendas para informar custos.
        </p>
      ) : (
        <>
          {inicio && acesso && <AvisoDeHistorico inicio={inicio} acesso={acesso} />}

          <section className="mt-6 rounded-xl border border-line bg-surface p-5">
            <h2 className="text-sm font-semibold">
              {comCusto} de {linhas.length}{" "}
              {linhas.length === 1 ? "produto com custo" : "produtos com custo informado"}
            </h2>
            <p className="mt-0.5 text-xs text-muted">
              {cobertura.completa
                ? "Todos os produtos do período têm custo informado."
                : `Isso cobre ${cobertura.pct}% da receita do período. O que falta aparece como receita sem custo nas outras telas.`}
            </p>
          </section>

          <section className="mt-4 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Produtos vendidos no período</h2>
            <p className="mt-0.5 text-xs text-muted">
              Em ordem de receita, que é a ordem em que informar o custo muda mais a conta. O valor
              salva sozinho ao sair do campo. Campo vazio significa &ldquo;não informado&rdquo;, que
              é diferente de zero.
            </p>
            <div className="mt-4">
              <TabelaCustos linhas={linhas} />
            </div>
          </section>
        </>
      )}
    </>
  );
}
