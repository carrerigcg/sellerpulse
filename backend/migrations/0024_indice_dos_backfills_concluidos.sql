-- backend/migrations/0024_indice_dos_backfills_concluidos.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- `dias_ja_buscados` (backend/jobs/queue.py) roda em toda carga do painel,
-- uma vez por conta, e procura os backfills concluidos do vendedor. Os dois
-- indices da fila so cobrem jobs ativos, entao a consulta lia a tabela
-- inteira, que cresce com cada job concluido de cada vendedor: 26 ms com 300
-- vendedores e um ano de fila, contra 0,18 ms com este indice (auditoria de
-- escala, 2026-11-06). As contas extras do Premium fazem a fila crescer mais
-- rapido.
--
-- Parcial: backfill concluido e raro (um por conta, mais um por troca para o
-- Premium), entao o indice fica minusculo.
--
-- Sem CONCURRENTLY: o runner de migrations roda dentro de transacao, e a fila
-- tem poucas dezenas de linhas, entao o lock e instantaneo.

create index idx_sync_jobs_backfills_concluidos on sync_jobs (seller_id)
    where kind = 'backfill' and status = 'done';
