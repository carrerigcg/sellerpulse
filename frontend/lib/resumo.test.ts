import { describe, expect, it } from "vitest";

import type { FluxoDia } from "./api";
import { calculaCobertura } from "./cobertura";
import {
  NADA_E_ANUNCIOS_SEM_AVALIACAO,
  NADA_PEDINDO_ATENCAO,
  RESUMO_INCOMPLETO,
  hrefDoFinanceiro,
  montaResumo,
  montaTarefas,
  montaVeredito,
  rodapeDasTarefas,
  type LinksDoResumo,
  type Totais,
} from "./resumo";

/**
 * O que carrega peso aqui é o aviso de comparação. Quem preenche custos hoje
 * passa a ver as vendas novas descontando o produto, e a sobra "cai" — sem o
 * aviso, o vendedor concluiria que a loja piorou, quando o que mudou foi a
 * conta ficar honesta. E o inverso também pesa: o aviso não pode calar uma
 * alta de custo que é real.
 */

/** O Intl usa espaço não separável em "R$ 1.000"; os textos esperados, não. */
const t = (s: string | null) => (s === null ? null : s.replace(/ /g, " "));

/** Totais coerentes: a margem é sempre a conta das outras três. */
function totais(receita: number, custo: number, custoProdutos: number): Totais {
  return { receita, custo, custoProdutos, margem: receita - custo - custoProdutos };
}

const COMPLETA = calculaCobertura(100, 0);

