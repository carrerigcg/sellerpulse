# SellerPulse — Fase 3: OAuth no Dashboard (v0.4.0)

**Fase:** 3 de 6 do roadmap
**Tag alvo:** `v0.4.0`
**Data:** 2026-08-19
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

Até a Fase 2 (`v0.3.0`, mergeada em `main`), o SellerPulse tem duas fontes de dados possíveis:

- **Modo Demo (padrão)** — SQLite `data/demo.db` versionado, gerado por `demo_data.py`. Zero credenciais, funciona no clone. É o modo que o dashboard usa hoje.
- **Modo Real via CLI** — `python -m src.setup_auth` faz OAuth via browser + callback em `localhost:8080`, salva `data/tokens.json`, e `python -m src.main --week=...` ingere pedidos. Funcional, mas exige clonar o repo, ter Python, e rodar terminal.

O sidebar do dashboard (`src/dashboard.py:41-51`) já expõe o toggle "Modo: Demo | Real", mas Real está desabilitado com aviso "Modo Real não disponível nesta versão — voltando para Demo." Esta fase **habilita o Real** de dentro do dashboard: o usuário clica em "Conectar minha conta ML", autoriza no ML, e o dashboard passa a mostrar os dados reais dele — tudo no browser, sem CLI, no app hospedado publicamente.

Estrategicamente, a fase inaugura o caminho pra SaaS: o modelo escolhido é single-tenant por sessão de browser (opção C do brainstorm — "SaaS de mentira"), mas com decisões arquiteturais tomadas hoje que preparam a migração pra multi-tenant real (opção B) sem rewrite.

Design baseado em decisões travadas em sessão de brainstorm 2026-08-19 (5 perguntas de clarificação + 3 seções de arquitetura aprovadas em sequência).

## 2. Goals & non-goals

### Goals

- Entregar botão "Conectar minha conta Mercado Livre" no dashboard, funcional em produção hospedada (Streamlit Community Cloud).
- Fluxo OAuth completo (authorize → callback → exchange → refresh) executado **dentro** do dashboard, sem depender de CLI.
- **Isolamento total por sessão de browser**: dois visitantes conectando contas diferentes ao mesmo tempo veem apenas seus próprios dados. Zero risco de vazamento cross-session.
- Ingestão automática dos **últimos 6 meses** de pedidos + itens + categorias + claims ao conectar, com UI de progresso em fases (`st.status`).
- Toggle Demo/Real funcional: usuário alterna livre entre visões após conectar. Dados em memória sobrevivem à alternância dentro da mesma sessão.
- Deploy público em `https://sellerpulse.streamlit.app/` funcional e HTTPS.
- Cobertura de testes ≥ 80% nos módulos novos (`session_auth.py`, `session_store.py`, `ingest.py`).
- Camada analítica (`metrics.py`, `segmentation.py`) **não modificada** — recebe `conn` genérico, indiferente à origem (demo ou real).
- Preparação arquitetural pro Fase 6/B: código dos novos módulos deve permitir migração pra multi-tenant Postgres + auth de usuário sem reescrita.
- Tag `v0.4.0` publicada.

### Non-goals

- **Multi-tenant real** — sem login de usuário, sem persistência de dados entre sessões, sem coexistência de múltiplos vendedores num mesmo backend. Isso é o objeto da Fase 6 (SaaS real).
- **Migração do frontend Streamlit → Next.js/FastAPI** — fica pra Fase 6. O dashboard Streamlit vai ser eventualmente substituído; esta fase só faz ele funcionar bem hospedado.
- **Persistência dos dados ingeridos entre sessões** — quando o usuário fecha a aba (ou o worker do Streamlit reinicia), os dados dele desaparecem. Comportamento intencional pra privacidade e simplicidade. Reconectar re-ingere.
- **Landing page comercial / marketing** — a "landing" é o próprio dashboard-first com toggle Demo. Fase 6 pode adicionar landing dedicada.
- **Publicação do app ML no marketplace público de aplicações** — pra portfólio, o app fica em modo desenvolvedor no ML e recrutadores são adicionados como test users explicitamente. Publicação plena exige processo de aprovação do ML que fica pra Fase 6.
- **Revogação ativa do token no ML (`/oauth/revoke`)** — desconectar limpa `session_state` (o token some da memória) mas não chama endpoint de revoke. Tokens ML expiram em 6h de qualquer jeito. Revoke ativo é backlog.
- **Cache persistente / cron de re-ingestão** — cada sessão ingere do zero. Otimização pra Fase 6.
- **Ingestão em background / worker queue** — ingestão bloqueia a sessão do usuário (com progresso visual). Aceitável pros ~30-50s esperados. Worker queue fica pra Fase 6.
- **Suporte a conexão simultânea de múltiplas contas ML na mesma sessão** — uma conta por sessão. Trocar de conta = desconectar + reconectar.

## 3. Decisões travadas no brainstorm

Cinco decisões resolvidas em sessão 2026-08-19. Cada uma cita a alternativa preterida.

