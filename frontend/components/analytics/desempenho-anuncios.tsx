"use client";

import { useMemo, useState } from "react";

import type { AbcLinha } from "@/lib/api";
import {
  APARENCIA,
  ORDEM_DOS_FILTROS,
  calculaReferencia,
  diagnostica,
  type Diagnostico,
} from "@/lib/diagnostico";

import { AnuncioRemovidoPill, anuncioFoiRemovido } from "./anuncio-removido";

const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const pct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

type Campo = "titulo" | "visitas" | "unidades" | "conversao" | "diagnostico";

/**
 * O funil por anúncio: quem é visto, quem converte, e o que fazer com cada um.
 *
 * Vive separada da tabela ABC de propósito, e não é organização — é correção.
 * `receita_acumulada_pct` e a classe A/B/C são propriedades da ordem por
 * receita (a curva de Pareto). Ordenar aquela tabela por conversão deixaria o
 * acumulado sem sentido de leitura e a classe sem a ordem que a produziu.
 *
 * Duas tabelas, duas perguntas, duas ordens naturais.
 *
 * Client Component porque ordenar e filtrar precisam de estado. Os dados
 * chegam como props do Server Component da página: dado puro atravessa a
 * fronteira RSC, função não — restrição documentada em `lib/csv.ts`.
 */
