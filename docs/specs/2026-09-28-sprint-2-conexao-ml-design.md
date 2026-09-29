# SellerPulse — Sprint 2: Conexão com o Mercado Livre + fila de ingestão

**Sprint:** 2 de 4 da migração pra SaaS real (v0.4.0 → v1.0.0-saas)
**Data:** 2026-09-28
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

A Sprint 1 entregou a fundação e está em produção: schema multi-tenant no Supabase, Supabase Auth com ES256, API FastAPI no Render, frontend Next.js na Vercel, e a camada analítica (`metrics.py`/`segmentation.py`) portada pra Postgres com paridade verificada contra a original em SQLite.

O que ela deliberadamente **não** entregou: qualquer dado real. O único seller populado é sintético, semeado por `backend/scripts/seed_seller.py`. A tabela `oauth_tokens` foi criada vazia, só pra existir. O usuário consegue se cadastrar, logar e ver um dashboard — mas não consegue conectar a própria loja.

Esta sprint fecha esse vão. Ao final dela, um vendedor real conecta a conta do Mercado Livre, os tokens ficam cifrados no Postgres, e os seis meses de histórico dele entram no banco por uma fila assíncrona.

Três peças da base atual são reaproveitadas quase intactas, resultado de decisões future-proof da Fase 3:

- `src/session_auth.py` — monta a URL de consentimento e troca o `code` por tokens. Python puro, zero import de Streamlit.
- `src/auth.py` — `TokenSet` (com `is_expired()` e margem de segurança) e `OAuthClient.refresh()`.
- `src/ml_client.py` — cliente da API do ML com retry e tratamento de rate limit, já testado.

A peça que **não** dá pra reaproveitar como está é `src/ingest.py`: ela recebe `sqlite3.Connection` e grava via `src/storage.py`. Precisa do mesmo tipo de port que `metrics_pg.py` recebeu na Sprint 1.

## 2. Goals & non-goals

### Goals

- Usuário logado conecta a conta do Mercado Livre por OAuth, e a conexão **persiste** entre sessões (diferente da Fase 3, onde o token morria com a aba do browser).
- `access_token` e `refresh_token` ficam **cifrados** no Postgres, com versionamento de chave pra rotação futura.
- Refresh de token é seguro sob concorrência: o ML rotaciona o `refresh_token` a cada uso, e dois refreshes paralelos desconectariam o usuário.
- Fila de sincronização em tabela Postgres, consumida por um worker assíncrono, com lease, retomada e limite de tentativas.
- Backfill de 6 meses enfileirado automaticamente ao conectar a conta.
- Sincronização incremental (delta) disparada no login quando o último sync passou de 6 horas, mais um botão de sincronização manual.
- `ingest.py` portado pra Postgres/asyncpg, multi-tenant, com paridade verificada contra a versão SQLite.
- Endpoints públicos de demonstração (`/api/demo/*`), read-only, servindo o seller sintético.
- Frontend mínimo: botão de conectar, retorno do callback, status da sincronização por polling, estado vazio, desconectar.

### Non-goals (ficam pras próximas sprints)

- **Dashboard real** (gráficos, KPIs, Pareto, RFM, cohort) — Sprint 3. Esta sprint não mexe na aparência do dashboard.
- **Tela da demonstração** ("Ver demonstração" na landing) — Sprint 3. Aqui só nascem os endpoints.
- **Relatório PDF embutido** — Sprint 4.
- **Billing / planos pagos** — backlog pós-Global Solution.
- **Múltiplas contas ML por usuário** — o schema segue 1 `user` : 1 `seller`.
- **Revogação do token no lado do ML** — desconectar apaga localmente; não chama endpoint de revogação do ML.
- **Worker em processo dedicado** — decisão 1 abaixo. O código já nasce pronto pra isso, mas a migração é de outra sprint.

## 3. Decisões travadas no brainstorm