| # | Decisão | Escolha | Alternativas preteridas |
|---|---|---|---|
| 1 | Escopo do modelo | **C** — single-tenant por sessão, roadmap C → B no futuro | A (só pessoal local); B (multi-tenant real agora) |
| 2 | Ambiente de execução | **Hospedado público** (Streamlit Community Cloud) | Local only; Ambos (local + hospedado) |
| 3 | Isolamento entre visitantes concorrentes | **A** — sessão por visitante via `st.session_state`, SQLite in-memory por sessão | B (estado global "conta ativa"); C (só demo hospedado, real só local) |
| 4 | Janela de ingestão ao conectar | **6 meses fixos** | 4 semanas; 12 meses; progressivo (4sem → 6m em background); usuário escolhe |
| 5 | UX da toggle Demo/Real | **Dashboard-first + toggle Demo/Real na sidebar** | Landing com escolha explícita; dashboard-first sem toggle (só substitui a fonte) |
| 6 | Abordagem técnica geral | **A** — 100% Streamlit-nativo (session_state + query_params + SQLite in-memory) | B (Upstash Redis pra sessões); C (FastAPI separado só pro callback) |

### Decisões de arquitetura future-proof (custo zero agora, ganho grande na migração pro B)

Três decisões conscientes tomadas mesmo em modo single-tenant, especificamente pra facilitar migração futura pro multi-tenant:

1. **Tokens indexados por `ml_seller_id`** — o `InMemoryTokenStore` já guarda com chave `seller_id`, mesmo com 1 entrada só. Schema idêntico ao que vira row no Postgres depois.
2. **Coluna `seller_id` em todas as tabelas analíticas ingeridas** — mesmo que sempre com o mesmo valor no C, a coluna já existe. Adicionar coluna depois com dados populados é sempre pior.
3. **OAuth completamente desacoplado do Streamlit** — `session_auth.py` é módulo puro Python (recebe `state`, `code`, `redirect_uri`; devolve `authorize_url` ou `TokenSet`). Zero import de `streamlit`. Migração pra Next.js/FastAPI reutiliza intacto.

## 4. Arquitetura geral

### Módulos novos (3)

**`src/session_auth.py`** — orquestração OAuth pra contexto web (Streamlit + futuro Next.js).

Camada fina em cima do `auth.py` existente. API pública:

- `build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str` — monta a URL de consentimento do ML.
- `exchange_code_for_tokens(client_id: str, client_secret: str, code: str, redirect_uri: str) -> TokenSet` — troca `code` por tokens. Reutiliza internamente `OAuthClient.exchange_code`, mas trabalha com um `InMemoryTokenStore` (não toca disco).
- `sanitize_oauth_error(msg: str) -> str` — remove qualquer substring que pareça `APP_USR-...` antes de logar.

Zero import de `streamlit`. Puro Python testável.

**`src/session_store.py`** — armazenamento em memória por sessão.

- `InMemoryTokenStore` — mesma interface do `TokenStore` (métodos `save(tokens)`, `load() -> TokenSet`), mas backing store é `dict` interno. Substituível diretamente no `OAuthClient` (que já é agnóstico ao tipo de store).
- `create_session_db() -> sqlite3.Connection` — cria conexão SQLite `:memory:` e roda `storage.init_schema(conn)` (função existente de `storage.py`). Retorna conn pronta pra receber ingestão.

Também zero import de `streamlit`. Testável.

**`src/ingest.py`** — orquestração do backfill dos 6 meses.

```python
def ingest_last_6_months(
    client: MLClient,
    seller_id: int,
    conn: sqlite3.Connection,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> IngestResult:
    ...
```

Chama os endpoints do ML em ordem (users/me → orders → items → categories → claims), grava via funções de `storage.py`, dispara `on_progress(fase, atual, total)` a cada tick pra UI mostrar progresso.

Retorna `IngestResult(total_orders: int, distinct_items: int, distinct_buyers: int, warnings: list[str])`.

Testável sem Streamlit — testes usam MLClient mockado via `responses` e uma conn `:memory:` de verdade.

### Módulos alterados (2)

**`src/dashboard.py`** — sidebar ganha a lógica real do toggle Demo/Real, mais tratamento do callback OAuth.

Ordem de execução no topo do arquivo (crítica — Streamlit re-executa esse arquivo a cada interação):

1. Verifica se `st.query_params` tem `code` + `state` → é callback OAuth, chama handler
2. Renderiza sidebar (que decide se mostra "Conectar" ou "Desconectar" baseado em `session_state`)
3. Se sidebar decidiu iniciar auth ou iniciar ingestão, dispara respectivamente

Estados possíveis do sidebar (5 — detalhados na Seção 7):
- Modo Demo (default)
- Modo Real + nenhuma conta conectada
- Modal de consentimento aberto (pré-redirect)
- Ingestão em andamento (após callback)
- Modo Real + conta conectada

**`src/pages/1_executive.py`, `2_products.py`, `3_customers.py`** — cada uma troca a linha que abre `data/demo.db` diretamente por uma chamada a um helper:

```python
from src.dashboard_helpers import get_active_conn

conn = get_active_conn()  # devolve demo.db conn OU session_conn baseado em session_state
```

Muda 1 linha por página. Nenhuma outra modificação.

### Módulo helper novo (menor)

**`src/dashboard_helpers.py`** — funções auxiliares consumidas pelas páginas.

