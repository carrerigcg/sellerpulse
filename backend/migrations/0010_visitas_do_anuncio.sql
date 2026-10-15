-- backend/migrations/0010_visitas_do_anuncio.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- A spec reservava o numero 0009; ele foi usado pela RLS do custo de produto
-- em 2026-10-14. O conteudo e o mesmo.
--
-- VISITA E DADO PERECIVEL, e essa e a diferenca estrutural em relacao a tudo
-- que o sistema ingere hoje. Pedido o Mercado Livre guarda para sempre -- da
-- pra pedir seis meses de historico a qualquer momento, que e o que o
-- backfill faz. Visita nao: a janela consultavel e de 150 dias (confirmado na
-- documentacao em 2026-10-15; acima disso a API devolve erro) e o numero so
-- fica disponivel depois de ~48h.
--
-- Consequencia: se nao colher, perdeu. Quem conectar hoje e sincronizar
-- daqui a seis meses perdeu os primeiros quatro meses, e nenhuma chamada
-- futura traz de volta.
create table item_visits (
    seller_id  uuid not null references sellers(id) on delete cascade,
    item_id    text not null,
    dia        date not null,
    visitas    integer not null check (visitas >= 0),
    -- NAO e enfeite. Um dia colhido dentro da janela de 48h pode estar
    -- subcontado, e sem isto nao ha como distinguir "teve 3 visitas" de
    -- "colhi cedo demais". E o que permite recolher so o que vale recolher.
    colhido_em timestamptz not null default now(),
    -- Upsert por esta chave: recolher um dia SUBSTITUI. Visita e contagem
    -- fechada do dia, nao evento acumulavel -- somar duplicaria.
    primary key (seller_id, item_id, dia)
);

-- A tela consulta por (seller_id, janela de dias) e agrega por item. A PK
-- serve a busca por item; este indice serve a varredura por periodo.
create index idx_item_visits_dia on item_visits (seller_id, dia);

-- Dia sem linha significa ZERO visitas. Nao existe linha com visitas = 0 por
-- item por dia: seriam dezenas de milhares de linhas sem informacao nenhuma.
-- Quem consulta trata a ausencia como zero.

-- O job de visitas e proprio, nao uma fase do delta: visitas tem cadencia,
-- limite e modo de falha diferentes, e um 429 no endpoint de visitas nao pode
-- atrasar a ingestao de pedidos, que sustenta todas as telas.
--
-- O nome da constraint nao esta declarado em 0004 (o check e em linha), entao
-- quem nomeia e o Postgres. Conferido em 2026-10-15 nos DOIS bancos, teste e
-- producao: `sync_jobs_kind_check` nos dois, com a mesma definicao. Um
-- `drop constraint` com nome errado derrubaria a migration no deploy, nao no
-- teste.
alter table sync_jobs drop constraint sync_jobs_kind_check;
alter table sync_jobs add constraint sync_jobs_kind_check
    check (kind in ('backfill','delta','visitas'));