| # | Decisão | Escolha | Alternativas preteridas |
|---|---|---|---|
| 1 | Onde o worker roda | **In-process no web service** (task asyncio no lifespan do FastAPI) + fila em Postgres com `FOR UPDATE SKIP LOCKED`. Custo R$ 0 | Background Worker do Render ($7/mês — não existe no plano grátis); GitHub Actions como worker (cron + `workflow_dispatch`) |
| 2 | Escopo da sincronização | **Backfill ao conectar + delta disparado no login** (se último sync > 6h) + botão manual | Só backfill manual; re-sync agendado por cron (o free tier hiberna, o agendamento não tem garantia) |
| 3 | Dado de demonstração | **Seller demo público read-only**, endpoints `/api/demo/*` sem auth, `seller_id` fixo no servidor | Nenhuma demo (estado vazio); semear dado sintético em cada conta nova com flag `is_demo` |
| 4 | Guarda dos tokens ML | **Cifra na aplicação com Fernet**, chave em env var, coluna `key_version` | Supabase Vault/pgsodium (amarra ao Supabase e o CI roda contra Postgres limpo); não cifrar e confiar na RLS |
| 5 | Onde o ML devolve o usuário | **Callback no backend (Render)**, identidade viajando num `state` assinado | Callback no frontend (Vercel), usando o cookie de sessão do Supabase |

### Justificativa da decisão 1 (a que mais molda o resto)

O Render não oferece Background Worker no plano grátis — o tipo de serviço começa no Starter pago. Rodar o loop dentro do web service é de graça, mas herda a hibernação: a instância dorme após ~15 min sem request, e um job em andamento morre com ela.

Isso é aceitável porque a fila em Postgres com `SKIP LOCKED` é idêntica nas três opções — o que muda é só **onde o loop gira**. O worker nasce como módulo isolado com entrypoint próprio (`python -m backend.worker`), então promovê-lo a processo dedicado depois é configuração de plataforma, não refactor. O preço da hibernação é pago com lease + retomada por cursor (seção 5).

### Justificativa da decisão 3

A demo não é andaime de portfólio, é superfície permanente do produto: serve tanto pra recrutador avaliar o trabalho sem criar conta quanto pra prospect ver o sistema funcionando antes de assinar. Duas consequências que isso impõe:

- O dado do seller demo é **determinístico** — semeado com seed fixa, não regenerado a cada deploy. Prospect que volta na semana seguinte vê os mesmos números, e print de tela não envelhece.
- É a única porta do sistema sem autenticação, então é read-only **por construção**: router só com GET e `seller_id` fixo em constante no servidor, nunca aceito por query param ou header.

A alternativa de semear dado sintético dentro de cada conta nova foi recusada por um motivo concreto: dado real e sintético coexistindo no mesmo tenant obriga *toda* query a respeitar o flag `is_demo`. É exatamente a classe de filtro transversal que o teste de mutação já pegou errado nesta base (o `seller_id` ausente no JOIN de `categories_cache`, na Sprint 1). Uma query esquecida e os números mentem sem avisar.

## 4. Achados de código que mudam o desenho

Três coisas descobertas ao ler a base durante o brainstorm. Todas produzem resultado errado em silêncio, que é o motivo de estarem no spec e não numa nota de implementação.

### 4.1 `get_orders` filtra por `date_created`, não por `date_last_updated`

`src/ml_client.py:85` monta `order.date_created.from/to`. Pra backfill histórico está correto. Pra delta, está errado: um pedido pago em julho que foi **cancelado ontem** tem `date_created` fora da janela do delta, então nunca é revisitado — e segue contando como receita para sempre.

O delta precisa filtrar por `order.date_last_updated`, que captura tanto pedido novo quanto pedido alterado. Isso pede um parâmetro novo em `get_orders` (qual campo de data usar), mantendo `date_created` como default pra não mudar o comportamento de quem já chama.

### 4.2 O `MLClient` é síncrono e o worker mora no mesmo processo da API

`src/ml_client.py` usa `requests`. Chamado direto de dentro do loop asyncio, ele bloqueia o event loop — e como o worker compartilha processo com o FastAPI (decisão 1), cada ingestão derrubaria a API inteira por minutos.

O port mantém o banco em asyncpg no loop e joga **só as chamadas HTTP** pra thread, via `asyncio.to_thread`. O `MLClient` fica intocado, e com ele os testes de retry/rate-limit que já existem. Portá-lo pra `httpx` async seria reescrever aquela lógica e invalidar aqueles testes sem ganho nenhum aqui.

### 4.3 A policy `oauth_tokens_own` expõe os tokens via PostgREST