- `get_active_conn() -> sqlite3.Connection` — inspeciona `st.session_state["sidebar_modo"]` e `st.session_state.get("session_conn")` pra decidir qual conn devolver.
- `get_active_ml_client() -> MLClient | None` — devolve `MLClient` com token renovado se necessário, ou `None` se não conectado. Consumido por qualquer código que precise chamar ML API durante a sessão (ex: botão "Recarregar dados").

### Módulos não modificados (importante)

- `src/auth.py` — sem mudanças. `OAuthClient` e `TokenSet` já são reutilizáveis.
- `src/ml_client.py` — sem mudanças. Já tem retry, paginação, tratamento de 429.
- `src/storage.py` — sem mudanças no schema. `init_schema(conn)` já funciona com conn `:memory:`.
- `src/metrics.py`, `src/segmentation.py` — **zero mudanças**. A camada analítica pura sobrevive intacta.
- `src/setup_auth.py` — sem mudanças. Continua funcionando pra dev local que quiser popular `data/historico.db` via CLI.
- `src/main.py` — sem mudanças. Comando `abrir-dashboard` continua funcionando (agora com a feature nova ativada).

### Fluxo de dados

```
┌───────────────────────────────────────────────────────────────────┐
│  Streamlit Cloud (1 worker, N sessões concorrentes)               │
│                                                                    │
│  Sessão A (browser 1)         Sessão B (browser 2)                │
│  ┌───────────────────┐        ┌───────────────────┐               │
│  │ st.session_state: │        │ st.session_state: │               │
│  │  ml_tokens_A      │        │  ml_tokens_B      │               │
│  │  ml_seller_id_A   │        │  ml_seller_id_B   │               │
│  │  session_conn_A   │        │  session_conn_B   │               │
│  │  (SQLite :memory:)│        │  (SQLite :memory:)│               │
│  └────────┬──────────┘        └────────┬──────────┘               │
│           │                            │                          │
└───────────┼────────────────────────────┼──────────────────────────┘
            │                            │
            ▼                            ▼
    ┌──────────────────────────────────────────┐
    │  API Mercado Livre (OAuth + /orders/...) │
    └──────────────────────────────────────────┘

Modo Demo (default): sessão lê data/demo.db (compartilhado, read-only)
```

## 5. Fluxo OAuth in-Streamlit

### Passo a passo

```
Usuário abre app         Streamlit Cloud                    ML OAuth
     │                        │                                │
     │─── GET / ─────────────>│                                │
     │<── dashboard demo ─────│                                │
     │                        │                                │
     │─── clica "Conectar" ──>│                                │
     │                        │ 1. gera state = secrets.       │
     │                        │    token_urlsafe(32)           │
     │                        │ 2. salva em session_state      │
     │                        │ 3. monta authorize_url         │
     │<── redirect (via ──────│                                │
     │    st.markdown com     │                                │
     │    JS window.location) │                                │
     │                        │                                │
     │─── GET /authorization ─┼───────────────────────────────>│
     │                        │                                │
     │<── consentimento ML ───┼────────────────────────────────│
     │                        │                                │
     │─── "Autorizar" ────────┼───────────────────────────────>│
     │                        │                                │
     │<── 302 redirect ──────────────────────────────────────  │
     │    to app URL/?code=X&state=Y                           │
     │                        │                                │
     │─── GET /?code=X&state=Y>                                │
     │                        │ 4. lê st.query_params          │
     │                        │ 5. valida state == session's   │
     │                        │ 6. POST /oauth/token           │───>│
     │                        │<── {access, refresh, exp} ─────────│
     │                        │ 7. salva em session_state      │
     │                        │ 8. st.query_params.clear()     │
     │                        │ 9. GET /users/me → seller_id   │───>│
     │                        │ 10. dispara ingest_last_6_months
     │<── dashboard com ──────│                                │
     │    dados reais         │                                │
```

### Estrutura do `st.session_state` por sessão

```python
{
    # Fase de conexão (transient)
    "oauth_state": "a3f7...",           # CSRF token; setado antes do redirect
    "oauth_status": "pending" | "connected" | "error",
    "oauth_error_message": str | None,  # mensagem sanitizada pra mostrar ao usuário

    # Após exchange (só existe se connected)
    "ml_tokens": TokenSet(...),          # dataclass de auth.py
    "ml_seller_id": 123456789,
    "ml_nickname": "VENDEDOR_XYZ",

    # Dados ingeridos (só existe se ingestão concluída)
    "session_conn": sqlite3.Connection,  # :memory:, populada por ingest.py
    "ingest_done_at": "2026-08-19T14:32:00Z",
    "ingest_result": IngestResult(...),  # pra mostrar contagens no sidebar

    # Estado de UI (já existe hoje)
    "sidebar_modo": "Demo" | "Real",
    "date_from": "...", "date_to": "...",
}
```

### Proteção CSRF via `state`

1. Antes do redirect: `state = secrets.token_urlsafe(32)` → salva em `session_state["oauth_state"]`.
2. Vai anexado na `authorize_url` como `&state=...`.
3. Quando volta o callback: comparamos `st.query_params["state"] == session_state["oauth_state"]`. Se não bater → erro, aborta troca do code, seta `session_state["oauth_error_message"] = "Falha de segurança na autenticação, tente novamente."`.
4. Sucesso → apaga `oauth_state` do session_state (single-use).

