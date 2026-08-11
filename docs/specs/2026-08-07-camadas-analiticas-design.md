# SellerPulse — Analytics Layers Design Doc

**Layer:** Analytics (metrics, segmentation, forecasting, patrimony) + Outputs (PDF, Dashboard, Notebook)
**Data:** 2026-08-07
**Status:** Design aprovado — implementação pendente (Fase 0 a seguir).

---

## 1. Contexto

O setor de ingestão (`auth`, `ml_client`, `storage`, `setup_auth`, `main`) já está implementado e testado — 33 testes verdes, spec correspondente em `docs/specs/2026-06-12-setor-4-ingestao-api-ml-design.md`.

Este documento cobre **tudo que vem acima da ingestão**: as 4 camadas analíticas puras (metrics, segmentation, forecasting, patrimony) e as 3 saídas que as consomem (PDF executivo, dashboard Streamlit, notebook narrativo).

Duas sessões de brainstorm precedem este design:

- **2026-08-03** — Pivot do projeto Tosh (serviço comercial) para **SellerPulse** (peça de portfólio para estágio em bancos BR). Fechadas Seções 1-2: formato "Full Analytics Suite" (mesma camada analítica alimentando PDF + notebooks + dashboard) e 3 decisões arquiteturais (camada analítica pura, CLI unificado, `demo.db` versionado + gerador com seed fixa).
- **2026-08-07** — Fechadas Seções 3-7 abaixo. Ambição consolidada como **"Quant Fund Analyst" MVP**: 9 análises + Monte Carlo patrimony + notebook narrativo estilo carta de gestor. Trade-off aceito: ~6.5 semanas de trabalho até `v1.0.0`, sem prazo específico de candidatura.

## 2. Goals & non-goals

### Goals

- Entregar **4 camadas analíticas puras** (funções `(conn, date_from, date_to, **opts) -> DataFrame | dict`, sem I/O, sem prints, sem rede) reutilizáveis pelas 3 saídas.
- Manter o **PDF executivo Corporate Executive** como face pública do projeto (identidade visual definida no mockup canônico) — agora com página nova de Patrimônio Monte Carlo.
- Publicar um **dashboard Streamlit interativo** no Streamlit Community Cloud com link público (`sellerpulse.streamlit.app`).
- Publicar um **notebook narrativo** que conte a história analítica ponta a ponta, estilo carta de gestor.
- Sustentar **80% coverage global** com CI matrix (py311/312/313 × ubuntu/windows) e quality gates (ruff, mypy strict, bandit).
- Entregar em **fases versionadas** (v0.1.0-alpha → v1.0.0), cada uma com tag + push, para que o repo mostre atividade consistente ao longo de 6.5 semanas.

### Non-goals

- Multi-tenant / SaaS. Continua sendo uma instância local por vendedor.
- Análises em tempo real. Recorte semanal é suficiente.
- Otimização estocástica de portfólio real (o "patrimony" aqui é um exercício analítico ilustrativo sobre reinvestimento de caixa, não conselho financeiro).
- E2E testing com Selenium, load testing, mutation testing, pixel-perfect PDF tests.

## 3. Decisões travadas no brainstorm

| Decisão | Escolha |
|---|---|
| Formato de entrega | **Full Analytics Suite** — PDF + notebook + dashboard alimentados pela mesma camada |
| Assinatura das análises | `def x(conn, date_from, date_to, **opts) -> pd.DataFrame \| dict` — puras, sem side effects |
| Persistência analítica | Nenhuma — métricas sempre recalculadas a partir do SQLite bruto |
| Ambição do MVP | **"Quant Fund Analyst"** — 9 análises + Monte Carlo patrimony + notebook narrativo |
| Hook narrativo | **Simulador patrimonial Monte Carlo** (a peça que difere de portfólios genéricos) |
| CLI | Unificado: `python -m src.main <ingerir\|gerar-pdf\|abrir-dashboard\|regerar-dados>` |
| Dados de demo | `data/demo.db` versionado (gerado com seed fixa por `demo_data.py`) |
| Deploy do dashboard | **Streamlit Community Cloud** (link público) |
| Tema visual | Corporate Executive (paleta navy/azul/dourado, Inter, sombras suaves) |
| Cronograma | 6 fases (v0.1.0-alpha → v1.0.0), ~6.5 semanas, sem janela de candidatura fixa |