`backend/migrations/0002_rls.sql` dá ao papel `authenticated` permissão de ler a própria linha de `oauth_tokens`. Com a tabela vazia era inofensivo. Com token real dentro, o browser do usuário passa a poder buscar aquela linha pela API REST automática do Supabase — dado que ele nunca precisa ter.

A `0004` remove a policy. RLS habilitada sem policy permissiva nega tudo, e o backend continua acessando pelo papel `postgres`, que não passa por RLS (arquitetura já documentada no cabeçalho da `0002`).

## 5. Arquitetura

### Módulos novos

| Módulo | Responsabilidade |
|---|---|
| `backend/ml/tokens.py` | Cifra/decifra Fernet; `PostgresTokenStore` carrega e salva `TokenSet` por `seller_id`, com `key_version` |
| `backend/ml/oauth.py` | Adapter sobre `src/session_auth.py`; emite e valida o `state` assinado; refresh apoiado no store |
| `backend/ml/ingest_pg.py` | Port de `src/ingest.py` pra asyncpg. Dois modos: `backfill` (180 dias por `date_created`) e `delta` (desde um instante, por `date_last_updated`) |
| `backend/jobs/queue.py` | `enqueue`, `claim_next` (`FOR UPDATE SKIP LOCKED`), `heartbeat`, `finish`, `fail` |
| `backend/worker/runner.py` | Loop asyncio. Sobe pelo `lifespan` do FastAPI e também roda como `python -m backend.worker` |
| `backend/routers/ml.py` | `POST /ml/connect/start`, `GET /ml/callback`, `DELETE /ml/connection`, `POST /ml/sync`, `GET /ml/sync/status` |
| `backend/routers/demo.py` | Endpoints públicos read-only do seller de demonstração |

O `src/` continua sendo só consumido — nenhuma dependência nova de `src/` para `backend/`, mantendo a direção que a Global Solution vai revisar.

### Fluxo de conexão

1. Frontend chama `POST /ml/connect/start` com o JWT do Supabase. O backend emite o `state` — JWT HS256 de 10 minutos, `sub` = `user_id` — e devolve a URL de consentimento. `client_id` e `client_secret` do ML nunca saem do servidor.
2. Browser vai ao ML, o usuário consente, o ML redireciona pra `GET /ml/callback?code=...&state=...`.
3. O backend valida assinatura e validade do `state`, resolve o `seller_id`, troca o `code` por tokens, chama `/users/me` pra gravar `ml_seller_id` e `ml_nickname`, cifra e persiste os tokens, **enfileira o job de backfill** e redireciona o browser pro frontend.
4. O worker — acordado, porque acabou de chegar um request — reclama o job e ingere, escrevendo progresso na própria linha do job.
5. Frontend acompanha por polling em `GET /ml/sync/status`.

O `state` assinado resolve CSRF e identidade na mesma peça. Sem ele, um link de callback forjado poderia plugar a conta ML de um atacante no dashboard da vítima.

### Onde exatamente o delta é disparado

"No login" é ambíguo o suficiente pra gerar duas implementações diferentes, então fica explícito: o frontend chama `POST /ml/sync` ao montar o dashboard, e **quem decide é o backend** — ele só enfileira se existir conexão ativa e `last_synced_at` for mais velho que 6 horas. Caso contrário responde que não havia o que fazer, sem criar job.

A regra mora no servidor de propósito. Se o frontend decidisse, a janela de 6 horas viraria algo que um cliente desatualizado (ou uma aba aberta desde ontem) pode ignorar, e o botão manual passaria a ser a única sincronização confiável.

### Refresh de token sob concorrência

O Mercado Livre **rotaciona o `refresh_token` a cada uso**: o refresh devolve um par novo e invalida o anterior. Dois pedidos de refresh em paralelo (por exemplo, uma requisição da API e o worker ao mesmo tempo) fariam um invalidar o outro, desconectando o usuário sem ele ter feito nada.

O refresh acontece dentro de uma transação com `SELECT ... FOR UPDATE` na linha de `oauth_tokens`. Quem chega segundo espera o lock, relê a linha e encontra o token já renovado — não queima o dele.

### Schema

