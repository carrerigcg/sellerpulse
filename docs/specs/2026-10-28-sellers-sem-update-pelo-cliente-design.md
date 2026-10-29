# `sellers` sem escrita pelo navegador

Estado: `0015` aplicada em produção em 2026-10-28 (version 20261029013222) e
registrada no `APLICADAS.tsv`. Conferido depois: `sellers` só tem
`sellers_select_own`, RLS ligada, 2 sellers (1 demo, 1 conectado) intactos.
Falta CI verde e merge.

## Por quê

A `0002` criou `sellers_update_own` (`for update using (user_id = auth.uid())`),
sem `with check` e sem limite de coluna. A chave anon do Supabase vai no
frontend, e a API REST automática (PostgREST) aceita `PATCH /sellers` de
qualquer usuário logado. Em produção, o papel `authenticated` tem `UPDATE` na
tabela, então a RLS é a única barreira, e essa policy a abria.

Conferido em produção em 2026-10-28 (só leitura): `sellers` tinha
`sellers_select_own` e `sellers_update_own`, ambas para `public`, RLS ligada.

## O que um usuário logado conseguia mudar na PRÓPRIA linha

Provado em banco local com papel sem privilégio e `auth.uid()` simulado
(antes: `UPDATE 1` nas quatro; depois: `UPDATE 0`). A linha de outro usuário
já era inatingível, porque sem `with check` o `using` vale também para a linha
nova, e então `user_id` não sai de `auth.uid()`.

| coluna | quem lê | o que o estrago faz |
| --- | --- | --- |
| `last_synced_at` | `routers/ml.py` (`/sync` de login e o cron), `worker/runner.py` (`_delta`) | No futuro, `agora - ultimo` fica negativo, então o login e o cron respondem "recente" e **não enfileiram nada**; só o sync manual passa. O painel envelhece sem erro, e quando um delta enfim roda ele grava `now()` e deixa um buraco entre a última sincronização real e esse instante. Não se mediu o que `ingest_janela` faz com `date_from > date_to`. Em `NULL`, o próximo sync vira `backfill` de seis meses de chamadas ao ML; o backfill grava `now()`, então o custo se repete a cada vez que o `NULL` é regravado |
| `ml_seller_id` | worker, `routers/ml.py` (conexão e conflito), cron de sync | `NULL` desconecta a conta. Um número livre ocupa o id antes de outro vendedor conectar, e a conexão dele falha na constraint `uniq_ml_seller_id` |
| `is_demo` | `routers/demo.py`, `demo_refresh.py`, `mcp_server.py`, `corrige_taxas_do_raw_json.py` | É a trava da única porta pública e do refresh que apaga dados. Essas três só agem sobre o id em `DEMO_SELLER_ID`, então virar `true` na linha de um vendedor comum não ativa nada ali. Já o `corrige_taxas_do_raw_json.py` pula qualquer linha `is_demo`, então para ele a coluna não é inerte. No sentido inverso, o dono da conta da demo (`user_id` é `not null`) podia pôr `false` e derrubar a demo pública (503) |
| `ml_nickname` | tela de conexão | Cosmético, mas é texto livre vindo do navegador |

Não foi provado que um `ml_seller_id` de outra loja devolveria pedidos dela:
o token usado é o da própria linha, e o ML deve recusar. Não se testou contra o
ML, e não precisa: remover a policy fecha o caminho de qualquer jeito.

## Decisões travadas

1. **Remover `sellers_update_own`** (`drop policy if exists`), numa migration
   nova, `0015`. A `0002` não se edita (está registrada no `APLICADAS.tsv`).
2. **A policy de leitura fica.** Vendedor continua vendo a própria linha.
3. **Nada mais muda.** Não há caminho legítimo que dependa da policy: o backend
   entra pelo papel `postgres` (que não passa por RLS) e o frontend usa o
   Supabase só para `auth.*` (nenhum `.from()`, `.rpc()`, `.update()` no
   `frontend/`). É o mesmo remédio que a `0005` aplicou em `oauth_tokens`.
4. **Sem `revoke` de `UPDATE` do papel `authenticated`** nesta rodada. Seria
   uma segunda camada, mas o Supabase reconcede privilégios em tabela nova e a
   RLS sem policy já nega. Fica anotado abaixo.
5. **Teste:** `backend/tests/test_rls_sellers.py` aplica os arquivos de
   `backend/migrations/` em ordem e exige que nenhuma policy de escrita
   sobreviva em `sellers`. O banco de teste não aplica as migrations de RLS
   (falta `auth.uid()`), então o teste prova a **sequência dos arquivos**, não
   o comportamento no Postgres. O comportamento foi provado à parte, no banco
   local descartável, e depois em produção (ver abaixo).

## Fora desta spec

- As policies `for all` das tabelas de tenant (`orders`, `order_items`,
  `items_cache`, `categories_cache`, `claims`, `item_visits`, `product_costs`,
  `shipment_costs`) também são `for all` sem `with check`: o dono da linha
  consegue gravar nelas pela API REST. Não afeta outro tenant (o `using` impede
  trocar o `seller_id`), mas permite a um vendedor adulterar os próprios
  números, e o painel mostraria isso como dado do ML. Nenhuma tela escreve
  nelas pelo Supabase (o custo vai pelo backend). Merece sua própria migration
  e revisão, tabela a tabela.
- `revoke insert, update, delete, truncate` de `anon` e `authenticated` nas
  tabelas do `public`. Hoje elas têm esses privilégios e dependem só de RLS.