## 4. Camada analítica — 9 análises + 1 hook

Distribuídas em 4 módulos. Todas seguem o contrato definido na Seção 3.

### 4.1. `src/metrics.py` — KPIs financeiros e operacionais

| # | Função | Saída | Uso |
|---|---|---|---|
| 1 | `fluxo_financeiro(conn, date_from, date_to)` | DataFrame por dia com receita bruta, taxas ML, frete, custo estimado, líquido + comparativo semana anterior | PDF P1, Dashboard P1 |
| 2 | `top_produtos(conn, date_from, date_to, n=10)` | DataFrame com top produtos e top categorias por faturamento e por unidades | PDF P2, Dashboard P2 |
| 3 | `reputacao_devolucao(conn, date_from, date_to)` | dict com nível ML, taxa de devolução, claims ativos, alertas | PDF P4, Dashboard P1 |

### 4.2. `src/segmentation.py` — segmentação de produtos e clientes

| # | Função | Saída | Uso |
|---|---|---|---|
| 4 | `abc_pareto(conn, date_from, date_to)` | DataFrame com produtos rankeados + classe A/B/C por receita acumulada (regra 80/15/5) | PDF P2 (curva compacta), Dashboard P2 |
| 5 | `rfm_scores(conn, date_from, date_to)` | DataFrame com Recency/Frequency/Monetary + score 1-5 por quintis + segmento (Champions, Loyal, At Risk, Hibernating, New) | Dashboard P3, Notebook |
| 6 | `cohort_produto(conn, date_from, date_to)` | DataFrame pivot (mês da 1ª venda × mês corrente → receita) — cohort **por produto**, não por comprador | Dashboard P2, Notebook |

> **Justificativa cohort por produto:** dados ML raramente permitem tracking longitudinal de comprador (buyers não têm ID persistente entre transações). Cohort por produto responde "produtos lançados em X ainda geram receita em Y?" que é mais acionável no contexto de vendedor.

### 4.3. `src/forecasting.py` — série temporal e anomalias

| # | Função | Saída | Uso |
|---|---|---|---|
| 7 | `forecast_sarima(conn, date_from, date_to, horizon=4)` | DataFrame com projeção 4 semanas à frente + banda de confiança + MAPE do backtest walk-forward (8 semanas). Sazonalidade fixa em 4 (mensal em série semanal) | PDF P1 (micro-chart no rodapé), Dashboard P4 |
| 8 | `detectar_anomalias(conn, date_from, date_to, sensibilidade=1.5)` | DataFrame de pontos anômalos via STL decomposition + limiar 1.5×IQR sobre o resíduo | PDF P4 (área "Alertas"), Dashboard P4 |

### 4.4. `src/patrimony.py` — simulador Monte Carlo (o hook)

| # | Função | Saída | Uso |
|---|---|---|---|
| 9 | `simular_alocacao(conn, date_from, date_to, capital, alocacao, n_trajetorias=10000)` | dict com trajetórias Monte Carlo + VaR 5% + CVaR 5% + Sharpe + estatísticas descritivas | Dashboard P5 (what-if) |
| 9b | `recomendar_perfis(conn, date_from, date_to, capital)` | dict com 3 perfis (conservador, moderado, agressivo) — cada um com alocação ótima na efficient frontier + métricas | PDF P3, Dashboard P5 |
| 9c | `backtest_recomendacao(conn, date_from, date_to, perfil)` | DataFrame 12 semanas com performance da estratégia vs. baseline "manter caixa parado" | PDF P3, Dashboard P5 |