describe("montaVeredito — a sobra", () => {
  it("sobra positiva que caiu, com o principal motivo", () => {
    const v = montaVeredito({
      atual: totais(118_000, 20_000, 45_700),
      anterior: totais(128_000, 21_000, 51_400),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.sobra)).toBe("Sobraram R$ 52.300 das suas vendas.");
    expect(t(v.comparacao)).toBe("R$ 3.300 a menos do que sobrou nos 30 dias anteriores.");
    expect(v.direcao).toBe("menos");
    expect(t(v.maiorPeso)).toBe(
      "Principal motivo: as vendas caíram R$ 10.000 — de R$ 128.000 para R$ 118.000.",
    );
    expect(v.explicacao).toBe(
      "É o que fica depois de pagar o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas ainda saem daí.",
    );
  });

  it("sobra que subiu", () => {
    const v = montaVeredito({
      atual: totais(128_000, 21_000, 51_400),
      anterior: totais(118_000, 20_000, 45_700),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.comparacao)).toBe("R$ 3.300 a mais do que sobrou nos 30 dias anteriores.");
    expect(v.direcao).toBe("mais");
  });

  it("sobra zero ainda é sobra, não falta", () => {
    const v = montaVeredito({
      atual: totais(10_000, 4_000, 6_000),
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(t(v.sobra)).toBe("Sobraram R$ 0 das suas vendas.");
  });

  it("sobra negativa vira falta, com a explicação de falta", () => {
    const v = montaVeredito({
      atual: totais(10_000, 3_000, 9_000),
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(t(v.sobra)).toBe("As vendas não cobriram os custos: faltaram R$ 2.000.");
    expect(v.explicacao).toBe(
      "Na conta entram o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas vêm depois.",
    );
  });

  it("com mês negativo, a comparação tem sujeito próprio — falta que diminuiu é melhora", () => {
    const v = montaVeredito({
      atual: totais(20_000, 5_000, 15_400), // −400
      anterior: totais(20_000, 5_000, 16_000), // −1.000
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.comparacao)).toBe("O resultado foi R$ 600 melhor que nos 30 dias anteriores.");
    expect(v.direcao).toBe("mais");
  });

  it("de sobra para falta é piora", () => {
    const v = montaVeredito({
      atual: totais(20_000, 5_000, 15_500), // −500
      anterior: totais(20_000, 5_000, 13_000), // +2.000
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.comparacao)).toBe("O resultado foi R$ 2.500 pior que nos 30 dias anteriores.");
    expect(v.direcao).toBe("menos");
  });

  it("falta no meio do real arredonda como o cartão do Financeiro (para longe do zero)", () => {
    const v = montaVeredito({
      atual: { receita: 0, custo: 0, custoProdutos: 1_000.5, margem: -1_000.5 },
      anterior: null,
      coberturaAtual: COMPLETA,
      coberturaAnterior: null,
    });
    expect(t(v.sobra)).toBe("As vendas não cobriram os custos: faltaram R$ 1.001.");
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

describe("montaVeredito — principal motivo", () => {
  it("só conta quem empurrou para o mesmo lado da mudança", () => {
    // A sobra caiu R$ 3.000. As vendas SUBIRAM R$ 5.000 — não são o motivo da
    // queda; o custo dos produtos subiu R$ 8.000 e é quem explica.
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe("Principal motivo: o custo dos produtos subiu R$ 8.000.");
    expect(v.avisoComparacao).toBeNull();
  });

  it("tarifas do Mercado Livre e frete", () => {
    const v = montaVeredito({
      atual: totais(100_000, 30_000, 30_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe(
      "Principal motivo: as tarifas do Mercado Livre e o frete subiram R$ 10.000.",
    );
  });

  it("diferença de R$ 1 que nenhuma parte arredondada explica: sem motivo, sem quebrar", () => {
    const v = montaVeredito({
      atual: { receita: 10_000, custo: 2_000.4, custoProdutos: 0, margem: 7_999.6 },
      anterior: { receita: 10_000, custo: 2_000.4, custoProdutos: 0.2, margem: 7_999.4 },
      coberturaAtual: COMPLETA,
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.comparacao)).toBe("R$ 1 a mais do que sobrou nos 30 dias anteriores.");
    expect(v.maiorPeso).toBeNull();
  });
});

describe("montaVeredito — aviso de comparação", () => {
  it("cobertura subiu e custo subiu: o motivo continua dito, e o aviso explica parte dele", () => {
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: calculaCobertura(105_000, 6_300), // 94%
      coberturaAnterior: calculaCobertura(100_000, 40_000), // 60%
    });
    expect(t(v.maiorPeso)).toBe("Principal motivo: o custo dos produtos subiu R$ 8.000.");
    expect(v.avisoComparacao).toBe(
      "Parte da diferença vem do custo informado: neste período, 94% do valor vendido tinha custo; no anterior, 60%.",
    );
  });

  it("cobertura caiu e custo subiu mesmo assim: a alta é real, e o aviso não a cala", () => {
    const v = montaVeredito({
      atual: totais(105_000, 20_000, 38_000),
      anterior: totais(100_000, 20_000, 30_000),
      coberturaAtual: calculaCobertura(105_000, 10_500), // 90%
      coberturaAnterior: COMPLETA,
    });
    expect(t(v.maiorPeso)).toBe("Principal motivo: o custo dos produtos subiu R$ 8.000.");
    expect(v.avisoComparacao).toBeNull();
  });

  it("avisa mesmo quando o principal motivo é outra parte — a cobertura distorce a conta toda", () => {
    const v = montaVeredito({
      atual: totais(100_000, 20_000, 30_000),
      anterior: totais(140_000, 28_000, 0),
      coberturaAtual: COMPLETA,
      coberturaAnterior: calculaCobertura(140_000, 140_000), // 0%
    });
    expect(t(v.maiorPeso)).toBe(
      "Principal motivo: as vendas caíram R$ 40.000 — de R$ 140.000 para R$ 100.000.",
    );
    expect(v.avisoComparacao).toBe(
      "Parte da diferença vem do custo informado: neste período, 100% do valor vendido tinha custo; no anterior, 0%.",
    );
  });
});

describe("montaVeredito — aviso de cobertura e explicação", () => {
  const base = { atual: totais(100, 10, 10), anterior: null, coberturaAnterior: null };

  it("parcial", () => {
    const v = montaVeredito({ ...base, coberturaAtual: calculaCobertura(100, 6) });
    expect(v.avisoCobertura).toBe(
      "6% do valor vendido neste período saiu sem custo informado — a sobra verdadeira é menor que essa.",
    );
  });

  it("nenhum custo: a explicação não afirma um desconto que não aconteceu", () => {
    const v = montaVeredito({ ...base, coberturaAtual: calculaCobertura(100, 100) });
    expect(v.avisoCobertura).toBe("Nenhuma venda deste período saiu com custo informado.");
    expect(v.explicacao).toBe(
      "É o que fica depois de pagar o Mercado Livre e o frete — o custo dos produtos ainda não foi descontado. Aluguel, salários e outras despesas também saem daí.",
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

/** Régua confiável e todo mundo na mediana: tudo campeão, nenhum cartão. */
const LOJA_EQUILIBRADA = Array.from({ length: 5 }, () => anuncio(100, 6));

const SEM_PENDENCIA = { custos: [{ custo_unitario: 10 }], abc: LOJA_EQUILIBRADA, rfm: [] };

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
        apoio: "Com o custo informado, as próximas vendas já descontam o produto.",
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

  it("anúncios pela mesma regra da seção Desempenho dos anúncios, com botões distintos", () => {
    const { tarefas, anunciosAvaliados } = montaTarefas({ ...SEM_PENDENCIA, abc: LOJA, links: LINKS });
    expect(anunciosAvaliados).toBe(true);
    expect(tarefas.map((x) => x.chave)).toEqual(["visto-e-rejeitado", "converte-falta-ser-visto"]);
    expect(tarefas[0].frase).toBe(
      "2 anúncios recebem mais visitas que a média da sua loja, mas vendem menos",
    );
    expect(tarefas[0].botao).toBe("Ver os que vendem menos");
    expect(tarefas[0].href).toBe(
      "/dashboard/produtos?de=2026-09-23&ate=2026-10-23&diagnostico=visto-e-rejeitado#desempenho-anuncios",
    );
    expect(tarefas[1].frase).toBe(
      "1 anúncio vende mais que a média da sua loja quando é visto, mas recebe poucas visitas",
    );
    expect(tarefas[1].apoio).toBe("Vale dar mais visibilidade a ele.");
    expect(tarefas[1].botao).toBe("Ver os pouco vistos");
  });

  it("sem referência confiável, nenhum cartão de anúncio — e anúncios não avaliados", () => {
    const resultado = montaTarefas({ ...SEM_PENDENCIA, abc: LOJA.slice(0, 3), links: LINKS });
    expect(resultado.tarefas).toEqual([]);
    expect(resultado.anunciosAvaliados).toBe(false);
  });

  it("clientes: os dias sem comprar dizem 'sumindo', e a janela é de 3 meses", () => {
    const { tarefas } = montaTarefas({
      ...SEM_PENDENCIA,
      rfm: [
        { segmento: "At Risk", monetary: 1_000.4, recency_dias: 52 },
        { segmento: "At Risk", monetary: 2_000, recency_dias: 70 },
        { segmento: "Champions", monetary: 5_000, recency_dias: 3 },
      ],
      links: LINKS,
    });
    expect(tarefas).toHaveLength(1);
    expect(tarefas[0].frase).toBe(
      "2 clientes que já compraram bem com você não compram há 52 dias ou mais",
    );
    expect(t(tarefas[0].apoio)).toBe("Nos últimos 3 meses, gastaram R$ 3.000 com você.");
    expect(tarefas[0].href).toBe("/dashboard/clientes?de=2026-07-25&ate=2026-10-23");
  });

  it("clientes no singular", () => {
    const { tarefas } = montaTarefas({
      ...SEM_PENDENCIA,
      rfm: [{ segmento: "At Risk", monetary: 100, recency_dias: 61 }],
      links: LINKS,
    });
    expect(tarefas[0].frase).toBe("1 cliente que já comprou bem com você não compra há 61 dias ou mais");
    expect(t(tarefas[0].apoio)).toBe("Nos últimos 3 meses, gastou R$ 100 com você.");
  });

  it("ordem fixa: custos, rejeitados, clientes, pouco vistos", () => {
    const { tarefas } = montaTarefas({
      custos: [{ custo_unitario: null }],
      abc: LOJA,
      rfm: [{ segmento: "At Risk", monetary: 100, recency_dias: 40 }],
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
  it("nada pendente, tudo carregado e anúncios avaliados: 'nada pedindo atenção'", () => {
    expect(rodapeDasTarefas(montaTarefas({ ...SEM_PENDENCIA, links: LINKS }))).toBe(
      NADA_PEDINDO_ATENCAO,
    );
  });

  it("sem régua para os anúncios, não afirma que eles estão bem", () => {
    expect(rodapeDasTarefas(montaTarefas({ ...SEM_PENDENCIA, abc: [], links: LINKS }))).toBe(
      NADA_E_ANUNCIOS_SEM_AVALIACAO,
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

describe("montaResumo", () => {
  /** Um dia de fluxo coerente: tarifas 10%, frete 5%, margem pela conta. */
  function dia(date: string, receita: number, custoProdutos: number): FluxoDia {
    const taxas_ml = receita * 0.1;
    const frete = receita * 0.05;
    return {
      date,
      receita_bruta: receita,
      taxas_ml,
      frete,
      custo_produtos: custoProdutos,
      receita_sem_custo: 0,
      margem_contribuicao: receita - taxas_ml - frete - custoProdutos,
    };
  }
  const ok = <T,>(value: T): PromiseSettledResult<T> => ({ status: "fulfilled", value });
  const falhou = (reason: unknown): PromiseSettledResult<never> => ({ status: "rejected", reason });
  const fontes = {
    abc: ok(LOJA_EQUILIBRADA),
    custos: ok([{ custo_unitario: 10 }]),
    rfm: ok([]),
    links: LINKS,
  };

  it("com os dois fluxos, a sobra é a margem somada dos dias", () => {
    const r = montaResumo({
      ...fontes,
      fluxo: ok([dia("2026-10-01", 1_000, 300), dia("2026-10-02", 1_000, 300)]),
      anterior: ok([dia("2026-09-01", 1_000, 300)]),
    });
    expect(r.erroNoFluxo).toBeNull();
    expect(r.semVendas).toBe(false);
    expect(t(r.veredito.sobra)).toBe("Sobraram R$ 1.100 das suas vendas.");
    expect(r.hrefFinanceiro).toBe("/dashboard/financeiro?de=2026-09-23&ate=2026-10-23");
  });

  it("fluxo atual com erro derruba a tela", () => {
    const erro = new Error("fora do ar");
    const r = montaResumo({ ...fontes, fluxo: falhou(erro), anterior: ok([]) });
    expect(r.erroNoFluxo).toEqual({ motivo: erro });
  });

  it("fluxo anterior com erro também derruba — sem ele a comparação mentiria por omissão", () => {
    const r = montaResumo({
      ...fontes,
      fluxo: ok([dia("2026-10-01", 1_000, 300)]),
      anterior: falhou(new Error("timeout")),
    });
    expect(r.erroNoFluxo).not.toBeNull();
  });

  it("fluxo anterior VAZIO é outra coisa: não houve venda para comparar", () => {
    const r = montaResumo({ ...fontes, fluxo: ok([dia("2026-10-01", 1_000, 300)]), anterior: ok([]) });
    expect(r.erroNoFluxo).toBeNull();
    expect(r.veredito.comparacao).toBe("Não houve vendas nos 30 dias anteriores para comparar.");
  });

  it("sem venda no período: estado vazio", () => {
    expect(montaResumo({ ...fontes, fluxo: ok([]), anterior: ok([]) }).semVendas).toBe(true);
  });
});