### Renovação de token durante a sessão

Tokens ML expiram em 6h. Fluxo de renovação transparente:

- Função `get_active_ml_client()` em `dashboard_helpers.py` é chamada por qualquer código que precisa bater na API.
- Ela lê `session_state["ml_tokens"]`, verifica `tokens.is_expired()` (método já existe em `auth.py:26`).
- Se expirado, instancia `OAuthClient` com `InMemoryTokenStore` que aponta pro `session_state`, chama `refresh()`. O refresh atualiza `session_state["ml_tokens"]` diretamente.
- Se o refresh falhar (refresh_token revogado ou expirado), limpa tokens do session_state, seta `session_state["sidebar_modo"] = "Demo"`, e mostra toast "Sua sessão expirou. Reconecte pra ver dados reais."

### Redirect da UI pro ML

Streamlit não tem redirect nativo (não é framework HTTP tradicional). Solução: injetar um `<meta http-equiv="refresh">` ou executar `window.location.href = ...` via `st.markdown(..., unsafe_allow_html=True)`. O padrão consolidado é:

```python
st.markdown(
    f'<meta http-equiv="refresh" content="0; url={authorize_url}">',
    unsafe_allow_html=True,
)
st.stop()
```

Isso força o browser a navegar imediatamente pro ML sem esperar nova interação.

### Tratamento de erros no fluxo

| Situação | Comportamento |
|---|---|
| Usuário cancela consentimento no ML | Callback vem com `?error=access_denied` (sem `code`). Handler detecta, seta `session_state["oauth_error_message"] = "Autorização cancelada. Você pode tentar de novo quando quiser."` |
| `state` do callback não bate | Descarta o code, seta erro genérico "Falha de segurança na autenticação, tente novamente." Loga o incidente com `code` truncado. |
| POST `/oauth/token` retorna 4xx | Captura a mensagem do ML via `sanitize_oauth_error(resp.text)`, mostra tratada. Sugere reconectar. |
| Rate limit (429) durante ingestão | `MLClient` já tem retry com `Retry-After`. UI mostra "Aguardando ML liberar próxima requisição..." e continua. |
| Ingestão falha no meio | Mantém o que já foi ingerido no `session_conn`, mostra dados parciais com banner "Ingestão interrompida — [Tentar novamente]". |
| Refresh token inválido durante sessão | Limpa tokens, volta pra Demo, toast "Sessão expirou, reconecte." |

## 6. Isolamento entre sessões — garantias

- **Streamlit garante `session_state` por browser session** — cada aba/navegador tem um cookie único que amarra ao próprio dict de session_state, isolado pelo runtime. Não há API pra código da sessão A ler session_state da B.
- **Objetos em memória (`sqlite3.Connection` in-memory) ficam presos ao dict `session_state`** — quando dict morre, conn vai pro GC do Python e o SQLite in-memory desaparece com ele.
- **Sem arquivos em disco** — nenhum `/tmp/session_X.db`, nenhum cache local. Zero risco de vazamento por leitura cruzada de arquivo.
- **Worker restart** — se o Streamlit Cloud reinicia o worker (deploy, sleep por inatividade), TODAS as sessões morrem simultaneamente e todos os visitantes precisam reconectar. Comportamento aceitável e comunicado no modal de consentimento ("seus dados ficam apenas nesta sessão").

## 7. UX do toggle Demo/Real + ingestão

### Estados visuais da sidebar (5)

**Estado 1: Demo (default, chegada)**
```
┌─────────────────────────────┐
│  SellerPulse                │
│  ─────────────────          │
│  Período: [Início] [Fim]    │
│  ─────────────────          │
│  Fonte de dados:            │
│    ⦿ Demo                   │
│    ○ Minha conta ML         │
│  ─────────────────          │
│  SellerPulse v0.4.0         │
└─────────────────────────────┘
```

**Estado 2: Radio em "Minha conta ML", ainda não conectado**
```
│  Fonte de dados:            │
│    ○ Demo                   │
│    ⦿ Minha conta ML         │
│                             │
│  ⚠ Nenhuma conta conectada. │
│  Ainda vendo dados demo.    │
│                             │
│  [🔌 Conectar minha conta]  │
```

**Estado 3: Modal antes do redirect** (após clicar "Conectar" — usa `st.dialog`)
```
┌────────────────────────────────────────┐
│  Conectar sua conta Mercado Livre      │
│                                        │
│  Vamos te redirecionar pro Mercado     │
│  Livre pra você autorizar o acesso.    │
│                                        │
│  O SellerPulse vai poder:              │
│   ✓ Ler seus pedidos dos últimos 6    │
│     meses                              │
│   ✓ Ler dados de produtos vendidos    │
│   ✓ Ler reclamações da conta          │
│                                        │
│  Não podemos alterar preços, criar    │
│  anúncios ou responder mensagens.      │
│                                        │
│  Seus dados ficam apenas nesta         │
│  sessão do navegador. Quando fechar    │
│  a aba, tudo é apagado.                │
│                                        │
│    [Cancelar]  [Continuar no ML →]    │
└────────────────────────────────────────┘
```

