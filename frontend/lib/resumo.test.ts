import { describe, expect, it } from "vitest";

import { calculaCobertura } from "./cobertura";
import {
  EXPLICACAO_DA_SOBRA,
  NADA_PEDINDO_ATENCAO,
  RESUMO_INCOMPLETO,
  hrefDoFinanceiro,
  montaTarefas,
  montaVeredito,
  rodapeDasTarefas,
  type LinksDoResumo,
  type Totais,
} from "./resumo";

/**
 * O que carrega peso aqui é a proteção da cobertura. Quem preenche custos
 * hoje passa a ver as vendas novas descontando o produto, e a sobra "cai" —
 * sem a proteção, a frase culparia o custo e o vendedor concluiria que a loja
 * piorou, quando o que mudou foi a conta ficar honesta.
 */

/** O Intl usa espaço não separável em "R$ 1.000"; os textos esperados, não. */
const t = (s: string | null) => (s === null ? null : s.replace(/ /g, " "));

/** Totais coerentes: a margem é sempre a conta das outras três. */
function totais(receita: number, custo: number, custoProdutos: number): Totais {
  return { receita, custo, custoProdutos, margem: receita - custo - custoProdutos };
}

const COMPLETA = calculaCobertura(100, 0);

describe("montaVeredito — a sobra", () => {
  it("sobra positiva que caiu, com o que mais pesou", () => {
    const v = montaVeredito({
      atual: totais(118_000, 20_000, 45_700),
      anterior: totais(128_000, 21_000, 51_400),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.sobra)).toBe("Sobraram R$ 52.300 das suas vendas.");
    expect(t(v.comparacao)).toBe("R$ 3.300 a menos que nos 30 dias anteriores.");
    expect(v.direcao).toBe("menos");
    expect(t(v.maiorPeso)).toBe(
      "O que mais pesou: as vendas caíram R$ 10.000 — de R$ 128.000 para R$ 118.000.",
    );
    expect(v.explicacao).toBe(EXPLICACAO_DA_SOBRA);
  });

  it("sobra que subiu", () => {
    const v = montaVeredito({
      atual: totais(128_000, 21_000, 51_400),
      anterior: totais(118_000, 20_000, 45_700),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.comparacao)).toBe("R$ 3.300 a mais que nos 30 dias anteriores.");
    expect(v.direcao).toBe("mais");
  });

  it("sobra negativa vira falta, nunca 'sobraram -R$'", () => {
    const v = montaVeredito({
      atual: totais(10_000, 3_000, 9_000),
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(t(v.sobra)).toBe("As vendas não cobriram os custos: faltaram R$ 2.000.");
  });

  it("'o mesmo' quando os números da tela, já arredondados, são iguais", () => {
    const atual = { receita: 5_000, custo: 1_000, custoProdutos: 2_999.6, margem: 1_000.4 };
    const anterior = { receita: 5_000, custo: 1_000, custoProdutos: 3_000.4, margem: 999.6 };
    const v = montaVeredito({ atual, anterior, coberturaAtual: COMPLETA, coberturaAnterior: COMPLETA });
    expect(v.comparacao).toBe("O mesmo que nos 30 dias anteriores.");
    expect(v.direcao).toBe("igual");
    expect(v.maiorPeso).toBeNull();
  });

  it("sem vendas no período anterior, não compara", () => {
    const v = montaVeredito({
      atual: totais(10_000, 2_000, 3_000),
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(v.comparacao).toBe("Não houve vendas nos 30 dias anteriores para comparar.");
    expect(v.direcao).toBe("sem-comparacao");
    expect(v.maiorPeso).toBeNull();
  });
});

describe("montaVeredito — o que mais pesou", () => {
  it("só conta quem empurrou para o mesmo lado da mudança", () => {
    // A sobra caiu R$ 3.000. As vendas SUBIRAM R$ 5.000 — não pesaram para a
    // queda; o custo dos produtos subiu R$ 8.000 e é quem explica.
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe("O que mais pesou: o custo dos produtos subiu R$ 8.000.");
  });

  it("Mercado Livre e frete", () => {
    const v = montaVeredito({
      atual: totais(100_000, 30_000, 30_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe(
      "O que mais pesou: o que o Mercado Livre e o frete levaram subiu R$ 10.000.",
    );
  });

  it("proteção: com cobertura diferente entre os meses, não culpa o custo", () => {
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: calculaCobertura(105_000, 6_300), // 94%
      coberturaAnterior: calculaCobertura(100_000, 40_000), // 60%
    });
    expect(v.maiorPeso).toBe(
      "A comparação mistura meses diferentes: neste, 94% das vendas têm custo informado; no anterior, 60%.",
    );
  });
});

describe("montaVeredito — aviso de cobertura", () => {
  const base = { atual: totais(100, 10, 10), anterior: null, coberturaAnterior: null };

  it("parcial", () => {
    const v = montaVeredito({ ...base, coberturaAtual: calculaCobertura(100, 6) });
    expect(v.avisoCobertura).toBe(
      "6% das vendas deste mês estão sem custo informado — a sobra real é menor.",
    );
  });

  it("nenhum custo informado", () => {
    const v = montaVeredito({ ...base, coberturaAtual: calculaCobertura(100, 100) });
    expect(v.avisoCobertura).toBe(
      "Nenhuma venda deste mês tem custo informado — a sobra acima não desconta o custo dos produtos.",
    );
  });

  it("completa: sem aviso", () => {
    expect(montaVeredito({ ...base, coberturaAtual: COMPLETA }).avisoCobertura).toBeNull();
  });
});

const LINKS: LinksDoResumo = {
  base: "/dashboard",
  periodo: { de: "2026-09-23", ate: "2026-10-23" },
  periodoClientes: { de: "2026-07-25", ate: "2026-10-23" },
};

/** Linha de funil com a conversão calculada como o backend entrega. */
function anuncio(visitas: number, unidades: number) {
  return { visitas, unidades, conversao: (100 * unidades) / visitas };
}

/**
 * Cinco anúncios com amostra suficiente: mediana de conversão 6%, de visitas
 * 100. Dois "vistos e rejeitados" (200 visitas, 2% e 3%), um "converte, falta
 * ser visto" (50 visitas, 10%) e dois campeões.
 */
const LOJA = [anuncio(200, 4), anuncio(200, 6), anuncio(50, 5), anuncio(100, 8), anuncio(100, 6)];

const SEM_PENDENCIA = { custos: [{ custo_unitario: 10 }], abc: [], rfm: [] };

describe("montaTarefas", () => {
  it("produtos sem custo, pelo que falta hoje", () => {
    const { tarefas } = montaTarefas({
      ...SEM_PENDENCIA,
      custos: [{ custo_unitario: 10 }, { custo_unitario: null }, { custo_unitario: null }],
      links: LINKS,
    });
    expect(tarefas).toEqual([
      {
        chave: "custos",
        frase: "2 produtos que você vendeu estão sem custo informado",
        apoio: "Sem ele, a sobra lá em cima aparece maior do que a real.",
        botao: "Informar custos",
        href: "/dashboard/custos?de=2026-09-23&ate=2026-10-23",
      },
    ]);
  });

  it("singular, e na demo o botão é 'Ver custos' (lá a tabela é só leitura)", () => {
    const { tarefas } = montaTarefas({
      ...SEM_PENDENCIA,
      custos: [{ custo_unitario: null }],
      links: { ...LINKS, base: "/demo" },
    });
    expect(tarefas[0].frase).toBe("1 produto que você vendeu está sem custo informado");
    expect(tarefas[0].botao).toBe("Ver custos");
    expect(tarefas[0].href).toBe("/demo/custos?de=2026-09-23&ate=2026-10-23");
  });

  it("anúncios pela mesma regra da seção Desempenho dos anúncios", () => {
    const { tarefas } = montaTarefas({ ...SEM_PENDENCIA, abc: LOJA, links: LINKS });
    expect(tarefas.map((x) => x.chave)).toEqual(["visto-e-rejeitado", "converte-falta-ser-visto"]);
    expect(tarefas[0].frase).toBe("2 anúncios recebem visitas, mas vendem pouco");
    expect(tarefas[0].href).toBe(
      "/dashboard/produtos?de=2026-09-23&ate=2026-10-23&diagnostico=visto-e-rejeitado#desempenho-anuncios",
    );
    expect(tarefas[1].frase).toBe("1 anúncio vende bem quando é visto, mas pouca gente chega até ele");
    expect(tarefas[1].apoio).toBe("Vale dar mais visibilidade a ele.");
  });

  it("sem referência confiável, nenhum cartão de anúncio", () => {
    const { tarefas } = montaTarefas({ ...SEM_PENDENCIA, abc: LOJA.slice(0, 3), links: LINKS });
    expect(tarefas).toEqual([]);
  });

  it("clientes em risco, com o valor e a janela de 3 meses", () => {
    const { tarefas } = montaTarefas({
      ...SEM_PENDENCIA,
      rfm: [
        { segmento: "At Risk", monetary: 1_000.4 },
        { segmento: "At Risk", monetary: 2_000 },
        { segmento: "Champions", monetary: 5_000 },
      ],
      links: LINKS,
    });
    expect(tarefas).toHaveLength(1);
    expect(tarefas[0].frase).toBe("2 clientes que compravam bem estão sumindo");
    expect(t(tarefas[0].apoio)).toBe("Nos últimos 3 meses, gastaram R$ 3.000 com você.");
    expect(tarefas[0].href).toBe("/dashboard/clientes?de=2026-07-25&ate=2026-10-23");
  });

  it("ordem fixa: custos, rejeitados, clientes, pouco vistos", () => {
    const { tarefas } = montaTarefas({
      custos: [{ custo_unitario: null }],
      abc: LOJA,
      rfm: [{ segmento: "At Risk", monetary: 100 }],
      links: LINKS,
    });
    expect(tarefas.map((x) => x.chave)).toEqual([
      "custos",
      "visto-e-rejeitado",
      "clientes-em-risco",
      "converte-falta-ser-visto",
    ]);
  });
});

describe("rodapeDasTarefas", () => {
  it("nada pendente e tudo carregado: 'nada pedindo atenção'", () => {
    expect(rodapeDasTarefas(montaTarefas({ ...SEM_PENDENCIA, links: LINKS }))).toBe(
      NADA_PEDINDO_ATENCAO,
    );
  });

  it("fonte que falhou NUNCA vira 'nada pedindo atenção'", () => {
    const resultado = montaTarefas({ custos: [], abc: null, rfm: [], links: LINKS });
    expect(resultado.incompleto).toBe(true);
    expect(rodapeDasTarefas(resultado)).toBe(RESUMO_INCOMPLETO);
  });

  it("com tarefas e tudo carregado: sem rodapé", () => {
    const resultado = montaTarefas({ ...SEM_PENDENCIA, custos: [{ custo_unitario: null }], links: LINKS });
    expect(rodapeDasTarefas(resultado)).toBeNull();
  });
});

describe("hrefDoFinanceiro", () => {
  it("leva o período do Resumo", () => {
    expect(hrefDoFinanceiro(LINKS)).toBe("/dashboard/financeiro?de=2026-09-23&ate=2026-10-23");
  });
});
