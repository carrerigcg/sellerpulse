import { describe, expect, it } from "vitest";

import { BOM, formataCampo, montaCsv, nomeDoArquivo, type Coluna } from "./csv";

/**
 * Por que o frontend ganhou testes por causa desta função:
 *
 * formatação brasileira errada não derruba nada. Gera um arquivo que abre,
 * parece certo e tem os números errados — o modo de falha mais caro que
 * existe, e invisível em `lint` e `build`, que é tudo que a CI rodava aqui.
 */

type Linha = { nome: string; valor: number | null };
const COLUNAS: Coluna<Linha>[] = [
  { titulo: "Produto", campo: "nome" },
  { titulo: "Receita", campo: "valor" },
];

describe("formataCampo", () => {
  it("usa vírgula como separador decimal", () => {
    // Com ponto, o Excel pt-BR lê como texto e nenhuma soma funciona.
    expect(formataCampo(1234.5)).toBe("1234,5");
    expect(formataCampo(0.1)).toBe("0,1");
    expect(formataCampo(-12.75)).toBe("-12,75");
  });

  it("deixa inteiro sem vírgula", () => {
    expect(formataCampo(412)).toBe("412");
  });

  it("transforma ausência em campo vazio, nunca em zero", () => {
    // Zero numa planilha é uma afirmação: quem somar a coluna acredita nela.
    expect(formataCampo(null)).toBe("");
    expect(formataCampo(undefined)).toBe("");
  });

  it("trata NaN e Infinity como ausência", () => {
    expect(formataCampo(NaN)).toBe("");
    expect(formataCampo(Infinity)).toBe("");
  });

  it("põe entre aspas o campo que contém o separador", () => {
    // Sem isto, o título quebra a linha em duas colunas e desloca tudo à direita.
    expect(formataCampo("Kit 3 peças; promoção")).toBe('"Kit 3 peças; promoção"');
  });

  it("duplica aspas dentro do campo", () => {
    expect(formataCampo('Capacete "Pro"')).toBe('"Capacete ""Pro"""');
  });

  it("põe entre aspas o campo com quebra de linha", () => {
    expect(formataCampo("linha1\nlinha2")).toBe('"linha1\nlinha2"');
  });

  it("deixa texto simples intocado", () => {
    expect(formataCampo("Luminária LED 50W")).toBe("Luminária LED 50W");
  });

  it("não deixa vazar o ruído binário da soma do backend", () => {
    // Valores reais do arquivo baixado da demo em 14/10/2026. O backend soma
    // dinheiro com SUM() no Postgres e o double não fecha em centavos; sem
    // tratamento, a coluna de reais sai com "4263,240000000001".
    expect(formataCampo(4263.240000000001)).toBe("4263,24");
    expect(formataCampo(1031.6399999999999)).toBe("1031,64");
    expect(formataCampo(37.120000000000005)).toBe("37,12");
    expect(formataCampo(0.1 + 0.2)).toBe("0,3");
  });

  it("preserva a precisão que o número de fato tem", () => {
    // A porcentagem da curva ABC vem com 4 casas de propósito. Um arredonda-
    // mento cego a 2 casas aqui destruiria a coluna inteira, e o arquivo
    // continuaria "parecendo certo".
    expect(formataCampo(32.8503)).toBe("32,8503");
    expect(formataCampo(0.0865)).toBe("0,0865");
    expect(formataCampo(99.9413)).toBe("99,9413");
  });
});

describe("montaCsv", () => {
  it("começa com o BOM literal", () => {
    // Sem ele o Excel no Windows lê UTF-8 como ANSI: "Iluminação" vira lixo.
    //
    // A asserção é contra "﻿" escrito à mão, NÃO contra a constante
    // importada. Comparar com a constante é tautologia: se ela virasse "",
    // `startsWith("")` seria sempre verdadeiro e o teste passaria com o BOM
    // removido do produto. Foi o que aconteceu — descoberto por mutação.
    expect(montaCsv([], COLUNAS).charCodeAt(0)).toBe(0xfeff);
    expect(BOM).toBe("﻿");
  });

  it("separa campos com ponto e vírgula", () => {
    const csv = montaCsv([{ nome: "Luminária", valor: 138747.5 }], COLUNAS);
    expect(csv).toContain("Luminária;138747,5");
  });

  it("escreve o cabeçalho em português, por extenso", () => {
    expect(montaCsv([], COLUNAS)).toContain("Produto;Receita");
  });

  it("termina as linhas com CRLF", () => {
    const csv = montaCsv([{ nome: "A", valor: 1 }], COLUNAS);
    expect(csv).toBe("﻿Produto;Receita\r\nA;1\r\n");
  });

  it("segue a ordem das colunas, não a das chaves do objeto", () => {
    const invertidas: Coluna<Linha>[] = [COLUNAS[1], COLUNAS[0]];
    const csv = montaCsv([{ nome: "A", valor: 9 }], invertidas);
    expect(csv).toContain("Receita;Produto");
    expect(csv).toContain("9;A");
  });

  it("preserva acentuação", () => {
    const csv = montaCsv([{ nome: "Iluminação e Decoração", valor: 1 }], COLUNAS);
    expect(csv).toContain("Iluminação e Decoração");
  });

  it("gera só o cabeçalho quando não há linhas", () => {
    expect(montaCsv([], COLUNAS)).toBe("﻿Produto;Receita\r\n");
  });
});

describe("nomeDoArquivo", () => {
  it("carrega a tela e o período", () => {
    // Três exportações com janelas diferentes viram três arquivos na pasta de
    // downloads; sem a data no nome, não dá pra saber qual é qual.
    expect(nomeDoArquivo("produtos", "2026-07-15", "2026-10-13")).toBe(
      "sellerpulse-produtos-2026-07-15_2026-10-13.csv",
    );
  });
});
