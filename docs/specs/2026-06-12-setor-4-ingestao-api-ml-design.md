# SellerPulse — Ingestion Layer Design Doc

**Layer:** Ingestion (API + persistence)
**Data:** 2026-06-12
**Status:** Implementado — 33 testes passando.

---

## 1. Contexto

SellerPulse é um pipeline analítico para vendedores do Mercado Livre. Este documento define **como o pipeline busca e armazena os dados brutos** que alimentam as camadas analíticas superiores (metrics, segmentation, forecasting, patrimony).

O SellerPulse opera em dois modos:

- **Modo sintético (padrão):** dados gerados por `src/demo_data.py` — não requer conexão externa.
- **Modo real (opcional):** ingestão via API oficial ML com OAuth 2.0.

Este doc cobre o **modo real** — a ingestão OAuth + persistência SQLite.

Decisões de camadas superiores relevantes para este design:
- **Stack:** Python, execução manual via CLI unificado (`python -m src.main <subcomando>`).
- **Saídas:** PDF executivo (WeasyPrint), Notebooks Jupyter, Dashboard Streamlit — todos consomem a mesma camada analítica pura sobre SQLite.
- **Janela default:** "últimos 7 dias" + "7 dias anteriores" para comparação.
- **Métricas do relatório executivo:** líquido recebido, top peças, top categorias, devoluções, reputação ML.

## 2. Goals & non-goals

### Goals
- Fluxo OAuth funcional: 1 autorização inicial → 6 meses de execuções sem intervenção.
- Buscar dados suficientes para as métricas do relatório executivo e demais camadas analíticas.
- Persistir dados crus localmente para auditoria, re-execução de semanas passadas, e independência da disponibilidade da API ML no momento da geração.
- Idempotência: rodar 2x a mesma janela produz o mesmo resultado, sem duplicação.

### Non-goals
- Multi-tenant (múltiplas contas ML simultâneas). Ingestão hoje serve 1 conta por instância.
- Sync em tempo real / webhooks ML. Cadência sob demanda é suficiente.
- Análises longitudinais de longo prazo — cobertas pela camada `forecasting.py`.
- Dashboard web / UI de ingestão. Saídas são responsabilidade das camadas superiores.

## 3. Decisões travadas no brainstorm

| Decisão | Escolha |
|---|---|
| Organização do código | Pacote modular: `auth.py`, `ml_client.py`, `storage.py`, `main.py`, `setup_auth.py` |
| Persistência | SQLite local em `data/historico.db` |
| Storage de secrets | `.env` (`ML_CLIENT_ID`, `ML_CLIENT_SECRET`) + `data/tokens.json` (tokens rotativos, com ACL no Windows) |
| HTTP client | `requests` síncrono (~30-50 chamadas por execução — async é overkill) |
| Refresh token | Rotação obrigatória a cada uso: novo `refresh_token` persistido ANTES da próxima chamada |
| Modo de execução | CLI: default (últimos 7 dias) + flags `--week=YYYY-WNN` e `--from/--to` para janelas explícitas |

## 4. Arquitetura — módulos

```
sellerpulse/
├── data/
│   ├── historico.db                  # SQLite (modo real)
│   ├── demo.db                       # SQLite (modo sintético)
│   └── tokens.json                   # access + refresh tokens (rotativos)
├── docs/specs/                       # design docs como este
├── mockup/                           # mockup HTML do PDF
├── src/
│   ├── __init__.py
│   ├── auth.py                       # OAuth: autorização inicial + refresh
│   ├── ml_client.py                  # cliente HTTP para endpoints ML (com retry)
│   ├── storage.py                    # repositório SQLite (orders, items, claims, runs)
│   ├── setup_auth.py                 # script standalone: bootstrap OAuth
│   ├── main.py                       # orquestrador CLI
│   └── ...                           # metrics, segmentation, forecasting, patrimony, renderers
├── tests/
├── .env                              # CLIENT_ID, CLIENT_SECRET
├── .env.example                      # template versionado
├── .gitignore                        # .env, data/, RELATORIOS/, __pycache__
├── requirements.txt
└── pyproject.toml
```