**Estado 4: Ingestão em andamento** (após callback bem-sucedido — usa `st.status`)
```
│  🟢 Conectado: VENDEDOR_XYZ        │
│                                     │
│  ⟳ Baixando seus dados...          │
│    ▶ Verificando conta       ✓     │
│    ▶ Baixando pedidos    (47%)     │
│      1.247 de ~2.640                │
│    ▶ Detalhes de produtos          │
│    ▶ Reclamações                   │
│    ▶ Calculando métricas           │
│                                     │
│  Tempo estimado: ~30s               │
```

Dashboard fica visível durante isso, mas com banner no topo: "Carregando seus dados reais... o dashboard ainda mostra Demo. Recarrega automaticamente quando pronto."

**Estado 5: Conectado, ingestão concluída**
```
│  Fonte de dados:            │
│    ○ Demo                   │
│    ⦿ Minha conta ML  🟢     │
│                             │
│  Conectado: VENDEDOR_XYZ    │
│  2.341 pedidos · 6 meses    │
│  Atualizado: 14:32          │
│                             │
│  [🔄 Recarregar dados]      │
│  [⛔ Desconectar]           │
```

### Fases da ingestão

| Fase | Endpoint ML | Tempo estimado (vendedor médio) |
|---|---|---|
| 1. Identificar seller | `GET /users/me` | ~1s |
| 2. Baixar pedidos | `GET /orders/search` (paginado) | ~15-25s |
| 3. Enriquecer itens | `GET /items/{id}` (batch por SKU único) | ~8-12s |
| 4. Baixar categorias novas | `GET /categories/{id}` (só as não cacheadas) | ~2-3s |
| 5. Baixar claims | `GET /post-purchase/v1/claims/search` | ~3-5s |
| 6. Persistir + init métricas base | Local (in-memory SQLite) | ~1-2s |

**Total esperado: ~30-50s**. Streamlit Cloud não tem timeout hard de request pra WebSocket, então a ingestão bloqueia a sessão do usuário mas não crasha.

Fases são **sequenciais** — paralelizar aqui só complica sem ganho relevante (a maior parte é I/O da API do ML que já tem retry).

### Callback de progresso

`ingest_last_6_months` recebe `on_progress: Callable[[str, int, int], None]`. Dashboard passa uma callback que atualiza `st.status` em tempo real:

```python
with st.status("Baixando seus dados...", expanded=True) as status:
    def update(fase: str, atual: int, total: int):
        status.update(label=f"⟳ {fase}...")
        if fase == "Baixando pedidos":
            st.write(f"  {atual} de ~{total}")

    result = ingest_last_6_months(client, seller_id, conn, on_progress=update)
    status.update(label="✓ Dados carregados!", state="complete")
```

### Comportamento pós-ingestão

- Toast: `"✓ Dados carregados! 2.341 pedidos processados."`
- Radio "Fonte de dados" já está em "Minha conta ML" (foi o que triggou o fluxo). As 3 páginas do dashboard, na próxima renderização, chamam `get_active_conn()` e recebem o `session_conn` — automaticamente veem dados reais.
- `date_from`/`date_to` selecionado é preservado (não zera).
- Se usuário voltar pra "Demo", `get_active_conn()` devolve a conn do `demo.db`. Dados reais continuam em `session_state["session_conn"]`, sem re-baixar quando voltar pra "Minha conta ML".

### Estados de exceção

| Situação | Comportamento |
|---|---|
| Conta sem pedidos em 6 meses | Ingestão termina rápido, dashboard mostra "Sua conta não tem pedidos no período. Os gráficos ficam vazios. [Voltar pro Demo]" |
| Rate limit prolongado (>60s aguardando) | Ingestão pausada com toast "ML está limitando requisições, aguardando 60s..." Não crasha, retoma automaticamente |
| Ingestão parcial (crashou depois de baixar pedidos mas antes de itens) | Dashboard funciona com o que tem, banner amarelo: "Ingestão incompleta — enriquecimento de produtos falhou. [Tentar novamente]" |
| Usuário fecha a aba durante ingestão | Sessão morre, dados perdidos. No próximo acesso é como se nunca tivesse conectado. Sem estado zumbi. |

### Botão "Recarregar dados"

Limpa `session_state["session_conn"]`, cria conn nova via `create_session_db()`, chama `get_active_ml_client()` (renova token se necessário), roda `ingest_last_6_months` de novo. Útil se o vendedor fez venda nos últimos minutos.

### Botão "Desconectar"

- `session_state.pop("ml_tokens", None)`, `session_state.pop("ml_seller_id", None)`, etc.
- Fecha e descarta `session_state["session_conn"]`.
- `session_state["sidebar_modo"] = "Demo"`.
- Toast: `"Desconectado. Seus dados foram removidos da sessão."`
- (Fora do MVP): revogação ativa do token via ML `/oauth/revoke`. Backlog documentado em não-goals.

## 8. Segurança

### Secrets management

- `CLIENT_ID` e `CLIENT_SECRET` (do app SellerPulse único, registrado uma vez) vão em `st.secrets` (Streamlit Cloud tem UI de secrets criptografados). Nunca commitados, nunca em env vars do repo.
- `.env.example` local ganha `ML_REDIRECT_URI` como campo documentado (dev local usa `http://localhost:8501/`, prod usa `https://sellerpulse.streamlit.app/`).
- Configuração é lida via helper `get_config()` que tenta `st.secrets` primeiro, cai pra `os.environ` (`.env`) se rodando local.