```sql
-- backend/migrations/0004_ml_tokens_e_fila.sql

-- As colunas em texto puro nunca receberam dado real: trocar agora é barato.
alter table oauth_tokens
    drop column access_token,
    drop column refresh_token,
    add column access_token_enc  text not null,
    add column refresh_token_enc text not null,
    add column key_version smallint not null default 1;

-- Ver seção 4.3: o browser não precisa nem do ciphertext.
drop policy "oauth_tokens_own" on oauth_tokens;

alter table sellers add column last_synced_at timestamptz;

create table sync_jobs (
    id            bigserial primary key,
    seller_id     uuid not null references sellers(id) on delete cascade,
    kind          text not null check (kind in ('backfill','delta')),
    status        text not null default 'queued'
                  check (status in ('queued','running','done','failed')),
    attempts      integer not null default 0,
    fase          text,
    processados   integer not null default 0,
    total         integer not null default 0,
    cursor        jsonb,
    warnings      jsonb not null default '[]'::jsonb,
    erro          text,
    leased_until  timestamptz,
    created_at    timestamptz not null default now(),
    started_at    timestamptz,
    finished_at   timestamptz,
    -- O reaper busca lease vencido com `leased_until < now()`, e NULL < now()
    -- e unknown, nao true: uma linha 'running' sem lease nunca seria repescada,
    -- e uniq_sync_job_ativo a contaria como ativa — travando o seller pra sempre.
    constraint running_tem_lease check (status <> 'running' or leased_until is not null)
);

-- Um job ativo por seller. A garantia é do banco, não de um `if` no app:
-- impede o botão manual de empilhar backfills e o delta de duplicar job.
create unique index uniq_sync_job_ativo on sync_jobs(seller_id)
    where status in ('queued','running');

create index idx_sync_jobs_fila on sync_jobs(created_at)
    where status in ('queued','running');

alter table sync_jobs enable row level security;
create policy "sync_jobs_select_own" on sync_jobs for select using (
    seller_id in (select id from sellers where user_id = auth.uid())
);
```

Na implementação isso virou **dois arquivos**, não um: `0004_ml_tokens_e_fila.sql` com o DDL portátil (roda no Supabase e no banco de teste) e `0005_rls_sprint2.sql` com a RLS e a `drop policy`, que dependem de `auth.uid()` e por isso só rodam no Supabase — a mesma divisão que `setup_test_db.py` já aplica pra excluir a `0002` e a `0003`.

### Retomada e tolerância a falha

Aqui é onde a decisão 1 cobra o preço. A instância hiberna e pode matar um job no meio do caminho. Duas defesas:

- **Lease.** `claim_next` marca `leased_until = now() + 2 min` e o worker renova por heartbeat enquanto progride. Job cujo lease venceu volta a ser candidato — o worker seguinte o repesca.
- **Cursor.** O backfill processa **mês a mês**, gravando em `cursor` o último mês concluído. Se a instância cair no quarto mês, a repescagem continua do quarto em vez de recomeçar os seis. Sem isso, um seller com volume alto poderia nunca terminar o backfill num free tier.

Três tentativas e o job vira `failed`, com a mensagem em `erro` e visível no `GET /ml/sync/status`. Falha parcial de enriquecimento (um item ou categoria que não veio) segue o comportamento atual do `ingest.py`: acumula em `warnings` e não derruba o job.

## 6. Testes

Cada item abaixo é verificado por **mutação** — quebrar o código de propósito e confirmar que o teste falha — que é o padrão adotado nesta base depois de quatro pontos cegos encontrados assim na Sprint 1.

| Alvo | O que o teste tem que pegar |
|---|---|
| Fernet | Round-trip; ciphertext adulterado **levanta exceção** em vez de devolver lixo; `key_version` gravado |
| `state` assinado | Token expirado, assinatura inválida, e `sub` de outro usuário — o cenário do link forjado |
| Refresh concorrente | Duas corrotinas renovando juntas resultam em **uma** chamada HTTP ao ML, e ambas terminam com token válido |
| Fila | Dois workers competindo reclamam cada job uma única vez; lease vencido é repescado; índice parcial rejeita job ativo duplicado |
| `ingest_pg` | Paridade com os fixtures do ingest SQLite atual; e ingerir pro seller A nunca grava linha com `seller_id` do B |
| Delta | Pedido `paid` no backfill que volta `cancelled` no delta **muda de status** — o bug que o filtro por `date_created` esconderia (seção 4.1) |
| Cursor | Job interrompido no meio retoma do último mês gravado, sem reprocessar os anteriores nem pular nenhum |
| `/api/demo/*` | Responde sem autenticação; aceita só GET; `seller_id` passado por parâmetro é ignorado |
| Worker não bloqueia | Ingestão em andamento não impede a API de responder (seção 4.2) |