**Responsabilidades:**

- **`auth.py`** — único módulo que conhece o protocolo OAuth. Expõe `get_valid_access_token()` que decide internamente se renova ou usa o cache. Lê/grava `data/tokens.json`.
- **`ml_client.py`** — recebe um `access_token` e faz chamadas HTTP. Sabe paginar `/orders/search`, fazer retry com backoff em 5xx, lidar com 429 (rate limit). Não persiste nada.
- **`storage.py`** — SQLite. UPSERT de orders, items, claims. Consultas pré-feitas para as camadas superiores. Schema versionado via tabela `schema_version`.
- **`main.py`** — orquestrador. Parseia CLI args, chama `auth`, `ml_client`, `storage` na ordem. Loga em `runs`.
- **`setup_auth.py`** — script standalone executado uma vez na configuração inicial. Abre navegador, captura código, popula `data/tokens.json` pela primeira vez.

## 5. Fluxo OAuth

### 5.1. Pré-requisito (uma única vez)

Criar aplicação no Mercado Livre Developer Center (developers.mercadolivre.com.br):
- Nome: `SellerPulse` (ou outro)
- Descrição: "Pipeline analítico para vendedores ML"
- Redirect URI: `http://localhost:8080/callback`
- Domínio: `localhost`
- Tópicos de notificação: nenhum (não usamos webhooks)

Resultado: `CLIENT_ID`, `CLIENT_SECRET` → salvar em `.env`.

### 5.2. Autorização inicial (uma única vez)

Executar `python -m src.setup_auth`. O script:

1. Abre o navegador padrão na URL:
   ```
   https://auth.mercadolivre.com.br/authorization?response_type=code&client_id={CLIENT_ID}&redirect_uri=http://localhost:8080/callback
   ```
2. Sobe um servidor HTTP temporário na porta 8080, esperando o callback.
3. Usuário faz login com sua conta ML e clica "Autorizar".
4. ML redireciona para `http://localhost:8080/callback?code=ABC123...`
5. Script captura o `code`, faz POST para `https://api.mercadolibre.com/oauth/token`:
   ```
   grant_type=authorization_code
   client_id={CLIENT_ID}
   client_secret={CLIENT_SECRET}
   code={code_capturado}
   redirect_uri=http://localhost:8080/callback
   ```
6. Recebe `{access_token, token_type, expires_in, refresh_token, scope, user_id}`.
7. Persiste em `data/tokens.json` com `expires_at = now + expires_in segundos`.
8. Mostra mensagem: "Autorização concluída. Agora você pode rodar `python -m src.main`."

### 5.3. Renovação automática (a cada execução)

Quando `main.py` precisa do token, chama `auth.get_valid_access_token()`:

1. Lê `data/tokens.json`.
2. Se `expires_at` é no futuro com folga (> 10 min), devolve `access_token` direto.
3. Se expirou ou está perto: POST `/oauth/token` com `grant_type=refresh_token` e o `refresh_token` atual.
4. Recebe novo par `{access_token, refresh_token, expires_in}`.
5. **Sobrescreve `data/tokens.json` ANTES de retornar.** Crítico — perder o novo refresh = perder acesso permanente.
6. Devolve o novo `access_token`.

### 5.4. Falha de refresh

Se a chamada de refresh devolver 4xx (refresh expirou ou foi invalidado):
- Loga erro claro em `runs`.
- Sai com exit code != 0.
- Mensagem em `runs.error_message` instruindo: "Refresh token inválido. Re-rodar `python -m src.setup_auth` para reautorizar."

## 6. Endpoints ML — mapeamento por análise

Base URL: `https://api.mercadolibre.com`. Todos com header `Authorization: Bearer {access_token}`.

### 6.1. Pedidos (fluxo financeiro + top produtos + devoluções)

```
GET /orders/search?seller={USER_ID}
  &order.status=paid          # apenas pedidos efetivados
  &order.date_created.from={ISO8601}
  &order.date_created.to={ISO8601}
  &sort=date_desc
  &limit=50
  &offset=0
```

Paginação: incrementar `offset` em 50 até `paging.total` ser alcançado.