### Scopes solicitados

- Solicitamos `offline_access read` (não `write`). Documentado em README e no modal de consentimento (Estado 3 da sidebar).
- Nenhum endpoint de mutação (`POST`/`PUT`/`DELETE` em `/items`, `/orders`, `/messages`, etc) é chamado pelo código. Auditável por grep.

### HTTPS obrigatório

- Streamlit Cloud sempre serve HTTPS. `redirect_uri` registrado no ML: `https://sellerpulse.streamlit.app/`.
- Config do ML rejeita callbacks HTTP em produção. Erros de HTTPS misconfig aparecem no fluxo de consentimento (não silenciosos).

### Tokens em memória apenas

- No modo hospedado, nenhum token toca disco. `InMemoryTokenStore` mantém tudo em `st.session_state`.
- Quando sessão morre (aba fecha ou worker reinicia), tokens vão pro GC do Python.
- Zero cache local, zero cookies com tokens, zero localStorage.

### Logs — sanitização

- `sanitize_oauth_error` em `session_auth.py` troca qualquer substring que match `APP_USR-[\w\-]+` (padrão dos tokens ML) por `[REDACTED]` antes de logar.
- Aplicado em todo `OAuthError` levantado e em qualquer `st.error` que mostre mensagem do backend ML.
- `MLClient` já usa `response.text[:200]` em erros — trunca payloads antes de logar. Sanitizer adicional garante que mesmo os 200 chars não vazem token.

### CSRF via `state`

- 32 bytes de entropia via `secrets.token_urlsafe(32)`.
- Validado no callback com comparação `secrets.compare_digest(...)` (constant-time, evita timing attacks).
- Single-use: após validação bem-sucedida, `oauth_state` é removido de `session_state`.

### Não-riscos documentados

- **Token expirar 6h sem uso**: aceitável — ML expira tokens em ~6h por design; sessão típica de demo <30min.
- **Múltiplas sessões da mesma conta ML**: se o mesmo vendedor abrir 2 abas e conectar em ambas, cada uma tem tokens próprios. ML permite. Não há race condition.
- **Streamlit worker leaking objects entre requests**: `session_state` é isolado por design; testado pela própria equipe do Streamlit.

## 9. Testes

### Unit — `tests/test_session_auth.py` (~6 testes)

- `test_build_authorize_url_includes_state_and_redirect`
- `test_build_authorize_url_uses_configured_client_id`
- `test_exchange_code_returns_tokenset` — via `responses` mock em `https://api.mercadolibre.com/oauth/token`
- `test_exchange_code_raises_on_ml_error` — mock devolve 400, verifica que levanta `OAuthError`
- `test_sanitize_error_message_redacts_ml_tokens` — feed com string contendo `APP_USR-abc123def456...` → verifica que sai `[REDACTED]`
- `test_sanitize_error_message_preserves_other_content` — só troca tokens, resto passa

### Unit — `tests/test_session_store.py` (~4 testes)

- `test_inmemory_token_store_save_load_roundtrip` — save → load devolve o mesmo TokenSet
- `test_inmemory_token_store_load_raises_when_empty` — load sem save prévio → `FileNotFoundError` (mesmo contrato do `TokenStore` de disco)
- `test_session_db_creates_schema_on_first_use` — `create_session_db()` devolve conn com tabela `orders` criada
- `test_session_db_multiple_calls_return_fresh_conns` — chamadas sucessivas devolvem conns isoladas (dados de uma não vazam pra outra)

### Integration — `tests/test_ingest.py` (~5 testes, MLClient mockado via `responses`)

- `test_ingest_calls_all_phases_in_order` — verifica sequência de chamadas HTTP (users/me → orders → items → categories → claims)
- `test_ingest_progress_callback_fired_per_phase` — callback recebe cada nome de fase
- `test_ingest_persists_orders_to_conn` — após rodar, `SELECT COUNT(*) FROM orders` bate com o total mockado
- `test_ingest_handles_zero_orders_gracefully` — mock devolve 0 pedidos → não crasha, `IngestResult.total_orders == 0`
- `test_ingest_partial_failure_preserves_already_ingested` — mock falha na fase 3 (items) → pedidos da fase 2 continuam na conn, `IngestResult.warnings` documenta a falha

### Unit — `tests/test_dashboard_helpers.py` (~3 testes)

- `test_get_active_conn_returns_demo_when_modo_demo`
- `test_get_active_conn_returns_session_conn_when_modo_real_and_connected`
- `test_get_active_conn_returns_demo_when_modo_real_but_not_connected` — fallback seguro

### Manual — checklist pré-deploy

Documentado como seção final em `docs/specs/2026-08-19-oauth-in-dashboard-design.md` (este arquivo). Executado em staging (branch `feat/oauth-in-dashboard` deployado em subdomínio Streamlit Cloud separado):

1. Deploy staging bem-sucedido, URL público acessível
2. Fluxo completo com conta ML pessoal do Guilherme
3. Testar cancelamento de consentimento no ML
4. Testar 2 abas em paralelo com contas diferentes (verificar isolamento visual)
5. Simular expiração de token (esperar 6h ou forçar via ferramenta de debug alterando `expires_at` no session_state)
6. Verificar que Demo mode continua funcionando após conectar + desconectar
7. Verificar comportamento em conta sem pedidos nos últimos 6 meses (usar conta test do ML)