Os testes rodam no job `backend` do CI, contra o serviço Postgres do GitHub Actions, sem depender do Supabase.

## 7. Erros e casos de borda

- **Usuário nega consentimento no ML:** callback chega com `error=access_denied` e sem `code`. Redireciona pro frontend com mensagem, sem criar job.
- **`state` expirado** (usuário deixou a aba do ML aberta meia hora): mensagem pedindo pra tentar de novo, não erro genérico.
- **Conta ML já conectada em outro usuário do SellerPulse:** `ml_seller_id` não é único hoje. Detectar e recusar com mensagem clara, em vez de deixar dois tenants ingerindo a mesma loja.
- **Refresh falha com `invalid_grant`** (usuário revogou o acesso no ML): apaga os tokens, marca a conexão como caída e pede reconexão no frontend. Não insiste em retry.
- **Seller sem nenhum pedido nos 6 meses:** backfill termina com `done` e zero linhas. O dashboard cai no estado vazio, não em erro — e o `pd.to_numeric` corrigido em `4c6f49b` é justamente o que faz esse caminho não estourar.
- **Token do ML vazando em log:** `sanitize_oauth_error` (`src/session_auth.py:38`) já redige os patterns `APP_USR-` e `TG-`. Todo caminho de erro novo passa por ela.

## 8. Fora de escopo desta sprint (reafirmando)

Dashboard real e tela da demo (Sprint 3), PDF embutido (Sprint 4), billing, múltiplas contas ML por usuário, revogação do token no lado do ML, worker em processo dedicado.

## 9. Pré-requisitos manuais

O Mercado Livre exige `redirect_uri` em **HTTPS**, então `localhost` não serve pra testar o callback. A URL do backend no Render precisa ser cadastrada como redirect URI na aplicação do ML antes do checkpoint 1.

Variáveis de ambiente novas no Render (nenhuma vai pro frontend — nenhuma leva prefixo `NEXT_PUBLIC_`):

| Variável | Conteúdo |
|---|---|
| `ML_CLIENT_ID` | App ID da aplicação do Mercado Livre |
| `ML_CLIENT_SECRET` | Secret da aplicação do ML |
| `ML_REDIRECT_URI` | URL do callback no Render, idêntica à cadastrada no ML |
| `TOKEN_ENCRYPTION_KEY` | Chave Fernet (32 bytes base64url). Perder essa chave invalida todos os tokens guardados e força todo mundo a reconectar |
| `STATE_SECRET` | Segredo que assina o `state` do OAuth. Separado do anterior de propósito: propósitos distintos, chaves distintas |
| `FRONTEND_URL` | Pra onde o callback redireciona depois de conectar |
| `DEMO_SELLER_ID` | UUID do seller de demonstração servido por `/api/demo/*` |

**Dependências:** nada de novo pra instalar — `Fernet` vem de `cryptography`, que já chega como dependência transitiva de `pyjwt[crypto]`. Mas ela passa a ser **declarada explicitamente** no `backend/requirements.txt`: cifra de token é funcionalidade de segurança central, e depender de um extra de terceiro pra mantê-la presente é frágil. Junto entra `responses`, a biblioteca que a suíte legada já usa pra mockar a API do ML e que os testes desta sprint precisam.

## 10. Checkpoints

1. **Tokens cifrados + OAuth ponta a ponta.** Migration `0004`, `ml/tokens.py`, `ml/oauth.py`, `routers/ml.py` (start + callback + disconnect). Ao final: conectar uma conta real grava token cifrado e `ml_seller_id`.
2. **Fila + worker + backfill.** `jobs/queue.py`, `worker/runner.py`, `ml/ingest_pg.py` em modo backfill com cursor. Ao final: conectar dispara os 6 meses e o dado aparece no Postgres.
3. **Delta + demo + frontend + deploy.** Delta no login, botão manual, `routers/demo.py`, frontend mínimo, deploy no Render e na Vercel.
