// frontend/lib/conversa-da-demo.test.ts
import { describe, expect, it } from "vitest";

import { totalizarFluxo } from "../components/analytics/executive-totals";
import type { FluxoDia } from "./api";
import { coberturaDoFluxo } from "./cobertura";
import { PERGUNTA_DA_CONVERSA, SEM_NUMEROS, respostaDaConversa } from "./conversa-da-demo";
import { montaVeredito, vereditoDoFluxo } from "./resumo";

/** O Intl usa espaço não separável em "R$ 1.000"; os textos esperados, não. */
const t = (s: string) => s.replace(/ /g, " ");

function dia(date: string, receita: number, custoProdutos: number): FluxoDia {
  const taxas_ml = receita * 0.12;
  const frete = receita * 0.01;
  return {
    date,
    receita_bruta: receita,
    taxas_ml,
    frete,
    receita_sem_frete: 0,
    custo_produtos: custoProdutos,
    receita_sem_custo: 0,
    margem_contribuicao: receita - taxas_ml - frete - custoProdutos,
  };
}

const atual = [dia("2026-11-01", 60000, 25000), dia("2026-11-02", 40000, 15000)];
const anterior = [dia("2026-10-01", 50000, 20000)];

describe("resposta da conversa", () => {
  it("a pergunta é a da maquete aprovada", () => {
    expect(PERGUNTA_DA_CONVERSA).toBe("Quanto sobrou das minhas vendas nos últimos 30 dias?");
  });

  it("usa os mesmos números do Resumo da demo", () => {
    const veredito = vereditoDoFluxo(atual, anterior);
    const r = respostaDaConversa(atual, anterior);
    expect(r.frase).toBe(veredito.sobra);
    expect(r.linhas?.map((l) => l.rotulo)).toEqual([
      "Vendas",
      "Comissão do ML",
      "Frete",
      "Custo dos produtos",
    ]);
    expect(r.linhas).toEqual(veredito.partes);
    expect(r.fecho).toBe(veredito.lembrete);
  });

  it("o Resumo e a conversa saem da mesma conta", () => {
    const veredito = vereditoDoFluxo(atual, anterior);
    const aMao = montaVeredito({
      atual: totalizarFluxo(atual),
      anterior: totalizarFluxo(anterior),
      coberturaAtual: coberturaDoFluxo(atual),
      coberturaAnterior: coberturaDoFluxo(anterior),
    });
    expect(veredito).toEqual(aMao);
  });

  it("com custo faltando, avisa como o Resumo e marca o custo como parcial", () => {
    // 30.000 das vendas sem custo informado: a sobra mostrada é maior que a real.
    const parcial = [{ ...dia("2026-11-01", 100000, 30000), receita_sem_custo: 30000 }];
    const veredito = vereditoDoFluxo(parcial, anterior);
    expect(veredito.avisoCobertura).not.toBeNull();

    const r = respostaDaConversa(parcial, anterior);
    expect(r.avisos).toContain(veredito.avisoCobertura);
    expect(r.linhas).toEqual(veredito.partes);
    expect(r.linhas?.find((l) => l.rotulo === "Custo dos produtos")?.nota).toBeTruthy();
  });

  it("com custo completo, nenhum aviso de cobertura", () => {
    expect(respostaDaConversa(atual, anterior).avisos).toEqual([]);
  });

  it("sobra de R$ 47.000 aparece na frase", () => {
    // 100.000 − 12.000 − 1.000 − 40.000
    expect(t(respostaDaConversa(atual, anterior).frase)).toBe("Sobraram R$ 47.000 das suas vendas.");
  });

  it("no negativo, diz que faltou", () => {
    const ruim = [dia("2026-11-01", 10000, 20000)];
    expect(respostaDaConversa(ruim, anterior).frase).toMatch(/^As vendas não cobriram os custos/);
  });

  it("sem dado da demo, nenhuma tabela e nenhum número", () => {
    const r = respostaDaConversa(null, null);
    expect(r.linhas).toBeNull();
    expect(r.avisos).toEqual([]);
    expect(r.frase).toBe(SEM_NUMEROS);
    expect(r.frase).not.toMatch(/\d/);
  });

  it("demo sem venda no período também não inventa número", () => {
    const r = respostaDaConversa([], anterior);
    expect(r.linhas).toBeNull();
    expect(r.frase).toBe(SEM_NUMEROS);
  });
});