### O que NÃO é testado automaticamente

- Redirect real do browser pro ML — depende de interação humana no consentimento do ML. Coberto apenas no manual.
- Isolamento cross-session real (browsers separados) — coberto no manual (testes de sessão do Streamlit são in-process e não simulam 2 browsers).

### Meta de coverage

Módulos novos: `session_auth.py` ≥ 90%, `session_store.py` ≥ 85%, `ingest.py` ≥ 80%, `dashboard_helpers.py` ≥ 85%.

Global mantém ≥ 80% (não regride).

## 10. Setup operacional

Checklist executado por Guilherme antes do go-live:

### 1. Criar/atualizar app no ML

- Portal: `developers.mercadolivre.com.br`
- Nome: `SellerPulse Analytics`
- Tipo: "Aplicação que consome API do ML"
- Redirect URI: `https://sellerpulse.streamlit.app/`
- Escopos: `offline_access read`
- Modo: **desenvolvedor** (não publicar plenamente ainda — publicação é backlog Fase 6)
- Test users: adicionar contas dos recrutadores que forem testar (ou orientar a usar conta test ML)

### 2. Deploy Streamlit Cloud

- Conectar repo `github.com/carrerigcg/sellerpulse` na conta Streamlit Cloud
- Branch: `main`
- Entry point: `src/dashboard.py`
- Python version: 3.11
- Secrets (via UI do Streamlit Cloud, criptografados):
  ```toml
  ML_CLIENT_ID = "..."
  ML_CLIENT_SECRET = "..."
  ML_REDIRECT_URI = "https://sellerpulse.streamlit.app/"
  ```

### 3. Rate limits a estar ciente

- App do ML tem cota por dia (varia por perfil, geralmente ~10k requests/dia pra devs).
- Um visitante consome ~50-200 requests na ingestão de 6 meses.
- Cabe folgadamente dezenas de demos/dia. Se for pra Fase 6, avaliar quota upgrade com ML.

### 4. Comunicação da URL

- Compartilhar `https://sellerpulse.streamlit.app/` no README do projeto (badge no topo)
- Compartilhar em portfólio (LinkedIn, currículo) como link direto pra demo interativa

## 11. Preparação pro Fase 6 (SaaS multi-tenant real)

### Já pronto pro B (decisões que carregamos hoje)

- ✅ Camada analítica pura (`metrics.py`, `segmentation.py`) recebe `conn` — indiferente à origem. Zero mudança quando migrar pra Postgres.
- ✅ `OAuthClient` já é agnóstico ao `TokenStore` (só depende da interface `save`/`load`). Trocar `InMemoryTokenStore` por `PostgresTokenStore` no B é 20 linhas.
- ✅ `MLClient` já é agnóstico a onde os tokens vieram. Reutilizado intacto.
- ✅ `session_auth.py` e `ingest.py` são módulos puros Python (zero import de streamlit). Reutilizáveis em Next.js/FastAPI backend.
- ✅ Tokens já indexados por `ml_seller_id`, sessões já isoladas.
- ✅ Coluna `seller_id` planejada em todas as tabelas ingeridas desde o dia 1.

### O que muda no Fase 6

- 🔄 Frontend: Streamlit → Next.js (App Router) + FastAPI backend. Camada analítica sobrevive; Streamlit é substituído.
- 🔄 `InMemoryTokenStore` → `PostgresTokenStore` (nova classe, mesma interface — tabela `oauth_tokens` com FK pra `users`).
- 🔄 SQLite in-memory por sessão → Postgres multi-tenant compartilhado com coluna `seller_id` em todas as queries.
- ➕ Camada de auth de usuário (avaliar Clerk, Supabase Auth, ou próprio via NextAuth).
- ➕ Worker background pra ingestão (Celery, Arq, ou Inngest). Dashboard não bloqueia.
- ➕ Cron pra re-ingestão periódica (diária/semanal) de cada seller conectado.
- ➕ Landing page comercial dedicada.
- ➕ Billing / planos (opcional dependendo de estratégia).

### Estimativa de esforço da migração (chute mid-level)

3-6 semanas full-time. Não é rewrite — é evolução isolada por camada. A camada analítica pura é o "ativo permanente"; o resto orbita ela.

## 12. Roadmap de implementação — 10 blocos

Cada bloco vira 1 commit (às vezes 2). Estimativa total ~5.5 dias úteis.

