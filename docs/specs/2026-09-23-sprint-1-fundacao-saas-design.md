# SellerPulse — Sprint 1: Fundação SaaS

**Sprint:** 1 de 4 da migração pra SaaS real (v0.4.0 → v1.0.0-saas)
**Data:** 2026-09-23
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

Até `v0.4.0` (Fase 3, tag `cc5a20b`), o SellerPulse é um app **Streamlit single-tenant por sessão de browser**: cada aba tem sua própria conexão SQLite `:memory:`, tokens ML vivem em `st.session_state`, e nada persiste entre sessões. É um "SaaS de mentira" deliberado — decisão travada no brainstorm da Fase 3 (ver `docs/specs/2026-08-19-oauth-in-dashboard-design.md`, decisão #1, opção C) — com arquitetura preparada pra evoluir pra multi-tenant real sem rewrite.

Esta sessão de brainstorm (2026-09-22/23) decidiu fazer essa evolução: o SellerPulse vira um **SaaS real e autônomo** — usuários se cadastram, conectam a própria conta do Mercado Livre, e seus dados persistem entre sessões. Isso é uma mudança de arquitetura completa demais pra um spec só, então foi quebrada em **4 sprints sequenciais + uma revisão global (\"Global Solution\") ao final**:

| Sprint | Escopo |
|---|---|
| **1 — Fundação** (este spec) | Schema Postgres multi-tenant, Supabase Auth, API FastAPI expondo a camada analítica pura, shell Next.js autenticado |
| 2 — Conexão ML + fila | OAuth do ML persistente, tokens criptografados no Postgres, ingestão assíncrona via fila/worker |
| 3 — Dashboard web | Migração das 3 páginas (Executive/Products/Customers) de Streamlit pra React |
| 4 — Relatório embutido | Aba "Gerar relatório" no site, expõe `pdf_renderer.py` via endpoint |
| Global Solution | Pente fino: segurança, LGPD, performance, testes, custo estimado hardcoded, checklist de deploy |

O dashboard Streamlit atual (`sellerpulse.streamlit.app`) **sai do ar no início desta sprint** — decisão explícita do Guilherme, ciente do vácuo de portfólio até o site novo estar navegável.

Design baseado em decisões tomadas em sessão de brainstorm 2026-09-22/23 (análise de código completa + 6 perguntas de clarificação resolvidas em sequência).

## 2. Goals & non-goals

### Goals

- Usuário consegue se cadastrar e logar no SaaS via Supabase Auth (email/senha **e** Google OAuth).
- Schema Postgres multi-tenant existe no Supabase, com Row-Level Security garantindo isolamento entre sellers.
- API FastAPI (hospedada no Render) expõe `metrics.py`/`segmentation.py` via REST, autenticada pelo JWT do Supabase, sempre filtrando pelo `seller_id` do usuário logado.
- `metrics.py`/`segmentation.py` portados pra rodar contra Postgres (troca de sintaxe SQLite → Postgres nas queries), mantendo a mesma assinatura pública (recebe `conn`, devolve `DataFrame`) e os testes existentes como base.
- Frontend Next.js (Vercel) com `/login`, `/signup`, `/dashboard` protegida, provando o fluxo ponta a ponta: login → chamada autenticada → dado renderizado.
- `demo_data.py` portado pra popular um seller de teste no Postgres (sem isso, a Sprint 1 termina com telas vazias e nada pra validar visualmente).
- Testes cobrindo os endpoints novos e a camada analítica portada.

### Non-goals (ficam pras próximas sprints)

- **OAuth do Mercado Livre / ingestão real** — Sprint 2. Nesta sprint, o único dado no Postgres é sintético (via `demo_data.py` portado).
- **Fila/worker assíncrono** — Sprint 2. Não há ingestão de verdade ainda pra enfileirar.
- **Páginas finais do dashboard (gráficos, KPIs, Pareto, RFM, cohort)** — Sprint 3. O `/dashboard` desta sprint é um shell mínimo provando autenticação + 1 chamada de API, não o produto final.
- **Relatório PDF embutido** — Sprint 4.
- **Billing / planos pagos** — backlog pós-Global Solution, não mencionado como prioridade.
- **Suporte a múltiplas contas ML por usuário** — schema assume 1 `user` : 1 `seller` por enquanto (mesma simplificação da Fase 3, agora persistida).
- **Revogação ativa de token, cron de re-sync** — sem tokens ainda nesta sprint; adiado pra quando existirem (Sprint 2+).

## 3. Decisões travadas no brainstorm

| # | Decisão | Escolha | Alternativas preteridas |
|---|---|---|---|
| 1 | Escopo do produto | **SaaS real autônomo** — usuários próprios, dados persistentes | Continuar single-tenant por sessão (modelo C da Fase 3) |
| 2 | Stack backend/frontend | **FastAPI + Next.js** | Full TypeScript (rewrite da camada pura); Python monolito server-rendered |
| 3 | Onde os dados ficam | **Postgres via Supabase** | Postgres self-hosted (Railway/Render); SQLite por tenant |
| 4 | Modelo de ingestão | **Fila assíncrona** (worker em background) | Síncrona com progresso (como hoje); híbrido |
| 5 | Onde o PDF aparece | **Aba "Gerar relatório" dentro do site** (Sprint 4) | PDF como produto separado/anexo |
| 6 | Formato do plano de migração | **4 sprints de 3 checkpoints + Global Solution final** | Fases únicas sem checkpoints intermediários |
| 7 | Hosting do backend | **Render** (trocado de Railway durante o brainstorm) | Railway; Fly.io; Vercel Functions (inviável — serverless não roda WeasyPrint/GTK nem worker de longa duração) |
| 8 | Destino do Streamlit atual | **Sai do ar já**, no início da Sprint 1 | Manter no ar em paralelo até o site novo estar pronto; manter no ar com banner |
| 9 | Método de login do SaaS | **Email/senha + Google OAuth** (Supabase Auth) | Só email/senha; só Google; magic link |

### Ponto em aberto (não bloqueia esta sprint)

O plano da Fase 4 (PDF v2 — enriquecer o *conteúdo* do relatório com seções ABC/RFM/cohort, `docs/plans/2026-08-25-pdf-v2-guia-analytics.md`, worktree em `.worktrees/pdf-v2`) ainda não tem decisão sobre se entra junto da Sprint 4 ou fica pra depois. Decidir ao chegar na Sprint 4.

## 4. Arquitetura geral

```
┌─────────────────────┐         ┌──────────────────────────┐
│  Next.js (Vercel)   │  HTTPS  │  FastAPI (Render)         │
│  /login /signup     │────────▶│  valida JWT Supabase      │
│  /dashboard (shell) │◀────────│  resolve seller_id        │
└──────────┬───────────┘         │  chama metrics/segmentation│
           │                     └──────────┬────────────────┘
           │ Supabase Auth (SSR)             │
           ▼                                 ▼
┌─────────────────────────────────────────────────────────┐
│  Postgres (Supabase) — RLS por seller_id                 │
│  auth.users (gerenciado) │ sellers │ orders │ order_items │
│  items_cache │ categories_cache │ claims │ oauth_tokens*  │
└─────────────────────────────────────────────────────────┘
```
`*oauth_tokens` — schema criado nesta sprint, populado só na Sprint 2.

**Dois OAuths distintos, não confundir:**
- **Supabase Auth** — login do usuário *no SellerPulse*. Objeto desta sprint.
- **OAuth do Mercado Livre** (`session_auth.py`) — conectar a *conta de vendedor*. Objeto da Sprint 2. `session_auth.py` já é puro Python sem import de Streamlit (decisão future-proof da Fase 3) — será reaproveitado praticamente intacto.

### Módulos novos

**Backend (`backend/` — novo diretório na raiz, paralelo a `src/`)**

- `backend/main.py` — app FastAPI, monta os routers.
- `backend/deps.py` — dependency que valida o JWT do Supabase (via chave pública do projeto), extrai `user_id`, resolve `seller_id` consultando a tabela `sellers`. Levanta 401 se token inválido/ausente, 404 se usuário sem seller associado ainda.
- `backend/routers/metrics.py`, `backend/routers/segmentation.py` — endpoints REST finos, um por função pública de `src/metrics.py`/`src/segmentation.py`.
- `backend/db.py` — pool de conexão Postgres via `asyncpg` (idiomático com os endpoints assíncronos do FastAPI), substitui o `sqlite3.Connection` que essas funções recebiam antes.

**Camada analítica portada**

`src/metrics.py` e `src/segmentation.py` precisam de uma segunda variante (ou parametrização) das queries pra rodar em Postgres — os pontos identificados na análise inicial:

- `substr(date_closed, 1, 10)` (SQLite, `metrics.fluxo_financeiro`) → `date_closed::date` ou `to_char(date_closed, 'YYYY-MM-DD')` no Postgres.
- `strftime('%Y-%m', ...)` (SQLite, `segmentation.cohort_produto`) → `to_char(date_closed, 'YYYY-MM')`.
- `ON CONFLICT ... DO UPDATE` — sintaxe compatível entre os dois, sem mudança.

Abordagem: manter a assinatura pública idêntica (`fn(conn, date_from, date_to, ...) -> DataFrame`) e trocar apenas as strings SQL internas condicionadas ao dialeto, OU duplicar as duas queries lado a lado com um dialect flag. Detalhar isso no plano de implementação — decisão de "como" fica pro `writing-plans`, não pro spec.

**Seed de dados**

`src/demo_data.py` (puro Python, gera pedidos sintéticos) ganha uma função `seed_postgres(conn, seller_id)` que grava no schema novo — reaproveita a lógica de geração, troca só o destino da escrita.

**Frontend (`frontend/` — novo diretório na raiz)**

- Next.js App Router. `/login`, `/signup` usando Supabase Auth UI ou client customizado.
- `/dashboard` — rota protegida (middleware verifica sessão Supabase), faz 1 chamada autenticada pra API (ex: `GET /metrics/fluxo-financeiro`) e renderiza o resultado cru — prova de conceito, não produto final.
- Paleta navy/gold de `src/theme.py` (`COLORS`, `CHART_SEQUENCE`) vira tokens Tailwind/CSS — reaproveita a identidade visual da Fase 2.5 sem reaproveitar o código Streamlit em si.

### Schema Postgres (Supabase)

```sql
-- gerenciado pelo Supabase: auth.users

create table sellers (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references auth.users(id) unique,
    ml_seller_id  bigint,              -- null até conectar (Sprint 2)
    ml_nickname   text,
    created_at    timestamptz not null default now()
);

create table orders (
    order_id         bigint not null,
    seller_id        uuid not null references sellers(id),
    date_closed       timestamptz not null,
    status            text not null,
    total_amount      numeric not null,
    marketplace_fee   numeric not null,
    shipping_cost     numeric not null,
    buyer_id          bigint,
    raw_json          jsonb not null,
    fetched_at        timestamptz not null,
    primary key (seller_id, order_id)
);
create index idx_orders_date on orders(seller_id, date_closed);

create table order_items (
    seller_id   uuid not null,
    order_id    bigint not null,
    item_id     text not null,
    quantity    integer not null,
    unit_price  numeric not null,
    primary key (seller_id, order_id, item_id),
    foreign key (seller_id, order_id) references orders(seller_id, order_id)
);

create table items_cache (
    seller_id     uuid not null references sellers(id),
    item_id       text not null,
    title         text not null,
    category_id   text not null,
    fetched_at    timestamptz not null,
    primary key (seller_id, item_id)
);

create table categories_cache (
    seller_id     uuid not null references sellers(id),
    category_id   text not null,
    name          text not null,
    fetched_at    timestamptz not null,
    primary key (seller_id, category_id)
);

create table claims (
    seller_id    uuid not null references sellers(id),
    claim_id     bigint not null,
    order_id     bigint,
    status       text not null,
    date_created timestamptz not null,
    raw_json     jsonb not null,
    fetched_at   timestamptz not null,
    primary key (seller_id, claim_id)
);
create index idx_claims_date on claims(seller_id, date_created);

-- schema criado agora, populado na Sprint 2
create table oauth_tokens (
    seller_id      uuid primary key references sellers(id),
    access_token   text not null,   -- criptografado at rest (pgsodium ou app-level)
    refresh_token  text not null,   -- criptografado at rest
    expires_at     timestamptz not null,
    updated_at     timestamptz not null default now()
);

-- RLS: todas as tabelas acima ativam row level security,
-- policy padrão = seller.user_id = auth.uid() (via join com sellers)
```

Diferença chave vs. o SQLite atual: `order_id`/`claim_id` deixam de ser `PRIMARY KEY` sozinhos e passam a ser `(seller_id, order_id)` — no SQLite single-tenant um `order_id` do ML era globalmente único (1 tenant só); em multi-tenant, dois sellers diferentes nunca colidem por definição, mas a chave composta é a forma correta de modelar isso e deixa RLS mais simples de raciocinar.

## 5. Fluxo de autenticação (checkpoint 1)

1. Usuário acessa `/signup`, cria conta via Supabase Auth (email/senha ou Google).
2. Supabase Auth dispara trigger (`on auth.users insert`) que cria a row correspondente em `sellers` (via Postgres function/trigger, não no app) — garante que todo `auth.users` sempre tem exatamente 1 `sellers` row.
3. Login subsequente: Next.js guarda sessão via cookie SSR do Supabase.
4. Toda chamada à API FastAPI carrega o JWT no header `Authorization: Bearer`; `backend/deps.py` valida contra a chave pública do projeto Supabase e resolve `seller_id`.

## 6. Testes

- **Camada analítica portada:** reaproveita os 14 testes de `test_metrics.py` + 22 de `test_segmentation.py` como base — adapta a fixture de conexão pra Postgres de teste (Supabase local via CLI, ou container `postgres:16` no CI). Mesmos casos, novo backend.
- **API:** `TestClient` do FastAPI + JWT mockado (usuário de teste fixo) + Postgres de teste seedado via `seed_postgres`.
- **Frontend:** fora de escopo de teste automatizado nesta sprint (é um shell de prova de conceito); validação manual do fluxo login → dashboard.
- **CI:** GitHub Actions ganha um segundo workflow (ou job) que sobe Postgres de serviço e roda os testes do `backend/`; o workflow atual (`tests.yml`) continua cobrindo `src/`/`tests/` como está.

## 7. Erros e casos de borda

- Token Supabase expirado/inválido → API responde 401; frontend redireciona pra `/login`.
- Usuário autenticado mas sem `sellers` row (não deveria acontecer dado o trigger, mas defensivo) → 404 com mensagem clara.
- Seller sem dados ainda (não rodou seed) → endpoints devolvem listas/DataFrames vazios, não erro — mesmo contrato de hoje quando `fluxo_financeiro` não tem pedidos no período.

## 8. Fora de escopo desta sprint (reafirmando)

Ingestão ML real, fila assíncrona, UI final do dashboard, PDF, billing, revogação de token, multi-conta por usuário. Cada um tem sprint ou backlog próprio conforme tabela da Seção 1.
