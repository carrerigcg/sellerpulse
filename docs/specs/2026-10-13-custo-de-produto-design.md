# SellerPulse — Custo de produto informado pelo vendedor

**Data:** 2026-10-13
**Status:** Implementado em 2026-10-14 (PR #11), checkpoints 1 a 6. Duas divergencias do desenho estao registradas no PR.

---

## 1. Contexto

Hoje o SellerPulse calcula `receita − comissão do Mercado Livre − frete` e chama isso de **margem de contribuição**. Em outubro de 2026 foi removido um `COST_ESTIMATE_RATE` de 55% que chutava o custo do produto, com a decisão explícita de que **custo de produto só entra se o vendedor informar** — nunca estimado.

O mecanismo de informar nunca foi construído. O resultado é um rótulo incompleto, e a palavra "incompleto" é precisa: margem de contribuição, por definição, é receita menos os **custos variáveis**. O custo da mercadoria é o maior deles. Faltando ele, o número de hoje não é uma margem de contribuição parcial — é uma margem de contribuição **errada para mais**.

Isto não muda o nome da métrica. **Faz o nome que já existe passar a ser verdade.**

A varredura de concorrentes de 2026-10-13 confirmou o caminho. A AvantPro Control — que faz o mesmo trabalho do SellerPulse, de graça, com Mercado Livre e Shopee — anuncia *"margem real após os custos: produto, impostos e tarifas"*. Eles não adivinham o custo: eles perguntam. É a mesma decisão, já construída do outro lado.

## 2. Goals & non-goals

### Goals

- Tela **Custos** no dashboard: lista os produtos que o vendedor já vendeu, com coluna de custo editável.
- Tabela `product_costs` com **data de vigência** desde o início, mesmo que a tela só pergunte o custo atual.
- `fluxo_financeiro` e `abc_pareto` passam a descontar o custo **quando ele existe** para aquele item na data daquele pedido.
- **Cobertura visível em toda tela que mostra margem.** Nunca apresentar um número como completo quando ele não é.
- Prioridade de preenchimento guiada pela curva ABC: os produtos classe A primeiro.

### Non-goals

- **Impostos.** A AvantPro inclui; nós não, nesta versão. Regime tributário (Simples, Lucro Presumido, MEI), substituição tributária e alíquota por categoria são um projeto próprio, e errar imposto é pior que não mostrar.
- **Custos fixos** (aluguel, salários, anúncios). Margem de contribuição é sobre custo variável; lucro líquido é outra métrica e outra tela.
- **Importação por planilha.** Decidido: tabela editável primeiro. A planilha entra quando alguém com centenas de produtos reclamar — ver seção 9.
- **Edição de histórico pela tela.** O banco guarda a linha do tempo; a tela, nesta versão, só escreve "o custo passou a ser X a partir de hoje".
- **Custo por variação** (cor, tamanho). O ML tem variações sob o mesmo `item_id`; tratamos no nível do `item_id`.
- **Renomear a métrica.** Continua "margem de contribuição". Ver seção 1.

## 3. Decisões travadas

Decididas com o Guilherme em 2026-10-13. Não re-litigar.

1. **Custo com data de vigência no banco, tela simples.** A tabela guarda `vigente_desde` desde o dia um; a tela pergunta só "quanto custa hoje". Adicionar edição de histórico depois é mudança de tela, não migration dolorosa.
2. **Tabela editável, não planilha.** Ele preenche os que importam, começando pelos classe A.
3. **Nunca estimar.** Produto sem custo informado não ganha custo nenhum — ganha a marca de "sem custo".

## 4. Por que a data de vigência não é over-engineering

Sem ela, atualizar um custo **reescreve o passado**: o fornecedor sobe o preço em outubro, você corrige o cadastro, e a margem de setembro muda junto. O lucro de um mês fechado vira outro número.

Para um produto cujo argumento central é *"calculada, não estimada"*, isso é mentir sobre o histórico — e o pior tipo de mentira, porque é silenciosa e plausível.

O custo é o de uma coluna a mais e um `order by` na consulta.

## 5. Modelo de dados

```sql
-- backend/migrations/0008_custo_de_produto.sql
create table product_costs (
    seller_id      uuid not null references sellers(id) on delete cascade,
    item_id        text not null,
    vigente_desde  date not null,
    custo_unitario numeric not null check (custo_unitario >= 0),
    criado_em      timestamptz not null default now(),
    primary key (seller_id, item_id, vigente_desde)
);
```

**Por que a chave inclui `vigente_desde`:** é o que permite duas linhas para o mesmo produto. Informar o custo de novo no mesmo dia **substitui** (upsert na chave); num dia diferente **acrescenta** um período.

**Por que `date` e não `timestamptz`:** o custo é decisão comercial do dia, não evento com hora. E `date` evita a classe de bug de fuso que já apareceu neste projeto.

**Por que não uma coluna em `items_cache`:** porque uma coluna não guarda linha do tempo. A chave daquela tabela é `(seller_id, item_id)` — uma linha por produto —, e custo com vigência precisa de várias.

> Não é por risco de sobrescrita, embora pareça. O upsert da ingestão (`_garante_cache_de_item`, `backend/ml/ingest_pg.py`) nomeia as colunas que atualiza — `title`, `category_id`, `fetched_at` — então uma coluna de custo sobreviveria ao refresh. Fica registrado porque é a objeção natural de quem ler isto depois, e a resposta dela é "sim, sobreviveria, e mesmo assim não serve".

**RLS:** policy no mesmo padrão de `order_items` (defesa em profundidade — o isolamento real continua sendo `seller_id = $N` nas queries).

### A consulta do custo vigente

Para cada item de pedido, o custo que vale é o da **última vigência anterior ou igual** à data do pedido:

```sql
select pc.custo_unitario
  from product_costs pc
 where pc.seller_id = oi.seller_id
   and pc.item_id   = oi.item_id
   and pc.vigente_desde <= o.date_closed::date
 order by pc.vigente_desde desc
 limit 1
```

Na prática, um `lateral join`. Pedido anterior à primeira vigência fica **sem custo** — não herda o primeiro valor para trás, de propósito: o vendedor informou o custo de hoje, não afirmou nada sobre antes.

## 6. O que muda no cálculo

`margem_contribuicao = receita_bruta − taxas_ml − frete − custo_total`

onde `custo_total = Σ (quantidade × custo_unitario_vigente)`, somando **só os itens que têm custo**.

Duas colunas novas em `fluxo_financeiro`, e as mesmas duas em `abc_pareto` por produto:

- `custo_produtos` — o que foi descontado
- `receita_sem_custo` — quanto da receita veio de itens sem custo informado

A segunda é o que torna a primeira honesta. Sem ela, um vendedor com 3 de 47 produtos preenchidos veria uma margem quase intacta e concluiria que lucra muito.

## 7. Cobertura: a regra de honestidade

Toda tela que mostrar margem mostra, junto, **quanto da receita está coberta por custo informado**:

> Margem de contribuição · **R$ 150.230**
> *Custo informado para 68% da receita do período. 31 produtos sem custo.*

Três estados:

| Cobertura | Tratamento |
|---|---|
| 0% | A margem aparece como hoje, com aviso de que não considera custo de produto e um atalho para a tela de Custos |
| 1–99% | Valor mostrado com a porcentagem ao lado, sempre |
| 100% | Sem aviso |

**Nunca esconder o número por estar incompleto, e nunca mostrá-lo como se estivesse completo.** Esconder faria a tela parecer quebrada para quem nunca preencheu nada; mostrar sem a marca é exatamente o chute que foi removido em outubro, só que mais sutil.

## 8. A tela de Custos

Rota `/dashboard/custos`, no grupo **Configuração** da navegação, ao lado de "Conectar conta".

Uma tabela, ordenada pela classe ABC e depois por receita decrescente — quem sustenta o faturamento aparece primeiro, porque é onde o custo muda mais a conta:

| Classe | Produto | Receita (90d) | Unidades | Custo unitário |
|---|---|---|---|---|
| A | Luminária LED 50W | R$ 138.747 | 412 | `[ 48,00 ]` |
| A | Capacete X | R$ 61.487 | 203 | `[      ]` |

- **Salva por linha**, ao sair do campo. Sem botão "salvar tudo": um formulário de 47 linhas que falha inteiro por causa de uma é hostil.
- **Campo vazio significa "não informado"**, nunca zero. Zero é uma afirmação — "este produto não me custa nada" — e precisa ser digitada.
- **Resumo no topo:** quantos produtos têm custo e quanto da receita isso cobre.
- Na **demonstração**, a tela é somente leitura com custos já semeados; a demo não tem usuário para escrever.

### Endpoints

| Verbo | Rota | Resposta |
|---|---|---|
| `GET` | `/custos` | Produtos vendidos na janela, com custo vigente quando houver, classe ABC, receita e unidades |
| `PUT` | `/custos/{item_id}` | `{ "custo_unitario": 48.00 }` → grava com `vigente_desde = hoje` |
| `DELETE` | `/custos/{item_id}` | Remove a vigência de hoje (desfaz um erro de digitação do dia) |

**Primeiro endpoint de escrita de dado do vendedor no sistema.** `seller_id` vem de `get_current_seller_id`, nunca do corpo. O `item_id` é validado contra `items_cache` daquele vendedor — senão vira escrita arbitrária de chave.

## 9. Testes

- **Vigência:** pedido antes da primeira vigência fica sem custo; pedido depois usa a vigência correta; com duas vigências, cada pedido pega a sua. **É o teste que prova que o passado não foi reescrito** — confirmar por mutação, trocando o `order by ... desc limit 1` por um custo único.
- **Cobertura:** com metade dos produtos preenchidos, `receita_sem_custo` reflete a outra metade. Mutação: zerar esse campo e ver o teste quebrar.
- **Zero não é vazio:** custo `0` registrado desconta zero e **conta como informado**; ausência não desconta e conta como não informado.
- **Isolamento:** `PUT` não aceita `seller_id` no corpo, e `item_id` de outro vendedor é recusado.
- **Paridade:** com zero custos cadastrados, `fluxo_financeiro` devolve exatamente os mesmos números de hoje. É o teste que garante que a feature não altera quem não a usa.
- **Upsert:** dois `PUT` no mesmo dia geram uma linha, não duas.

## 10. Checkpoints

1. Migration e RLS; `product_costs` existe e o teste de paridade passa (ninguém é afetado ainda).
2. Consulta do custo vigente nas duas análises, com `custo_produtos` e `receita_sem_custo`.
3. Endpoints `GET`/`PUT`/`DELETE`, com os testes de isolamento.
4. Tela de Custos e o indicador de cobertura nas telas Executive e Produtos.
5. PR com CI verde.
6. Depois do merge: semear custos na demonstração — senão a vitrine mostra 0% de cobertura e a feature parece quebrada.

## 11. Próximas, nesta ordem

Registradas para não virarem escopo desta:

1. **Importação por planilha**, quando alguém com centenas de produtos reclamar da digitação.
2. **Edição de histórico** pela tela, quando alguém precisar corrigir um custo do passado.
3. **Impostos**, que é projeto próprio.
4. **Desempenho do anúncio** (visitas e conversão) e **exportação para Excel** — as outras duas da varredura de concorrentes.