Cada pedido em `results[]` traz, entre outros:
- `id` (order_id)
- `date_closed`
- `status` (`paid`, `cancelled`, etc.)
- `total_amount`
- `payments[].marketplace_fee` (taxa ML)
- `shipping.list_cost` (frete pago pelo vendedor; 0 quando pago pelo comprador)
- `order_items[].item.id`, `quantity`, `unit_price`

### 6.2. Detalhes do item (nomes de produtos, categorias)

```
GET /items/{item_id}
```

Resposta traz `title` e `category_id`. **Cachear em `items_cache`** — esses campos só mudam se o vendedor editar o anúncio (raro). TTL: 30 dias (re-buscar no próximo run após).

### 6.3. Nome da categoria (top categorias)

```
GET /categories/{category_id}
```

Devolve `name`. **Cachear em `categories_cache` indefinidamente** — nomes de categorias ML praticamente nunca mudam.

### 6.4. Devoluções / claims

Duas fontes combinadas:

**(a) Pedidos cancelados pagos** — segunda query a `/orders/search` na mesma janela, filtrando `order.status=cancelled`. Critério de "devolução": pedido com `status=cancelled` cujo `date_closed` (data efetiva do fechamento/cancelamento) caia dentro da janela. Isso cobre pedidos que foram pagos e depois cancelados/devolvidos, mesmo que tenham sido criados antes da janela.

**(b) Reclamações formais ativas** — para o KPI de Reputação:
```
GET /post-purchase/v1/claims/search?seller_id={USER_ID}
  &date_created.from={ISO8601}
```

### 6.5. Reputação do vendedor

```
GET /users/{USER_ID}
```

Devolve `seller_reputation.level_id` (e.g., `"5_green"`, `"4_light_green"`, `"3_yellow"`, `"2_orange"`, `"1_red"`) e `seller_reputation.metrics.claims.value`.

Mapeamento de cor para o termômetro do relatório:
- `5_green`, `4_light_green` → "Verde · Excelente" (segmento 5)
- `3_yellow` → "Amarelo · Atenção" (segmento 3)
- `2_orange` → "Laranja · Cuidado" (segmento 2)
- `1_red` → "Vermelho · Crítico" (segmento 1)
- ausente → "Sem reputação ainda" (vendedor novo)

## 7. SQLite schema (`data/historico.db`)

```sql
CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE orders (
  order_id INTEGER PRIMARY KEY,
  date_closed TEXT NOT NULL,           -- ISO8601
  status TEXT NOT NULL,
  total_amount REAL NOT NULL,
  marketplace_fee REAL NOT NULL,
  shipping_cost REAL NOT NULL,
  buyer_id INTEGER,
  raw_json TEXT NOT NULL,              -- backup completo do pedido para auditoria
  fetched_at TEXT NOT NULL
);
CREATE INDEX idx_orders_date ON orders(date_closed);

CREATE TABLE order_items (
  order_id INTEGER NOT NULL REFERENCES orders(order_id),
  item_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price REAL NOT NULL,
  PRIMARY KEY (order_id, item_id)
);
CREATE INDEX idx_order_items_item ON order_items(item_id);

CREATE TABLE items_cache (
  item_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  category_id TEXT NOT NULL,
  fetched_at TEXT NOT NULL             -- usado para TTL de 30 dias
);

CREATE TABLE categories_cache (
  category_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);

CREATE TABLE claims (
  claim_id INTEGER PRIMARY KEY,
  order_id INTEGER,
  status TEXT NOT NULL,
  date_created TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);
CREATE INDEX idx_claims_date ON claims(date_created);

CREATE TABLE runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_at TEXT NOT NULL,
  week_start TEXT NOT NULL,
  week_end TEXT NOT NULL,
  pdf_path TEXT,
  status TEXT NOT NULL,                -- 'ok' | 'error'
  error_message TEXT
);
```

**Princípios do schema:**

