# SellerPulse — Exportação das tabelas

**Data:** 2026-10-13
**Status:** Implementado em 2026-10-13 (PR #9). A aba dedicada veio depois, em `2026-10-14-aba-exportacao-design.md`.

---

## 1. Contexto

Analista vive no Excel. Hoje o SellerPulse mostra tabelas bonitas e **não deixa levar o número embora** — quem quiser cruzar a curva ABC com a planilha de estoque copia à mão ou não cruza.

Os dois concorrentes resolvem isso. A AvantPro lista "Exportação para Excel" em todos os planos; a JoomPulse põe "Exportação de dados" como item do plano de R$ 332/mês.

É a mais barata das três features da varredura de 2026-10-13, e a mais visível: num portfólio de BI, exportar mostra que você pensou em quem **recebe** o número, não só em quem olha a tela.

## 2. A decisão de formato, e por que ela não é óbvia

Decidido com o Guilherme: **CSV no padrão brasileiro, gerado no navegador.**

O que torna a decisão interessante é a armadilha de localidade. O Excel em português espera **`;` como separador de campo e `,` como separador decimal**. Um CSV no padrão americano — `,` e `.` — abre como **uma coluna só**, toda embolada. O vendedor dá dois cliques, vê lixo, e conclui que a exportação não funciona.

Então o formato não é "CSV". É:

| | |
|---|---|
| Separador de campo | `;` |
| Separador decimal | `,` |
| Codificação | UTF-8 **com BOM** |
| Fim de linha | `\r\n` |

**O BOM não é opcional.** Sem ele, o Excel no Windows lê UTF-8 como ANSI e "Iluminação" vira "IluminaÃ§Ã£o". Três bytes resolvem.

**Por que no navegador e não no backend:** o dado já está carregado quando a pessoa olha a tela — `lib/api.ts` busca tudo antes de desenhar. Gerar ali custa zero dependência, zero endpoint e zero memória no Render, que tem 512 MB e hiberna. E o download precisaria carregar o token do Supabase de qualquer jeito, então o navegador montaria o arquivo mesmo na versão de backend.

**O que se perde, declarado:** nada de abas múltiplas, formatação ou tipos. Um arquivo por tela. Se alguém pedir uma pasta de trabalho com as três abas, é `.xlsx` e aí o backend volta à conversa — está na seção 8.

## 3. Goals & non-goals

### Goals

- Botão **Exportar** nas três telas do dashboard, sobre a tabela que está na tela.
- CSV no padrão brasileiro: `;`, decimal com vírgula, UTF-8 com BOM.
- Nome do arquivo com a tela e o período: `sellerpulse-produtos-2026-07-15_2026-10-13.csv`.
- **Exporta exatamente o que a tela mostra** — mesmas linhas, mesma ordem, mesmo período.
- Testes de unidade da geração do CSV, o que **exige introduzir uma suíte de testes no frontend**. Ver seção 6.

### Non-goals

- **`.xlsx`** e pasta de trabalho com abas. Ver seção 2.
- **Exportação no servidor** e agendada ("me mande a planilha toda segunda"). Isso é e-mail, e depende do domínio.
- **Exportar mais do que a tela mostra.** Se a tabela mostra 47 linhas, o arquivo tem 47. Exportar um conjunto diferente do visível é a receita para o número do arquivo não bater com o da tela, e aí os dois perdem a credibilidade.
- **Exportar na demonstração.** Ver seção 7.
- **Gráficos.** Exporta-se tabela.

## 4. Decisões travadas

1. **CSV brasileiro, no navegador.**
2. **Um arquivo por tela**, não um consolidado.
3. **O arquivo espelha a tela.** Mesmo filtro, mesma ordenação, mesmo período.

## 5. O que entra em cada arquivo

| Tela | Conteúdo | Colunas |
|---|---|---|
| Executive | Fluxo financeiro diário | data, receita bruta, comissão do ML, frete, margem de contribuição |
| Produtos | Curva ABC | classe, SKU, título, receita, % da receita, % acumulado |
| Clientes | RFM por comprador | comprador, recência (dias), frequência, valor, R, F, M, segmento |

**Cabeçalhos em português, por extenso.** `margem_contribuicao` é nome de coluna de banco; quem abre a planilha quer ler "Margem de contribuição".

**As telas que ganharem colunas novas, ganham nelas também.** Quando o custo de produto entrar, `custo` e `receita sem custo` entram no arquivo do Executive e no de Produtos; quando visitas entrarem, `visitas` e `conversão` entram no de Produtos. Fica registrado aqui porque é exatamente o tipo de coisa que se esquece: a tela ganha a coluna e o arquivo fica para trás, em silêncio.

## 6. Testes, e uma adição deliberada de escopo

**O frontend não tem suíte de testes.** São 270 testes no backend e zero aqui; a CI roda só `lint` e `build`.

Esta feature introduz **vitest**, e isso é adição de escopo consciente — não um "já que estamos aqui". A justificativa é específica: a lógica de formatação brasileira é **exatamente o tipo de coisa que quebra em silêncio**. Um decimal com ponto em vez de vírgula não derruba nada: gera um arquivo que abre, parece certo e tem os números errados. É o modo de falha mais caro que existe, e o único jeito de travá-lo é teste.

O escopo da suíte é mínimo: `vitest` em `devDependencies`, um `npm run test`, e a CI roda. Nada de React Testing Library, nada de teste de componente. Só a função pura.

A geração do CSV fica numa função pura em `frontend/lib/csv.ts`, separada do botão — é o que a torna testável sem navegador.

Casos:

- **Decimal com vírgula:** `1234.5` vira `1234,5`. Mutação: trocar por `toString()` e ver quebrar.
- **BOM presente:** o arquivo começa com `﻿`. Mutação: remover e ver quebrar.
- **Separador é `;`**, e um campo que contenha `;` sai entre aspas.
- **Aspas dentro do campo** viram aspas duplicadas (título de produto com `"` existe).
- **Nulo vira campo vazio**, nunca a string `null` nem `0` — a mesma regra do custo de produto e das visitas: ausência não é zero.
- **Acento sobrevive:** "Iluminação" volta íntegro ao ser lido como UTF-8.
- **Ordem das colunas** segue o cabeçalho declarado, não a ordem das chaves do objeto.

## 7. A demonstração

O botão **não aparece** em `/demo`.

O dado é fictício e está rotulado como tal em toda tela. Um arquivo baixado perde o rótulo: vira uma planilha com números de aparência real, sem nada dizendo que são inventados — e o ponto fraco dessa demonstração sempre foi número bonito sem procedência.

Se depois fizer sentido deixar exportar na demo, o arquivo leva uma primeira linha de aviso. Não nesta versão.

## 8. Próximas

1. **`.xlsx` com as três abas**, se alguém pedir pasta de trabalho. Aí o backend volta à conversa, com openpyxl.
2. **Envio agendado por e-mail**, que depende do domínio e do Resend.
3. **Exportar o cohort**, que é matriz e não tabela — precisa de decisão própria sobre como achatar.
