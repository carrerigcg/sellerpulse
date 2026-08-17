# SellerPulse — Fase 2: Segmentação + Dashboard (v0.3.0)

**Fase:** 2 de 6 do roadmap definido em `docs/specs/2026-08-07-camadas-analiticas-design.md`
**Tag alvo:** `v0.3.0`
**Data:** 2026-08-17
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

A Fase 1 (mergeada em `main` como `v0.2.0`) entregou a camada `src/metrics.py` (3 funções: `fluxo_financeiro`, `top_produtos`, `reputacao_devolucao`) e o `src/pdf_renderer.py` gerando as páginas P1, P2 e P4 do PDF executivo. A ingestão OAuth do Mercado Livre e o gerador de dados sintéticos (`demo_data.py`, `data/demo.db` versionado) já estavam prontos desde a Fase 0.

Esta fase adiciona a **segunda camada analítica** (segmentação de produtos e clientes) e a **primeira das três saídas interativas**: um dashboard Streamlit multi-page que roda localmente e consome a mesma camada analítica pura que o PDF já usa.

O design segue as decisões travadas em `docs/specs/2026-08-07-camadas-analiticas-design.md` §3 (camada analítica pura, CLI unificado) e resolve as ambiguidades específicas de escopo desta fase via 7 perguntas de clarificação respondidas em sessão de brainstorm 2026-08-17.

## 2. Goals & non-goals

### Goals

- Entregar `src/segmentation.py` com 3 funções puras (`abc_pareto`, `rfm_scores`, `cohort_produto`) seguindo o contrato definido no spec macro §3 (`(conn, date_from, date_to, **opts) -> pd.DataFrame`).
- Entregar `src/dashboard.py` + `src/pages/` com 3 páginas navegáveis (Executive Summary, Product Analytics, Customer Analytics) rodando via `python -m src.main abrir-dashboard`.
- Sidebar global operante: seletor de período **funcional**, toggle Demo/Real **visível com Real desabilitado**, filtro de categoria **visível desabilitado**, versão do build no rodapé.
- Coverage ≥ 85% em `src/segmentation.py` com testes de propriedade matemática (não `hypothesis` — testes manuais).
- Smoke tests em cada página do dashboard via `streamlit.testing` (só valida que carrega sem exception).
- CI continua verde (Python 3.11 × Ubuntu/Windows, sem mudanças na matriz).
- Tag `v0.3.0` publicada.

### Non-goals

- Deploy no Streamlit Community Cloud — fica para Fase 5 (Polish + Launch).
- Filtro de categoria funcional em cada página — fica para Fase 5.
- Toggle de tema dark — fica para Fase 5.
- Drill-down clicável por segmento RFM na página Customers — fica para Fase 5.
- Slider de sensibilidade IQR (STL anomalies) — fica para Fase 3.
- `hypothesis` (property-based testing library) — introduzido apenas na Fase 4 junto de `patrimony.py`.
- Interatividade rica em geral — cada página desta fase reage **apenas** ao seletor de período da sidebar. Nenhum widget dentro das páginas.

## 3. Decisões travadas no brainstorm

Sete decisões resolvidas em sessão 2026-08-17. Cada uma cita a alternativa preterida para contexto futuro.

| # | Decisão | Escolha | Alternativa preterida |
|---|---|---|---|
| 1 | Escopo do dashboard | **A** — shell + gráficos essenciais (1-2 charts principais por página, interatividade só via sidebar) | B (feature-complete com drill-down/sliders); C (só scaffold) |
| 2 | Deploy no Streamlit Cloud | **A** — só na Fase 5 | B (smoke deploy antecipado agora) |
| 3 | Granularidade do cohort | **B** — agregado por mês de lançamento (linhas = mês, não SKU individual) | A (SKU individual); C (por categoria) |
| 4 | Janela do RFM | **A** — mesma `date_from`/`date_to` das outras análises (contrato uniforme) | B (janela fixa 90/180d); C (A + warning) |
| 5 | Sidebar operante | **A** — período funcional; Demo/Real e categoria visíveis mas desabilitados | B (tudo operante); C (só período + versão) |
| 6 | Profundidade dos testes de dashboard | **A** — smoke raso (só valida load sem exception) | B (valida elementos-chave); C (raso + property test de integração) |
| 7 | Estrutura multi-page do Streamlit | **A** — pasta `pages/` (convenção nativa lida automaticamente pelo Streamlit) | B (single-file com `st.radio`); C (`st.navigation` API programática) |
| 8 | Ordem de implementação | **A** — bottom-up (analítica → CLI → dashboard) | B (top-down com scaffold primeiro); C (vertical slices) |

