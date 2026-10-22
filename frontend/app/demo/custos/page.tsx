import { TabelaCustos } from "@/components/analytics/tabela-custos";
import type { CustoLinha } from "@/lib/api";
import { coberturaInformada, produtosSemCusto } from "@/lib/cobertura";
import { getDemoCustos } from "@/lib/demo";
import { periodoPadrao } from "@/lib/periodo";
import { CabecalhoDeTela } from "@/components/analytics/cabecalho-de-tela";

/**
 * Custos da demonstração pública — somente leitura.
 *
 * A demo não tem usuário para escrever, e não existe `PUT /demo/custos`. A
 * tabela mostra os custos semeados em `backend/seed.py`, com a mesma ordem e
 * o mesmo significado da tela autenticada.
 *
 * Nem todo produto tem custo informado aqui, e isso é deliberado: semear 100%
 * faria o indicador de cobertura nunca aparecer, escondendo justamente a
 * promessa que ele carrega — nunca apresentar um número incompleto como
 * completo.
 */

export default async function DemoCustosPage({ searchParams }: PageProps<"/demo/custos">) {
  const params = await searchParams;
  const padrao = periodoPadrao();
  const de = typeof params.de === "string" ? params.de : padrao.de;
  const ate = typeof params.ate === "string" ? params.ate : padrao.ate;

  let linhas: CustoLinha[] = [];
  let erro: string | null = null;

  try {
    linhas = await getDemoCustos(de, ate);
  } catch {
    erro = "Não foi possível carregar a demonstração agora. Tente de novo em instantes.";
  }

  const cobertura = coberturaInformada(linhas);
  const comCusto = linhas.filter((l) => l.custo_unitario !== null).length;

  const temDados = !erro && linhas.length > 0;

  return (
    <>
      <CabecalhoDeTela
        titulo="Custos"
        subtitulo="Quanto cada produto custa ao vendedor. É o que falta para a margem ser a margem."
        de={de}
        ate={ate}
        tela="custos"
        temDados={temDados}
      />

      {erro ? (
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">{erro}</p>
      ) : !temDados ? (
        <p className="mt-8 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">
          Nenhum produto vendido neste período.
        </p>
      ) : (
        <>
          <section className="mt-6 rounded-xl border border-line bg-surface p-5">
            <h2 className="text-sm font-semibold">
              {comCusto} de {linhas.length} produtos com custo informado
            </h2>
            <p className="mt-0.5 text-xs text-muted">
              Isso cobre {cobertura.pct}% da receita do período. Os{" "}
              {produtosSemCusto(
                linhas.map((l) => ({
                  receita: l.receita,
                  receita_sem_custo: l.custo_unitario === null ? l.receita : 0,
                })),
              )}{" "}
              produtos sem custo aparecem marcados — e é por isso que as outras telas avisam que a
              margem ainda não está completa.
            </p>
          </section>

          <section className="mt-4 rounded-xl border border-line p-5">
            <h2 className="text-sm font-semibold">Produtos vendidos no período</h2>
            <p className="mt-0.5 text-xs text-muted">
              Em ordem de receita, que é a ordem em que informar o custo muda mais a conta. Na
              versão com a sua conta conectada, cada valor é editável e salva sozinho.
            </p>
            <div className="mt-4">
              <TabelaCustos linhas={linhas} somenteLeitura />
            </div>
          </section>
        </>
      )}
    </>
  );
}