**O que a simulação modela:** dado o caixa líquido semanal projetado pela `forecasting.py`, quanto reinvestir em (a) estoque de produtos A, (b) impulsionamento de anúncios, (c) reserva de caixa — sob quais premissas de retorno esperado e volatilidade, e qual o VaR/CVaR de cada mix. Não é otimização estocástica industrial — é um exercício analítico ilustrativo que demonstra domínio de estatística financeira.

**Números fixados:** 10.000 trajetórias, horizonte 12 semanas, grid de alocações amostrado uniformemente sobre o simplex de 3 dimensões, VaR/CVaR ao nível de 5%.

## 5. PDF executivo — 4 páginas Corporate Executive

Mantém a identidade visual do mockup canônico em `mockup/relatorio.html` (paleta navy/azul/dourado, Inter, sombras suaves, estilo McKinsey). Ganha 1 página nova (P3) e adições localizadas nas outras 3.

| Página | Conteúdo | Fonte |
|---|---|---|
| **P1 — Fluxo financeiro** | KPIs semanais + waterfall receita → líquido + comparativo semana anterior. **Novo:** micro-chart de forecast (próximas 4 semanas com banda) no rodapé. | `metrics.fluxo_financeiro` + `forecasting.forecast_sarima` |
| **P2 — Produtos** | Top 3 peças + top 3 categorias. **Novo:** curva Pareto ABC compacta ao lado. | `metrics.top_produtos` + `segmentation.abc_pareto` |
| **P3 — Patrimônio Monte Carlo** *(nova)* | Hero com recomendação (perfil moderado) + scatter da efficient frontier com 3 pontos destacados + tabela de backtest 12 semanas | `patrimony.recomendar_perfis` + `patrimony.backtest_recomendacao` |
| **P4 — Saúde operacional** | Reputação + devoluções + caixa "Considerações da semana". **Novo:** área "Alertas" com anomalias STL em pílulas coloridas. | `metrics.reputacao_devolucao` + `forecasting.detectar_anomalias` |

**Fora do PDF (vivem só no dashboard + notebook):** RFM, cohort. Razão: dashboards exploratórios servem melhor essas visualizações (drill-down), e o PDF perderia foco executivo se acumulasse tudo.

**Trabalho de mockup estimado:** ~2-3 dias para desenhar P3 nova + adições em P1/P2/P4 antes de iniciar `pdf_renderer.py`.

## 6. Dashboard Streamlit — 5 páginas + sidebar global

Multi-page app em `src/dashboard.py`. Deploy no **Streamlit Community Cloud** com link público estilo `sellerpulse.streamlit.app`.

**Sidebar global:** seletor de período, toggle Demo/Real, filtro de categoria, versão do build.

| Página | Conteúdo | Fonte |
|---|---|---|
| **P1 — Executive Summary** | Espelha o PDF: KPIs + waterfall + forecast + comparativo semana anterior | `metrics.*` + `forecasting.forecast_sarima` |
| **P2 — Product Analytics** | Top produtos/categorias interativo + Pareto ABC + heatmap de cohort | `metrics.top_produtos` + `segmentation.abc_pareto` + `segmentation.cohort_produto` |
| **P3 — Customer Analytics** | RFM scatter + distribuição por segmento + drill-down por segmento | `segmentation.rfm_scores` |
| **P4 — Time Series & Anomalias** | Série semanal + STL decomposition (trend/seasonal/residual) + anomalias na timeline + slider de sensibilidade IQR | `forecasting.forecast_sarima` + `forecasting.detectar_anomalias` |
| **P5 — Patrimony Simulator** *(estrela)* | Sliders de restrições + efficient frontier interativa + 3 cards de recomendação + what-if playground (histograma Monte Carlo interativo) + backtest 12 semanas | `patrimony.*` |