## 4. Camada analítica — `src/segmentation.py`

Três funções puras, contrato compartilhado: recebem `(conn: sqlite3.Connection, date_from: str, date_to: str)`, devolvem `pd.DataFrame`. Sem I/O de arquivo, sem prints, sem rede. Se o período não tem dados, retornam DataFrame vazio (colunas presentes, zero linhas) — não levantam exception.

### 4.1. `abc_pareto(conn, date_from, date_to) -> pd.DataFrame`

Ranqueia produtos vendidos no período por receita e classifica cada um em A/B/C pela regra 80/15/5 acumulada.

**Colunas de saída:**

| coluna | tipo | descrição |
|---|---|---|
| `sku` | str | código do produto (chave primária do produto no schema atual) |
| `titulo` | str | nome do produto |
| `receita` | float | receita total do produto no período (BRL) |
| `receita_pct` | float | percentual da receita total (soma de todas as linhas = 100.0 ± tolerância de arredondamento) |
| `receita_acumulada_pct` | float | percentual acumulado da linha 1 até a atual (monotonicamente crescente) |
| `classe` | str | 'A' se `receita_acumulada_pct` ≤ 80; 'B' se ≤ 95; 'C' caso contrário |

**Ordenação:** decrescente por `receita` (linha 1 = campeão).

**Regra de classe (edge case):** o produto que **cruza** a fronteira de 80% é incluído na classe A (regra "inclusive superior"). Idem para B.

**Uso:** PDF P2 (curva compacta), Dashboard página Products.

### 4.2. `rfm_scores(conn, date_from, date_to) -> pd.DataFrame`

Calcula R/F/M por comprador único no período, atribui scores 1-5 via quintis (5 grupos iguais) e rotula um segmento textual.

**Cálculo por comprador:**
- `recency_dias` = `date_to - MAX(data_compra)` em dias
- `frequency` = contagem de compras únicas no período
- `monetary` = soma do valor gasto no período

**Scores (quintis dentro da base do período):**
- `r_score` — 5 = menor recência (mais recente), 1 = maior recência
- `f_score` — 5 = maior frequência, 1 = menor
- `m_score` — 5 = maior gasto, 1 = menor

Ties (empates) resolvidos pelo método `pd.qcut(..., duplicates="drop")` — se houver empate significativo (muitos compradores com F=1), scores possíveis podem ser < 5 valores distintos. Isso é aceitável.

**Segmentos (ordem de avaliação, primeira regra que casa vence):**

| segmento | condição |
|---|---|
| Champions | R≥4 e F≥4 e M≥4 |
| Loyal | F≥4 e M≥3 |
| At Risk | R≤2 e (F≥3 ou M≥3) |
| New | R≥4 e F≤2 |
| Hibernating | R≤2 e F≤2 e M≤2 |
| Others | qualquer outra combinação |

**Colunas de saída:** `buyer_id` (str), `recency_dias` (int), `frequency` (int), `monetary` (float), `r_score` (int 1-5), `f_score` (int 1-5), `m_score` (int 1-5), `segmento` (str, um dos 6 rótulos acima).

**Uso:** Dashboard página Customers, Notebook (Fase 5).

### 4.3. `cohort_produto(conn, date_from, date_to) -> pd.DataFrame`

Retorna pivot agregado: linhas = mês em que o **grupo de produtos** foi lançado, colunas = mês corrente, células = receita agregada do grupo naquele mês.

**"Mês de lançamento" definição:** menor `data_venda` do produto no banco inteiro (não apenas no período). Se um produto teve primeira venda em jan/2026 e o período consultado é jul-ago/2026, ele pertence ao cohort "jan/2026" mesmo que só apareça em jul.

**Formato do DataFrame:**
- Index: `mes_lancamento` (formato `YYYY-MM`, tipo string)
- Colunas: `mes_corrente` (formato `YYYY-MM`, tipo string), ordenadas cronologicamente
- Células: soma de receita (float, BRL); `NaN` se o grupo ainda não existia naquele mês
- Todas as células acima da diagonal (`mes_corrente < mes_lancamento`) devem ser `NaN`

**Uso:** Dashboard página Products (heatmap), Notebook (Fase 5).

## 5. Dashboard Streamlit

### 5.1. Estrutura de arquivos

```
src/
  dashboard.py                     # entry point + sidebar global
  pages/                           # convenção nativa do Streamlit
    1_executive.py
    2_products.py
    3_customers.py
```