export function DesempenhoAnuncios({
  abc,
  filtroInicial = null,
}: {
  abc: AbcLinha[];
  /** Vem do cartão do Resumo: a pessoa chega vendo os anúncios de que a frase falava. */
  filtroInicial?: Diagnostico | null;
}) {
  const [campo, setCampo] = useState<Campo>("visitas");
  const [descendente, setDescendente] = useState(true);
  const [filtro, setFiltro] = useState<Diagnostico | null>(filtroInicial);

  const { referencia, comDiagnostico, contagens } = useMemo(() => {
    const referencia = calculaReferencia(abc);
    const comDiagnostico = abc.map((linha) => ({
      ...linha,
      diagnostico: diagnostica(linha, referencia),
    }));
    const contagens = new Map<Diagnostico, number>();
    for (const linha of comDiagnostico) {
      contagens.set(linha.diagnostico, (contagens.get(linha.diagnostico) ?? 0) + 1);
    }
    return { referencia, comDiagnostico, contagens };
  }, [abc]);

  const visiveis = useMemo(() => {
    const filtradas = filtro ? comDiagnostico.filter((l) => l.diagnostico === filtro) : comDiagnostico;
    const sinal = descendente ? -1 : 1;
    return [...filtradas].sort((a, b) => {
      if (campo === "titulo") return sinal * a.titulo.localeCompare(b.titulo, "pt-BR");
      if (campo === "diagnostico") {
        return sinal * (ORDEM_DOS_FILTROS.indexOf(a.diagnostico) - ORDEM_DOS_FILTROS.indexOf(b.diagnostico));
      }
      // `null` vai sempre para o FIM, independente da direção: ausência de
      // medição não é "o menor valor", e deixá-la liderar a ordenação
      // crescente encheria o topo da tela de linhas vazias.
      const va = a[campo];
      const vb = b[campo];
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return sinal * ((va as number) - (vb as number));
    });
  }, [comDiagnostico, filtro, campo, descendente]);

  function ordenarPor(novo: Campo) {
    if (novo === campo) {
      setDescendente((d) => !d);
      return;
    }
    setCampo(novo);
    // Texto começa crescente (A→Z); número começa decrescente (maior primeiro),
    // que é o que se quer ver em quase toda coluna de métrica.
    setDescendente(novo !== "titulo");
  }

  const semVisita = contagens.get("sem-visita") ?? 0;
  const totalDeVisitas = abc.reduce((soma, l) => soma + (l.visitas ?? 0), 0);

  /**
   * Quanto do tráfego vai para anúncio que converte abaixo da mediana.
   *
   * Aqui estava "produtos que precisam de atenção", e aquele número era oco:
   * com corte na mediana, cada quadrante fica com ~25% POR CONSTRUÇÃO, então
   * "atenção" daria ~50% em qualquer loja, sempre. Dizia respeito ao método,
   * não ao negócio de quem lê.
   *
   * Este varia de verdade: uma loja com anúncios bons desperdiça pouco
   * tráfego mesmo tendo metade do catálogo abaixo da própria mediana. E é uma
   * medida de magnitude, não de contagem — 3 produtos ruins com 10 mil visitas
   * importam mais que 20 com 50.
   */
  const visitasDesperdicadas = comDiagnostico
    .filter((l) => l.diagnostico === "visto-e-rejeitado")
    .reduce((soma, l) => soma + (l.visitas ?? 0), 0);
  const fatiaDesperdicada =
    totalDeVisitas > 0 ? Math.round((100 * visitasDesperdicadas) / totalDeVisitas) : 0;

  return (
    <section id="desempenho-anuncios" className="mt-6 rounded-xl border border-line p-5">
      <h2 className="text-sm font-semibold">Desempenho dos anúncios</h2>
      <p className="mt-0.5 text-xs text-muted">
        Quem é visto, quem converte, e o que fazer com cada um.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Resumo
          rotulo="Conversão mediana da loja"
          valor={referencia.confiavel ? `${pct.format(referencia.medianaConversao)}%` : "—"}
        />
        <Resumo rotulo="Visitas no período" valor={inteiro.format(totalDeVisitas)} />
        <Resumo
          rotulo="Visitas em anúncios que convertem abaixo da mediana"
          valor={referencia.confiavel ? `${fatiaDesperdicada}%` : "—"}
          detalhe={
            referencia.confiavel && visitasDesperdicadas > 0
              ? `${inteiro.format(visitasDesperdicadas)} visitas`
              : undefined
          }
        />
        <Resumo rotulo="Sem visita colhida" valor={inteiro.format(semVisita)} />
      </div>

      {!referencia.confiavel && (
        <p className="mt-3 rounded-lg bg-highlight-soft px-3 py-2 text-xs leading-relaxed text-ink">
          Poucos produtos têm visita suficiente para a mediana da loja significar algo, então nenhum
          recebe diagnóstico. Os números abaixo continuam valendo.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Chip ativo={filtro === null} onClick={() => setFiltro(null)}>
          Todos · {comDiagnostico.length}
        </Chip>
        {ORDEM_DOS_FILTROS.filter((d) => (contagens.get(d) ?? 0) > 0).map((d) => (
          <Chip key={d} ativo={filtro === d} onClick={() => setFiltro(filtro === d ? null : d)}>
            <span className={`h-1.5 w-1.5 rounded-full ${APARENCIA[d].cor}`} aria-hidden />
            {APARENCIA[d].rotulo} · {contagens.get(d)}
          </Chip>
        ))}
      </div>

      {/* Rolagem lateral no celular em vez de esconder colunas: aqui as cinco
          são o conteúdo, não decoração — esconder Conversão deixaria a seção
          sem motivo de existir. */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted">
            <tr className="border-b border-line">
              <Cabecalho campo="titulo" atual={campo} desc={descendente} ao={ordenarPor}>
                Produto
              </Cabecalho>
              <Cabecalho campo="visitas" atual={campo} desc={descendente} ao={ordenarPor} direita>
                Visitas
              </Cabecalho>
              <Cabecalho campo="unidades" atual={campo} desc={descendente} ao={ordenarPor} direita>
                Unidades
              </Cabecalho>
              <Cabecalho campo="conversao" atual={campo} desc={descendente} ao={ordenarPor} direita>
                Conversão
              </Cabecalho>
              <Cabecalho campo="diagnostico" atual={campo} desc={descendente} ao={ordenarPor}>
                Diagnóstico
              </Cabecalho>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((linha) => {
              const aparencia = APARENCIA[linha.diagnostico];
              return (
                <tr key={linha.sku} className="border-b border-line/60 last:border-0">
                  <td className="py-2.5 pr-3">
                    {anuncioFoiRemovido(linha) ? (
                      <AnuncioRemovidoPill />
                    ) : (
                      <span className="block max-w-[20rem] truncate" title={linha.titulo}>
                        {linha.titulo}
                      </span>
                    )}
                    <span className="text-xs text-muted">{linha.sku}</span>
                  </td>
                  <td className="tabular py-2.5 pr-3 text-right">
                    {linha.visitas === null ? (
                      <span className="text-muted">—</span>
                    ) : (
                      inteiro.format(linha.visitas)
                    )}
                  </td>
                  <td className="tabular py-2.5 pr-3 text-right">{linha.unidades}</td>
                  <td className="tabular py-2.5 pr-3 text-right">
                    {linha.conversao === null ? (
                      <span className="text-muted">—</span>
                    ) : (
                      <>
                        {pct.format(linha.conversao)}%
                        {/* A mediana embaixo de cada linha, e não só no resumo:
                            conversão sozinha não diz se é boa. 3% é ótimo em
                            eletrônico e ruim em acessório. */}
                        {referencia.confiavel && (
                          <span className="block text-xs text-muted">
                            {linha.conversao >= referencia.medianaConversao ? "acima" : "abaixo"} da
                            mediana
                          </span>
                        )}
                      </>
                    )}
                  </td>
                  <td className="py-2.5">
                    <span className="inline-flex items-center gap-1.5 text-xs" title={aparencia.acao}>
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${aparencia.cor}`} aria-hidden />
                      {aparencia.rotulo}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {visiveis.length === 0 && (
        <p className="mt-4 text-xs text-muted">Nenhum produto neste filtro.</p>
      )}
    </section>
  );
}

function Resumo({
  rotulo,
  valor,
  detalhe,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
}) {
  return (
    <div className="rounded-lg bg-surface px-3 py-2.5">
      <p className="text-xs leading-snug text-muted">{rotulo}</p>
      <p className="tabular mt-0.5 text-lg font-semibold">{valor}</p>
      {detalhe && <p className="tabular text-xs text-muted">{detalhe}</p>}
    </div>
  );
}

function Chip({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${
        ativo
          ? "border-accent bg-accent-soft font-medium text-accent-hover"
          : "border-line text-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function Cabecalho({
  campo,
  atual,
  desc,
  ao,
  direita,
  children,
}: {
  campo: Campo;
  atual: Campo;
  desc: boolean;
  ao: (c: Campo) => void;
  direita?: boolean;
  children: React.ReactNode;
}) {
  const ativo = campo === atual;
  return (
    // `aria-sort` no <th>, não no <button>: quem tem papel `columnheader` é a
    // célula, e é nela que o leitor de tela procura a direção da ordenação.
    <th
      aria-sort={ativo ? (desc ? "descending" : "ascending") : "none"}
      className={`py-2 ${direita ? "pr-3 text-right" : "pr-3"} font-medium`}
    >
      <button
        type="button"
        onClick={() => ao(campo)}
        className={`inline-flex items-center gap-1 uppercase tracking-wide transition hover:text-ink ${
          ativo ? "text-accent" : ""
        }`}
      >
        {children}
        <span aria-hidden className={ativo ? "" : "opacity-0"}>
          {desc ? "↓" : "↑"}
        </span>
      </button>
    </th>
  );
}