**UX decisões:**
- Tema light default + toggle dark opcional via `.streamlit/config.toml`.
- Interatividade 100% via Plotly + widgets Streamlit.
- SKUs sintéticos com nomes realistas via Faker (evita "Produto A1", "Produto B2" que quebram a ilusão de dashboard real).

## 7. Roadmap — 6 fases, ~6.5 semanas

Sem janela específica de candidatura. Cada fase termina com tag semver + push. Posts LinkedIn oportunos após Fases 1, 3 e 5.

| Fase | Duração | Tag | Entregável |
|---|---|---|---|
| **0 — Fundação** | 1 sem | `v0.1.0-alpha` | `demo_data.py` completo, CLI unificado esqueleto, CI GitHub Actions verde |
| **1 — Métricas + PDF v0.1** | 1 sem | `v0.2.0` | `metrics.py`, `pdf_renderer.py` com P1+P2+P4 (sem anomalias) |
| **2 — Segmentação + Dashboard** | 1 sem | `v0.3.0` | `segmentation.py` (ABC/RFM/cohort), dashboard páginas 1-3 |
| **3 — Forecasting + Time Series** | 1 sem | `v0.4.0` | `forecasting.py` (SARIMA + STL anomalies), dashboard P4, alertas na PDF P4 |
| **4 — Patrimony (o hook)** | 1.5 sem | `v0.5.0` | `patrimony.py` (Monte Carlo + efficient frontier + backtest), PDF P3 nova, dashboard P5 |
| **5 — Polish + Launch** | 1 sem | `v1.0.0` | Notebook narrativo, deploy Streamlit Cloud, README final, LinkedIn post principal |

## 8. Estratégia de testes

**Coverage target global:** 80%, badge Codecov no README.

### Tipos de teste por módulo

| Módulo | Estratégia |
|---|---|
| Módulos existentes (`auth`, `ml_client`, `storage`, `main`, `setup_auth`) | Já testados — 33 testes atuais, 85%+ coverage |
| `demo_data.py` | Unit + **determinismo**: mesma seed produz DB byte-identical |
| `metrics.py` | Unit com fixture DB determinístico |
| `segmentation.py` | Unit + **propriedades matemáticas**: soma dos pcts = 100%, ordenação ABC correta, RFM scores ∈ [1,5] |
| `forecasting.py` | Unit + **testes estatísticos**: MAPE < 15% em sinal sintético conhecido; anomalias injetadas são detectadas; sazonalidade recuperada |
| `patrimony.py` | Unit + **property tests** via `hypothesis`: alocação soma ao caixa; VaR ≤ mediana ≤ média; recomendação domina baseline em backtest |
| `pdf_renderer.py` | **Snapshot tests** via `pytest-regressions` contra HTML golden file |
| `dashboard.py` | Smoke tests via `streamlit.testing` — só valida load das páginas |

### CI Matrix (evolutiva)

- **Fase 0 (mínimo):** Python 3.11 × [ubuntu-latest, windows-latest] = 2 jobs.
- **Fase 5 (final):** Python [3.11, 3.12, 3.13] × [ubuntu-latest, windows-latest] = 6 jobs.

### Quality gates

- `ruff format` + `ruff check` (formatação + linter modernos, substitui black+isort+flake8).
- `mypy --strict` nos módulos analíticos (adicionado na Fase 5).
- `bandit` no código OAuth (security linter).

### Explicitamente fora

E2E Selenium, load testing, mutation testing, pixel-perfect PDF tests, fuzz testing.

## 9. Arquivos críticos a criar/modificar

### Novos módulos (`src/`)

