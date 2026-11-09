-- backend/migrations/0025_indice_da_fila_por_vendedor.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Tres consultas leem os jobs de um vendedor sem filtro de status ativo: o
-- ultimo job (`/ml/sync/status`, que o Conectar pede a cada 3 s enquanto um
-- job roda), as visitas colhidas ha pouco e o backfill que falhou ha pouco
-- (`backend/worker/runner.py`). Os indices da fila cobrem so jobs ativos e
-- backfills concluidos, entao elas liam a fila inteira, que cresce para
-- sempre: 60 ms com um ano de fila para 125 contas, contra 0,06 ms com este
-- indice (auditoria de escala, 2026-11-09, banco local).
--
-- `created_at` na chave serve o `ORDER BY created_at DESC LIMIT 1` do status.
--
-- Sem CONCURRENTLY: o runner de migrations roda dentro de transacao, e a fila
-- tem menos de cem linhas, entao o lock e instantaneo.

create index idx_sync_jobs_por_vendedor on sync_jobs (seller_id, created_at);
