# SellerPulse

> **Full Analytics Suite for Mercado Livre sellers — from raw orders to executive decisions.**

Pipeline analítico completo para vendedores do Mercado Livre: ingere pedidos via API oficial (OAuth 2.0), consolida em SQLite, e entrega insights em três formatos — relatório executivo em PDF, notebooks Jupyter narrativos e dashboard Streamlit interativo. Uma única camada analítica pura alimenta as três saídas.

[![tests](https://github.com/carrerigcg/sellerpulse/actions/workflows/tests.yml/badge.svg)](https://github.com/carrerigcg/sellerpulse/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-v0.1.0--alpha-blue.svg)

---

## 📊 Status atual

| Módulo | Estado |
|---|---|
| Ingestão OAuth Mercado Livre (`auth.py`, `ml_client.py`, `setup_auth.py`) | ✅ Pronto — 33 testes passando |
| Persistência SQLite com UPSERTs idempotentes (`storage.py`) | ✅ Pronto |
| Orquestrador CLI de ingestão (`main.py`) | ✅ Pronto |
| Dados sintéticos reprodutíveis (`demo_data.py`) | ✅ Pronto — `data/demo.db` versionado, determinístico via seed 42 |
| Camada analítica pura (`metrics.py`, `segmentation.py`, `forecasting.py`, `patrimony.py`) | 🚧 Em construção |
| Renderizador de PDF executivo (`pdf_renderer.py`) | 🚧 Em construção — mockup visual em `mockup/relatorio.html` |
| Dashboard Streamlit (`dashboard.py`) | 🚧 Em construção |
| Notebooks Jupyter narrativos (`notebooks/`) | 🚧 Em construção |
| CI GitHub Actions | ✅ Pronto — matrix py3.11 × ubuntu/windows, ruff + pytest |

---

## 🎯 Visão geral

**Problema.** O vendedor médio do Mercado Livre tem acesso a um painel operacional, mas não a uma leitura estratégica dos próprios dados. Fica difícil responder perguntas simples: *"quanto sobrou de lucro na semana?"*, *"quais produtos empurram meu faturamento?"*, *"vale a pena reinvestir esse caixa em estoque ou segurar?"*.

**Solução.** SellerPulse consome a API oficial do ML, consolida os dados de vendas em SQLite, e roda uma bateria de análises (segmentação ABC/RFM, forecast sazonal, detecção de anomalias, simulação patrimonial) que se materializam em três formatos complementares:

- **PDF executivo** — leitura de 3 páginas no padrão consultoria (McKinsey/BCG).
- **Notebooks Jupyter** — narrativa exploratória para quem quer entender a metodologia.
- **Dashboard Streamlit** — interativo, com filtros e drill-down.

**Hook narrativo.** O módulo `patrimony.py` implementa um simulador de reinvestimento: dado o caixa gerado na semana e as restrições operacionais do vendedor, propõe cenários de alocação (estoque × reserva × marketing). É a camada que transforma "relatório de vendas" em "assistente de decisão patrimonial".

---

## 🚀 Quick start

```bash
git clone https://github.com/carrerigcg/sellerpulse.git
cd sellerpulse
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
pytest
```

O modo **sintético** é o padrão — clone e execute em segundos, sem credenciais (o `data/demo.db` já vem versionado no repo):

```bash
python -m src.main gerar-pdf         # gera PDF em RELATORIOS/relatorio-YYYY-WNN.pdf
python -m src.main abrir-dashboard   # sobe Streamlit em localhost:8501            [Fase 2]
python -m src.main regerar-dados     # reconstrói data/demo.db a partir do gerador
```

> **Windows:** `gerar-pdf` depende do WeasyPrint, que requer o runtime GTK3.
> Instale via [GTK3 for Windows Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) — sem isso o comando falha com `libgobject-2.0-0`. Em Linux/macOS o `pip install` já cobre as libs nativas.

O modo **API real** (opcional — requer conta ML + credenciais em `.env`):

```bash
cp .env.example .env                 # preencha ML_CLIENT_ID e ML_CLIENT_SECRET
python -m src.setup_auth             # autoriza 1 vez via browser
python -m src.main --week=2026-W32   # ingere semana ISO específica
```

---

## 🏗️ Arquitetura

```
┌──────────────────────────────────────────────────────┐
│  Fontes de dados                                     │
│  ┌────────────────────┐    ┌─────────────────────┐  │
│  │  demo_data.py      │    │  ml_client.py       │  │
│  │  Faker + regras    │    │  OAuth 2.0 ML       │  │
│  │  (padrão)          │    │  (opcional)         │  │
│  └─────────┬──────────┘    └──────────┬──────────┘  │
└────────────┼──────────────────────────┼─────────────┘
             │                          │
             └────────────┬─────────────┘
                          ▼
                ┌──────────────────┐
                │  data/demo.db    │
                │  SQLite          │
                └────────┬─────────┘
                         ▼
        ┌────────────────────────────────────┐
        │  Camada analítica pura             │
        │  (recebe conn, devolve DataFrame)  │
        │                                    │
        │  metrics · segmentation            │
        │  forecasting · patrimony           │
        └───┬────────────┬────────────┬──────┘
            ▼            ▼            ▼
       ┌─────────┐  ┌─────────┐  ┌────────────┐
       │  PDF    │  │Notebook │  │ Dashboard  │
       │executivo│  │ Jupyter │  │ Streamlit  │
       └─────────┘  └─────────┘  └────────────┘
```

**Princípio central:** a camada analítica é **100% pura** — funções recebem `conn` (conexão SQLite) e devolvem `pd.DataFrame`. Sem side effects, sem I/O, sem chamadas de API. Isso garante que uma mudança de fórmula é aplicada 1x e propaga automaticamente para as 3 saídas.

---

## 🧠 Análises implementadas / previstas

| Análise | Módulo | Descrição |
|---|---|---|
| **Fluxo financeiro semanal** | `metrics.py` | Receita bruta − taxas ML − frete pago − custo estimado = líquido. Base de tudo. |
| **Top produtos & categorias** | `metrics.py` | Ranking por faturamento e por unidades — sinaliza motores do negócio. |
| **Segmentação ABC** | `segmentation.py` | Curva de Pareto: quais SKUs concentram 80% da receita. |
| **Segmentação RFM** | `segmentation.py` | Recency-Frequency-Monetary para caracterização de tipo de venda. |
| **Análise de cohort** | `segmentation.py` | Comportamento por cohort de mês de primeira venda. |
| **Forecast sazonal** | `forecasting.py` | ARIMA/Prophet para projeção de 4 semanas à frente. |
| **Detecção de anomalias** | `forecasting.py` | Flag automático de semanas fora do padrão histórico. |
| **Reputação × devolução** | `metrics.py` | KPI operacional — proxy de saúde da conta ML. |
| **Simulador patrimonial** | `patrimony.py` | Cenários de reinvestimento do caixa gerado. |

---

## 🛠️ Stack

- **Runtime:** Python 3.11+
- **Data:** SQLite (via `sqlite3` da stdlib), `pandas`, `numpy`
- **Modelagem:** `statsmodels`, `scikit-learn`
- **Visualização estática:** `matplotlib`, `seaborn`
- **Visualização interativa:** `plotly`, `streamlit`
- **PDF:** `weasyprint` + `jinja2`
- **HTTP + OAuth:** `requests`, `python-dotenv`
- **Dados sintéticos:** `faker`
- **Testes:** `pytest`, `responses` (mock HTTP)
- **CI:** GitHub Actions (matrix py3.11 × ubuntu/windows)

---

## 📁 Estrutura do repositório

```
sellerpulse/
├── src/
│   ├── auth.py              # OAuth 2.0: autorização + refresh rotativo
│   ├── ml_client.py         # cliente HTTP ML com retry, paginação, rate limit
│   ├── storage.py           # camada SQLite (schema + UPSERTs idempotentes)
│   ├── setup_auth.py        # bootstrap OAuth one-shot
│   ├── main.py              # CLI unificado — subcomandos
│   ├── demo_data.py         # gerador de dados sintéticos (seed fixa)
│   ├── metrics.py           # cálculos financeiros e operacionais
│   ├── pdf_renderer.py      # HTML + WeasyPrint → PDF
│   ├── segmentation.py      # ABC, RFM, cohort                                 [TODO]
│   ├── forecasting.py       # ARIMA, detecção de anomalias                    [TODO]
│   ├── patrimony.py         # simulador de reinvestimento                     [TODO]
│   └── dashboard.py         # app Streamlit                                    [TODO]
├── templates/
│   └── relatorio.html.j2    # template Jinja2 do PDF executivo
├── tests/                   # pytest — 84 testes cobrindo auth, ml_client, storage, main, demo_data, metrics, pdf_renderer
├── notebooks/               # 4 notebooks narrativos                          [TODO]
├── mockup/
│   └── relatorio.html       # referência visual do PDF (padrão Corporate Executive)
├── docs/
│   └── specs/               # design docs de cada camada
├── data/                    # SQLite (demo.db versionado; tokens/historico.db ignorados)
├── .env.example
├── requirements.txt
├── pyproject.toml
└── LICENSE
```

---

## 🔌 Conexão com conta ML real (opcional)

O modo padrão do SellerPulse é **100% sintético e reprodutível** — não precisa de credenciais. A camada de ingestão real via API ML fica disponível como conector opcional, útil para quem quer alimentar o pipeline com dados de uma conta real.

Fluxo de setup (uma única vez):

1. Criar aplicação em https://developers.mercadolivre.com.br → obtém `CLIENT_ID` e `CLIENT_SECRET`.
2. Configurar Redirect URI: `http://localhost:8080/callback`.
3. Copiar `.env.example` → `.env` e preencher.
4. Executar `python -m src.setup_auth` — abre o browser, autoriza, salva `data/tokens.json` com refresh token rotativo (válido por 6 meses; renovação subsequente é automática).

Após o bootstrap, qualquer execução usa o token válido corrente e rotaciona o refresh automaticamente. A camada de ingestão implementa retry com backoff, tratamento de 429 (rate limit), refresh de token durante execução em caso de 401, e persistência atômica do refresh rotativo (evita perda de acesso em caso de crash entre o POST de refresh e a próxima chamada).

---

## 🧪 Testes

```bash
pytest                           # roda toda a suíte
pytest tests/test_auth.py -v     # apenas módulo específico
pytest --cov=src                 # cobertura (requer pytest-cov)
```

A suíte cobre:
- OAuth: exchange de code, refresh rotativo, persistência atômica, tratamento de erros.
- Cliente ML: paginação de `/orders/search`, retry em 5xx, respeito a `Retry-After` em 429, parsing de payloads reais.
- Storage: UPSERTs idempotentes, TTL de caches, versionamento de schema, isolamento por transação.
- Orquestrador: resolução de janelas (--week, --from/--to, default), logging de runs, propagação de erros.

---

## 📜 Licença

[MIT](./LICENSE) — livre uso comercial e pessoal, com atribuição.

---

## 👤 Autor

**Guilherme Carreri** — analista de dados, aplicando para posições de estágio em BI / Data & Analytics.

Feedback, sugestões de análise ou colaboração: [carreri.gui@gmail.com](mailto:carreri.gui@gmail.com)