- `src/demo_data.py` — gerador de dados sintéticos com `random.seed(42)`
- `src/metrics.py` — fluxo financeiro + top produtos + reputação × devolução
- `src/segmentation.py` — ABC + RFM + cohort
- `src/forecasting.py` — SARIMA + STL anomalies
- `src/patrimony.py` — Monte Carlo simulator + efficient frontier + backtest
- `src/pdf_renderer.py` — HTML + WeasyPrint + Jinja2
- `src/dashboard.py` — Streamlit multi-page

### Modificar

- `src/main.py` — refactor para CLI unificado com subcomandos (`ingerir`, `gerar-pdf`, `abrir-dashboard`, `regerar-dados`)
- `mockup/relatorio.html` — adicionar P3 nova (patrimony), micro-forecast em P1, ABC compacta em P2, alertas em P4
- `requirements.txt` — adicionar pandas, numpy, statsmodels, scikit-learn, matplotlib, seaborn, plotly, streamlit, weasyprint, jinja2, faker, pmdarima, scipy, hypothesis, pytest-cov, pytest-regressions, ruff, mypy, bandit
- `README.md` — atualizar Status matrix conforme fases entregam, adicionar screenshots + link do dashboard live + case study
- `pyproject.toml` — configurar ruff, mypy, coverage

### Novos artefatos

- `data/demo.db` — versionado (SQLite ~1-5 MB com dados sintéticos)
- `notebooks/01-case-study.ipynb` — narrativa completa estilo carta de gestor
- `.github/workflows/tests.yml` — CI matrix
- `.streamlit/config.toml` — tema light/dark opcional
- `data/business_config.yaml.example` — template para modo real

## 10. Verificação — critério de aceite por fase

**Fase 0** — `python -m src.main regerar-dados && python -m src.main --help` gera `data/demo.db` e mostra subcomandos. `pytest` verde. CI verde.

**Fase 1** — `python -m src.main gerar-pdf` produz PDF em `RELATORIOS/` com P1+P2+P4. Coverage `metrics.py` ≥ 85%. Snapshot test do HTML passa.

**Fase 2** — `python -m src.main abrir-dashboard` sobe Streamlit local com 3 páginas navegáveis. Todas carregam sem erro. Coverage `segmentation.py` ≥ 85%.

**Fase 3** — Dashboard tem 4 páginas. PDF P4 mostra área de "Alertas" quando `forecasting.detectar_anomalias()` retorna anomalias no fixture. MAPE do backtest SARIMA < 15% em dados sintéticos.

**Fase 4** — PDF P3 renderiza. `python -c "from src.patrimony import simular_alocacao; ..."` roda em <10s. Property tests via `hypothesis` passam. Dashboard P5 permite interação what-if.

**Fase 5** — `streamlit run src/dashboard.py` no Streamlit Cloud responde. README com todos os screenshots. Coverage global ≥ 80%. `mypy --strict src/` sem erros. `bandit src/` sem HIGH.

## 11. Fora de escopo destas camadas

| Tema | Camada que cuida |
|---|---|
| OAuth ML + ingestão + persistência bruta | Setor 4 (`auth`, `ml_client`, `storage`, `setup_auth`, `main`) — já implementado |
| Otimização estocástica industrial de portfólio | Fora do escopo — patrimony é exercício analítico ilustrativo |
| Tracking longitudinal de compradores | Fora do escopo — dados ML não permitem; cohort é por produto |
| Alertas por email/push | Fora do escopo — geração sob demanda via CLI |

## 12. Próximos passos

1. **Aprovar este spec doc.** Se aprovado, prosseguir para o passo 2.
2. **Escrever plano de implementação da Fase 0** (`superpowers:writing-plans`) — função por função, teste por teste: `demo_data.py`, refactor de `main.py` para CLI unificado, `.github/workflows/tests.yml`, primeira tag `v0.1.0-alpha`.
3. Cada Fase 1-5 ganha seu próprio ciclo brainstorm → plan → execute conforme for chegando (não pré-planejar tudo de uma vez — as análises se refinam à medida que os dados aparecem).