| # | Bloco | Estimativa | Commit representativo |
|---|---|---|---|
| 1 | Preparação: bump `0.4.0-dev` + skeleton de arquivos + doc do `ML_REDIRECT_URI` no `.env.example` | 0.5d | `chore: skeleton fase 3` |
| 2 | `session_auth.py` (TDD: build_authorize_url + exchange + sanitize) | 0.5d | `feat(session_auth): oauth helpers` |
| 3 | `session_store.py` (TDD: InMemoryTokenStore + create_session_db) | 0.5d | `feat(session_store): in-memory stores` |
| 4 | `ingest.py` (TDD: orquestração das 6 fases com progress callback) | 1.0d | `feat(ingest): 6-month backfill` |
| 5 | `dashboard_helpers.py` (TDD: get_active_conn + get_active_ml_client) | 0.5d | `feat(dashboard): helpers` |
| 6 | `dashboard.py` — sidebar states 1, 2, 5 (Demo default + Real sem conta + Real conectado sem callback) | 0.5d | `feat(dashboard): sidebar toggle` |
| 7 | `dashboard.py` — states 3, 4 (modal de consentimento + callback + ingestão com progress) | 1.0d | `feat(dashboard): oauth flow` |
| 8 | Adaptar `pages/1_executive.py`, `2_products.py`, `3_customers.py` pra usar `get_active_conn()` | 0.5d | `feat(pages): use active conn` |
| 9 | Deploy staging + execução do checklist manual + fixes | 0.5d | `fix(oauth): correções pós-staging` |
| 10 | README (badge, seção "Demo ao vivo") + ruff + bump `0.4.0` + tag + deploy prod | 0.5d | `chore(release): v0.4.0` |

**Estratégia de branch:** trabalhar em `feat/oauth-in-dashboard`, abrir PR ao final, fazer squash-merge no `main`, criar tag `v0.4.0`, deploy prod.

## 13. Arquivos criados/modificados

### Criar

- `src/session_auth.py`
- `src/session_store.py`
- `src/ingest.py`
- `src/dashboard_helpers.py`
- `tests/test_session_auth.py`
- `tests/test_session_store.py`
- `tests/test_ingest.py`
- `tests/test_dashboard_helpers.py`

### Modificar

- `src/dashboard.py` — habilitar toggle Real, adicionar handlers de callback OAuth e ingestão
- `src/pages/1_executive.py` — trocar leitura direta de `data/demo.db` por `get_active_conn()`
- `src/pages/2_products.py` — idem
- `src/pages/3_customers.py` — idem
- `.env.example` — adicionar linha `ML_REDIRECT_URI=http://localhost:8501/` (comentada dizendo que prod usa outra URL)
- `pyproject.toml` — bump versão para `0.4.0`
- `README.md` — adicionar badge "Demo ao vivo" com link Streamlit Cloud; seção nova "🔌 Conectar sua conta ML" explicando o fluxo; atualizar tabela de status

### NÃO modificar

- `src/auth.py`, `src/ml_client.py`, `src/storage.py`, `src/metrics.py`, `src/segmentation.py`, `src/setup_auth.py`, `src/main.py`, `src/demo_data.py`.

## 14. Critério de aceite (executável)

A fase considera-se completa quando **todos** os itens abaixo verificam:

1. `pytest tests/test_session_auth.py tests/test_session_store.py tests/test_ingest.py tests/test_dashboard_helpers.py -v` — todos verdes
2. `pytest --cov` — coverage global ≥ 80%; coverage dos novos módulos conforme metas da Seção 9
3. `ruff format --check` e `ruff check` — sem falhas
4. `python -m src.main abrir-dashboard` (local) — dashboard sobe, sidebar mostra toggle funcional, clicar "Conectar minha conta" abre modal (redirect local vai pra ML, callback bate em `localhost:8501`, ingestão roda)
5. Deploy `https://sellerpulse.streamlit.app/` acessível via HTTPS, sem exceptions no console
6. Fluxo completo em produção com 1 conta ML real: conectar → autorizar → callback → ingestão → dashboard com dados reais
7. Toggle Demo/Real funcional: alternar não perde dados de nenhum dos lados
8. Botão Desconectar limpa sessão e volta pra Demo
9. Sidebar mostra `Conectado: VENDEDOR_XYZ · N pedidos · 6 meses` após ingestão bem-sucedida
10. 2 browsers/abas separadas com contas ML diferentes: cada uma vê apenas seus próprios dados (checagem manual)
11. Cancelamento de consentimento no ML volta pro dashboard com mensagem clara
12. CI GitHub Actions verde após push
13. Tag `v0.4.0` criada e publicada
14. README atualizado com badge de demo e seção da nova feature

## 15. Fora de escopo (empurra para fase posterior)

| Item | Fase que absorve |
|---|---|
| Multi-tenant real (login de usuário + Postgres) | Fase 6 (SaaS Launch) |
| Migração frontend Streamlit → Next.js/FastAPI | Fase 6 |
| Persistência de dados entre sessões | Fase 6 |
| Landing page comercial dedicada | Fase 6 |
| Worker background pra ingestão | Fase 6 |
| Cron de re-ingestão | Fase 6 |
| Publicação plena do app ML no marketplace público | Fase 6 |
| Revogação ativa de token via `/oauth/revoke` | Backlog (post-Fase 6) |
| Suporte a múltiplas contas ML por sessão | Backlog |
| Ingestão progressiva (4sem rápido + 6m em background) | Backlog (otimização de UX) |
| Billing / planos pagos | Fase 6+ |

## 16. Próximo passo

1. **Aprovar este spec.** Se aprovado:
2. Invocar `superpowers:writing-plans` para gerar plano de implementação passo-a-passo — cada bloco da Seção 12 vira uma tarefa detalhada com arquivos exatos, funções exatas, testes exatos.
3. Executar o plano em branch `feat/oauth-in-dashboard`, seguindo TDD por bloco.