- Métricas derivadas (líquido, top peças, etc.) NÃO são armazenadas. Sempre recalculadas a partir das tabelas brutas + cache. Permite mudar fórmulas sem migração e mantém a camada analítica pura.
- `raw_json` preserva a resposta original do ML — base para auditoria e backfill de campos futuros sem refetch.
- UPSERTs por `PRIMARY KEY` garantem idempotência (rodar 2x a mesma janela não duplica).
- `fetched_at` em todas as tabelas para TTL e debug.

## 8. Modos de execução

### 8.1. Default (última semana)

```bash
python -m src.main
```

Janela = "últimos 7 dias terminando agora".

### 8.2. Semana ISO específica

```bash
python -m src.main --week=2026-W23
```

Re-gera o dataset para a semana ISO 23 de 2026. Útil para:
- Sanity-check contra painel ML de uma semana passada
- Re-gerar relatório se o template mudar
- Debug

A re-execução usa o SQLite quando disponível; só chama a API para gaps (caso a semana não tenha sido capturada ainda).

### 8.3. Janela explícita

```bash
python -m src.main --from=2026-08-01 --to=2026-08-08
```

Range arbitrário de datas — útil para análises ad-hoc além do slot semanal.

## 9. Tratamento de erros

- **HTTP 429 (rate limit):** lê header `Retry-After` se presente, dorme, tenta de novo. Máx 3 tentativas.
- **HTTP 5xx:** retry com backoff exponencial (1s, 2s, 4s). Máx 3 tentativas.
- **HTTP 401 (token expirado durante run):** chama `auth.refresh()` uma vez e retenta a chamada.
- **HTTP 4xx exceto 401/429:** loga, marca `runs.status='error'`, sai sem prosseguir.
- **Refresh token inválido:** mensagem instrutiva em `runs.error_message`, exit code != 0.
- **Falha do SQLite:** propaga exceção (deve ser raro com SQLite local; indica corrupção do arquivo).

## 10. Verificação end-to-end

Para validar a implementação:

1. **Setup inicial em máquina limpa:** seguir o passo a passo do Dev Center, rodar `setup_auth.py`, conferir que `data/tokens.json` foi criado com `expires_at` no futuro.
2. **Refresh automático:** alterar manualmente `expires_at` para o passado em `data/tokens.json`, rodar `main.py`, conferir que o token foi rotacionado e a nova execução salvou novos valores.
3. **Refresh rotativo NÃO é perdido em caso de crash:** simular um crash entre o POST de refresh e a próxima chamada. Conferir que `tokens.json` foi salvo PRIMEIRO.
4. **Idempotência:** rodar `main.py` 2x para a mesma janela. Conferir que SQLite não duplica orders.
5. **Sanity-check vs painel ML:** rodar `--week=2026-W23` (semana passada real), comparar contagens e totais com o painel oficial. Tolerância: 0.
6. **Re-execução offline:** desligar internet, rodar `--week=2026-W23`. Como os dados já estão no SQLite, deve funcionar sem chamadas ML.
7. **Falha de rede:** desligar internet, rodar para janela NOVA. Conferir que `runs.status='error'` e nada é persistido parcialmente.

## 11. Fora de escopo desta camada

| Tema | Camada que cuida |
|---|---|
| Cálculo de métricas a partir dos dados crus | `metrics.py` |
| Segmentação de produtos e clientes | `segmentation.py` |
| Forecasting e detecção de anomalias | `forecasting.py` |
| Simulação de reinvestimento | `patrimony.py` |
| Geração do PDF executivo | `pdf_renderer.py` |
| Dashboard interativo | `dashboard.py` |
| Notebooks exploratórios | `notebooks/` |
| Geração de dados sintéticos | `demo_data.py` |

## 12. Próximos passos

Esta camada está implementada e testada (33 testes passando). Os próximos designs cobrem, na ordem:

1. **`demo_data.py`** — gerador sintético com `random.seed(42)` fixa, produzindo o mesmo `data/demo.db` a cada geração. Permite que o pipeline rode sem credenciais reais (modo padrão do repo).
2. **`metrics.py`** — camada analítica pura para os KPIs financeiros e operacionais.
3. **`segmentation.py`, `forecasting.py`, `patrimony.py`** — análises avançadas.
4. **`pdf_renderer.py`, `dashboard.py`, `notebooks/`** — as três saídas.
