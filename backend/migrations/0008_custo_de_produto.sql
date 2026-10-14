-- backend/migrations/0008_custo_de_produto.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Hoje a margem de contribuicao e `receita - comissao - frete`. Falta o maior
-- custo variavel de todos, o da mercadoria -- entao o numero nao e uma margem
-- parcial, e uma margem ERRADA PARA MAIS. Em outubro de 2026 foi removido um
-- COST_ESTIMATE_RATE de 55% que chutava esse custo, com a decisao de que custo
-- de produto so entra se o vendedor informar. Esta tabela e o mecanismo de
-- informar, que nunca tinha sido construido.
--
-- POR QUE `vigente_desde` NA CHAVE, e nao uma coluna em items_cache:
--
-- Sem data de vigencia, atualizar um custo REESCREVE O PASSADO. O fornecedor
-- sobe o preco em outubro, o vendedor corrige o cadastro, e a margem de
-- setembro muda junto -- um mes ja fechado vira outro numero. Para um produto
-- cujo argumento e "calculada, nao estimada", isso e mentir sobre o historico,
-- e no pior formato: silencioso e plausivel.
--
-- Com a data na chave, informar o custo de novo NO MESMO DIA substitui (upsert
-- na chave) e num dia diferente ACRESCENTA um periodo.
--
-- Uma coluna em items_cache nao serviria porque a chave daquela tabela e
-- (seller_id, item_id) -- uma linha por produto --, e uma linha nao guarda
-- linha do tempo. Nao e por risco de sobrescrita pela ingestao: o upsert de
-- `_garante_cache_de_item` nomeia as colunas que atualiza (title, category_id,
-- fetched_at), entao uma coluna de custo sobreviveria ao refresh. Sobreviveria,
-- e mesmo assim nao serve.
--
-- POR QUE `date` E NAO `timestamptz`: o custo e decisao comercial do dia, nao
-- evento com hora. E `date` evita a classe de bug de fuso que ja apareceu
-- neste projeto (ver FUSO_DO_VENDEDOR em backend/analytics/_common.py).
--
-- SEM INDICE EXTRA: a consulta do custo vigente filtra por
-- (seller_id, item_id) e pede o maior `vigente_desde` anterior a uma data. A
-- primary key ja e exatamente esse btree, na ordem certa.
create table product_costs (
    seller_id      uuid not null references sellers(id) on delete cascade,
    item_id        text not null,
    vigente_desde  date not null,
    -- `>= 0` e nao `> 0`: custo zero e uma afirmacao legitima ("este produto
    -- nao me custa nada") e precisa ser distinguivel de ausencia, que e a
    -- falta da linha. A tela nunca grava zero por campo vazio.
    custo_unitario numeric not null check (custo_unitario >= 0),
    criado_em      timestamptz not null default now(),
    primary key (seller_id, item_id, vigente_desde)
);