**Convenção:** o Streamlit lê automaticamente qualquer pasta chamada `pages/` que esteja no mesmo diretório do entry point. Usar o nome padrão evita ter que fazer roteamento manual via `st.navigation`. O prefixo numérico (`1_`, `2_`, `3_`) controla a ordem no menu lateral e o underscore vira espaço no título exibido (`1_executive.py` → "Executive").

**Nota de brainstorm:** a decisão original citava `dashboard_pages/` para deixar intenção explícita, mas isso obrigaria uso do `st.navigation` (API programática) — que foi descartado (decisão #7 escolheu padrão nativo). Portanto o nome tem que ser `pages/`.

### 5.2. Sidebar global (`src/dashboard.py`)

Renderizada em `st.sidebar` no topo de `src/dashboard.py`; visível em todas as páginas via `st.session_state`.

**Widgets:**
- `st.sidebar.title("SellerPulse")`
- `st.sidebar.date_input("Início", value=<hoje-90d>)` — grava em `st.session_state["date_from"]`
- `st.sidebar.date_input("Fim", value=<hoje>)` — grava em `st.session_state["date_to"]`
- Widget "Modo: Demo | Real" com Real desabilitado + tooltip `"Configure data/business.db para habilitar"`. Implementação: `st.radio` com parâmetro `captions` (adicionado ao Streamlit em 1.29) exibindo dica sob cada opção, combinado com `disabled=True` só quando o usuário selecionar "Real" (auto-revert para "Demo" via `st.session_state`). Se o `demo.db` estiver ausente e o `business.db` presente (caso raro), inverter o desabilitado — mas este caminho está fora do escopo da Fase 2 (não faz parte do critério de aceite; comportamento default é sempre Demo).
- `st.sidebar.selectbox("Categoria", ["Todas"], disabled=True, help="Disponível na v1.0")`
- `st.sidebar.caption(f"SellerPulse v{__version__}")` — versão lida via `importlib.metadata.version("sellerpulse")`

### 5.3. Página 1 — Executive Summary (`src/pages/1_executive.py`)

Consome: `metrics.fluxo_financeiro`, `metrics.reputacao_devolucao`.

**Layout (de cima pra baixo):**
1. `st.title("Executive Summary")` + `st.caption(f"{date_from} – {date_to}")`
2. Faixa de 4 `st.metric` cards (uso de `st.columns(4)`): Receita bruta, Custo total, Lucro líquido, Nível de reputação
3. Gráfico Plotly (barras empilhadas): receita/custo/líquido por dia — `plotly.express.bar(fluxo_df, x="data", y=["receita", "custo", "liquido"], barmode="stack")`
4. Comparativo semana anterior — 3 `st.metric` com delta calculado

### 5.4. Página 2 — Product Analytics (`src/pages/2_products.py`)

Consome: `metrics.top_produtos`, `segmentation.abc_pareto`, `segmentation.cohort_produto`.

**Layout:**
1. Título + período
2. Duas tabelas em colunas (`st.columns(2)`): top 10 produtos + top 10 categorias, via `st.dataframe(...)`
3. Gráfico Pareto combinado (barras + linha secundária) via `plotly.graph_objects.Figure` com dois traces
4. Heatmap de cohort via `plotly.express.imshow` com tooltip customizado

### 5.5. Página 3 — Customer Analytics (`src/pages/3_customers.py`)

Consome: `segmentation.rfm_scores`.

**Layout:**
1. Título + período
2. 4 `st.metric` cards: total de compradores únicos, Champions, At Risk, Ticket médio
3. Scatter plot RFM via `plotly.express.scatter(rfm_df, x="frequency", y="monetary", color="segmento", size="r_score", hover_data=["buyer_id", "recency_dias"])`
4. Distribuição por segmento via `plotly.express.bar` horizontal

### 5.6. Cache

Todas as chamadas às funções de `metrics.*` e `segmentation.*` são decoradas em wrappers locais em cada página com `@st.cache_data(ttl=300)` — invalida em 5 minutos ou quando os parâmetros mudam. A conexão SQLite não é cacheada (é aberta e fechada por chamada).

## 6. CLI

Modificação em `src/main.py`: adicionar subcomando `abrir-dashboard`.

```python
def cmd_abrir_dashboard(args):
    subprocess.run(["streamlit", "run", "src/dashboard.py"], check=True)
```

Aceita zero argumentos nesta fase. Fase 5 pode adicionar `--port`, `--headless`.

Uso: `python -m src.main abrir-dashboard` → abre navegador em `localhost:8501`.

## 7. Testes

### 7.1. `tests/test_segmentation.py`

Fixture compartilhada `sample_db` (segue padrão de `tests/test_metrics.py`) — cria SQLite temporário com dados sintéticos determinísticos cobrindo:
- 8-12 produtos com receitas conhecidas (para validar classificação ABC deterministicamente)
- 5-10 compradores com padrões de R/F/M controlados (para validar cada segmento RFM)
- 3-4 meses de histórico (para validar pivot de cohort)

**Testes de `abc_pareto` (mínimo 5):**
1. Estrutura: colunas esperadas + ordenação decrescente por receita
2. Propriedade: `sum(receita_pct) ≈ 100.0` (tolerância 0.01)
3. Propriedade: `receita_acumulada_pct` monotonicamente crescente
4. Classificação: com fixture onde 2 produtos somam 80%, ambos são classe A; próximos até 95% são B; resto C
5. Caso vazio: período sem vendas → DataFrame vazio com colunas corretas, sem exception

**Testes de `rfm_scores` (mínimo 7):**
1. Estrutura: 1 linha por buyer_id único
2. Propriedade: scores ∈ [1, 5]
3. Propriedade: `count(distinct buyer_id) == len(df) == sum(count por segmento)`
4-9. Um teste por segmento (Champions, Loyal, At Risk, New, Hibernating, Others) — comprador construído com R/F/M específicos e assert do rótulo esperado
10. Caso vazio: período sem compras → DataFrame vazio

**Testes de `cohort_produto` (mínimo 4):**
1. Estrutura: DataFrame pivot com meses nas linhas e colunas
2. Propriedade: células acima da diagonal são `NaN`
3. Consistência: diagonal bate com query SQL independente `SELECT strftime('%Y-%m', data) AS mes, SUM(receita) FROM ... GROUP BY mes`
4. Caso vazio: período sem dados → DataFrame vazio

**Meta:** coverage ≥ 85% em `src/segmentation.py` medido por `pytest-cov`.

### 7.2. `tests/test_dashboard.py`

3 testes, um por página, usando `streamlit.testing.v1.AppTest`:

```python
from streamlit.testing.v1 import AppTest

def test_executive_page_loads():
    at = AppTest.from_file("src/pages/1_executive.py")
    at.run(timeout=10)
    assert not at.exception

def test_products_page_loads():
    at = AppTest.from_file("src/pages/2_products.py")
    at.run(timeout=10)
    assert not at.exception

def test_customers_page_loads():
    at = AppTest.from_file("src/pages/3_customers.py")
    at.run(timeout=10)
    assert not at.exception
```

**Nota importante sobre `session_state`:** cada página lê `st.session_state["date_from"]` e `st.session_state["date_to"]`, que são populados pela sidebar no entry point `src/dashboard.py`. Quando `AppTest.from_file` roda uma página isolada, a sidebar do entry point **não** é executada — os valores não existem em `session_state`.

Cada página deve implementar um fallback: `date_from = st.session_state.get("date_from", <hoje-90d>)`. Isso vale tanto para os testes (que não pré-populam) quanto para o caso do usuário navegar diretamente para uma página sem passar pela home — o fallback garante que a página funciona.

Alternativa considerada: pré-popular via `at.session_state["date_from"] = ...` em cada teste. Preterida porque o fallback no código de produção é uma proteção genuína (não só workaround de teste), e evita duplicar dados de teste em 3 lugares.

## 8. CI e quality gates

**Sem mudanças no `.github/workflows/tests.yml`.** A matriz atual (Python 3.11 × ubuntu-latest/windows-latest) roda automaticamente os novos testes.

**Verificações locais antes de tag:**
- `ruff format` (formatador) — código formatado
- `ruff check` (linter) — sem warnings
- `pytest --cov` — coverage global mantido ≥ 80%, coverage de `segmentation.py` ≥ 85%
- `python -m src.main abrir-dashboard` — sobe sem erro (verificação manual)

`mypy --strict` e `bandit` continuam fora da Fase 2 (planejados para Fase 5 por decisão do spec macro §8).

## 9. Roadmap de implementação — 10 blocos

Cada bloco vira 1 commit (às vezes 2). Estimativa total ~5.5 dias úteis.

| # | Bloco | Estimativa | Commit representativo |
|---|---|---|---|
| 1 | Preparação: deps + skeleton de arquivos + bump `0.3.0-dev` | 0.5d | `chore(deps): add streamlit + plotly` |
| 2 | `abc_pareto` (TDD: testes + função) | 0.5d | `feat(segmentation): abc_pareto` |
| 3 | `rfm_scores` (TDD) | 1.0d | `feat(segmentation): rfm_scores` |
| 4 | `cohort_produto` (TDD) | 0.5d | `feat(segmentation): cohort_produto` |
| 5 | Subcomando `abrir-dashboard` + `dashboard.py` mínimo + teste CLI | 0.5d | `feat(cli): abrir-dashboard subcommand` |
| 6 | Sidebar global completa | 0.5d | `feat(dashboard): global sidebar` |
| 7 | Página 1 (Executive Summary) + smoke test | 0.5d | `feat(dashboard): page 1 executive` |
| 8 | Página 2 (Product Analytics) + smoke test | 1.0d | `feat(dashboard): page 2 products` |
| 9 | Página 3 (Customer Analytics) + smoke test | 0.5d | `feat(dashboard): page 3 customers` |
| 10 | README + ruff + bump `0.3.0` + tag + push | 0.5d | `chore(release): v0.3.0` |

**Ordem:** bottom-up (analítica antes de dashboard) conforme decisão #8. Cada função de `segmentation.py` pode ser testada isoladamente antes do dashboard existir.

**Estratégia de branch:** trabalhar em `feat/fase-2-segmentacao-dashboard`, abrir PR ao final, fazer squash-merge no `main`, criar tag `v0.3.0`.

## 10. Arquivos criados/modificados

### Criar

- `src/segmentation.py` — 3 funções puras
- `src/dashboard.py` — entry point + sidebar
- `src/pages/1_executive.py`
- `src/pages/2_products.py`
- `src/pages/3_customers.py`
- `tests/test_segmentation.py`
- `tests/test_dashboard.py`

### Modificar

- `src/main.py` — adicionar subcomando `abrir-dashboard`
- `tests/test_main.py` — adicionar teste do novo subcomando
- `requirements.txt` — adicionar `streamlit`, `plotly`
- `pyproject.toml` — bump versão para `0.3.0`
- `README.md` — atualizar tabela de status; adicionar seção "Dashboard interativo" com screenshot e comando

## 11. Critério de aceite (executável)

A fase considera-se completa quando **todos** os itens abaixo verificam:

1. `pytest tests/test_segmentation.py -v` — todos verdes, coverage `src/segmentation.py` ≥ 85%
2. `pytest tests/test_dashboard.py -v` — 3 testes verdes
3. `pytest --cov` — coverage global ≥ 80%
4. `ruff format --check` e `ruff check` — sem falhas
5. `python -m src.main abrir-dashboard` — Streamlit abre em `localhost:8501`, sem exception no terminal
6. Navegação manual entre as 3 páginas — todas renderizam sem erro
7. Alterar seletor de período na sidebar — dados de todas as páginas atualizam
8. Sidebar mostra Demo/Real com Real desabilitado (tooltip) e Categoria desabilitado (tooltip)
9. Rodapé da sidebar mostra `SellerPulse v0.3.0`
10. CI GitHub Actions verde após push (2 jobs: ubuntu, windows)
11. Tag `v0.3.0` criada e publicada
12. README atualizado com screenshot do dashboard e status `✅ Pronto` para `segmentation.py` e `dashboard.py`

## 12. Fora de escopo (empurra para fase posterior)

| Item | Fase que absorve |
|---|---|
| Deploy Streamlit Community Cloud | Fase 5 (Polish + Launch) |
| Filtro de categoria funcional | Fase 5 |
| Toggle dark theme | Fase 5 |
| Drill-down clicável por segmento RFM | Fase 5 |
| Notebook narrativo (Jupyter) | Fase 5 |
| Slider IQR / STL sensibilidade | Fase 3 (junto com forecasting) |
| Página P4 do dashboard (Time Series & Anomalias) | Fase 3 |
| Página P5 do dashboard (Patrimony Simulator) | Fase 4 |
| `hypothesis` para property-based testing | Fase 4 (junto com `patrimony.py`) |
| `mypy --strict` e `bandit` | Fase 5 |

## 13. Próximo passo

1. **Aprovar este spec.** Se aprovado:
2. Invocar `superpowers:writing-plans` para gerar plano de implementação passo-a-passo — cada bloco da Seção 9 vira uma tarefa detalhada com arquivos exatos, funções exatas, testes exatos.
3. Executar o plano em uma branch `feat/fase-2-segmentacao-dashboard`.
