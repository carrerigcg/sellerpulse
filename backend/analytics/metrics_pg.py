"""Porte de `src/metrics.py` pra Postgres/asyncpg (multi-tenant).

Por que este módulo existe separado de `src/metrics.py`: aquele módulo usa
`pd.read_sql_query`, que exige uma conexão DBAPI2 síncrona (SQLite via
`sqlite3`). `asyncpg` é assíncrono e não implementa essa interface — não dá
pra compartilhar a mesma função com um parâmetro de dialeto, porque o
padrão de chamada (sync vs. await) já é incompatível na raiz. Por isso as
funções aqui são reescritas com `pool.fetch(...)` + montagem manual do
DataFrame, mantendo as mesmas colunas, ordem e arredondamento do original.

Duas armadilhas de tradução de dialeto que este módulo trata explicitamente:

1. Schema multi-tenant: as tabelas usam chave composta (seller_id, ...).
   Todo JOIN casa também por `seller_id`, e toda query filtra
   `seller_id = $1` — senão dados de vendedores diferentes se misturam.
2. `numeric` do Postgres volta como `decimal.Decimal` via asyncpg. Colunas
   numéricas são convertidas pra `float` explicitamente ao montar o
   DataFrame, senão o dtype vira `object` e quebra downstream (gráficos,
   serialização).
3. Fuso do agrupamento diário: aqui o dia é contado em `FUSO_DO_VENDEDOR`
   (America/Sao_Paulo), não em UTC. Divergência INTENCIONAL de
   `src/metrics.py`, na mesma linha do desempate de `ORDER BY` explicado
   abaixo: lá `date_closed` é string ISO no SQLite e a query usa
   `substr(date_closed, 1, 10)`, sem conversão de fuso nenhuma — não existe
   UTC pra trocar. Aquela camada está congelada: ela lê um banco SQLite
   local e hoje serve só de referência de paridade para esta — mexer nela é
   uma mudança diferente, sem usuário real do outro lado.
"""

from __future__ import annotations

import uuid

import pandas as pd

from backend.analytics._common import FUSO_DO_VENDEDOR, _parse_boundary

# `SEM_CATEGORIA` e reexportado daqui: `src/metrics.py` passou a precisar do
# mesmo rotulo quando levou a mesma correcao de LEFT JOIN, e duas copias da
# string em duas camadas e exatamente como as camadas divergem. O import
# re-liga o nome neste namespace, entao quem ja importava
# `backend.analytics.metrics_pg.SEM_CATEGORIA` continua funcionando.
from src.metrics import SEM_CATEGORIA

# Nao existe custo estimado aqui, e nao deve voltar a existir: esta camada
# espelha `src/metrics.py`, onde o comentario do topo explica por que o
# percentual de COGS de 55% foi removido em vez de renomeado. A conta e
# margem de contribuicao = receita_bruta - taxas_ml - frete - custo_produtos.
# O frete vem de `shipment_costs`, por envio -- `orders.shipping_cost` nao e
# mais lido (docs/specs/2026-10-27-frete-real-design.md).
_FLUXO_COLUMNS = [
    "date",
    "receita_bruta",
    "taxas_ml",
    "frete",
    "receita_sem_frete",
    "custo_produtos",
    "receita_sem_custo",
    "margem_contribuicao",
]
_PRODUTOS_COLUMNS = ["item_id", "title", "category_name", "unidades", "receita"]
_CATEGORIAS_COLUMNS = ["category_id", "category_name", "unidades", "receita"]

# O fuso entra por f-string (nao por parametro $n) porque e constante do
# proprio codigo, nao entrada de usuario: nao ha superficie de injecao, e a
# query continua legivel pra quem for ler o SQL.
_FLUXO_QUERY = f"""
    -- Duas CTEs e nao um JOIN direto: a receita mora em `orders` (uma linha
    -- por pedido) e o custo mora em `order_items` (uma linha por item). Juntar
    -- as duas antes de agregar multiplicaria `total_amount` pelo numero de
    -- itens do pedido -- um pedido com 3 itens triplicaria a receita do dia.
    -- Cada lado agrega no seu grao e so entao os dois se encontram por dia.
    WITH por_dia AS (
        SELECT
            -- to_char sobre timestamptz converte pro fuso da SESSAO. O pool ja
            -- fixa server_settings={{"timezone": "UTC"}}, mas o AT TIME ZONE
            -- explicito torna essa query correta por si so, independente de
            -- config externa -- e, agora, o fuso declarado aqui e o do VENDEDOR
            -- (America/Sao_Paulo): o dia do grafico tem que ser o dia em que ele
            -- conta a venda, nao o dia UTC. Ver FUSO_DO_VENDEDOR em _common.py.
            to_char(o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}', 'YYYY-MM-DD') AS date,
            SUM(o.total_amount)                AS receita_bruta,
            SUM(o.marketplace_fee)             AS taxas_ml,
            -- Receita de pedido cujo envio ainda nao tem frete colhido. E o
            -- `receita_sem_custo` do frete: sem ela, um frete parcial pareceria
            -- completo. Pedido SEM envio nao entra -- sem envio nao ha frete a
            -- pagar, e isso e um fato, nao uma ausencia.
            COALESCE(SUM(o.total_amount) FILTER (
                WHERE o.shipment_id IS NOT NULL AND sc.shipment_id IS NULL
            ), 0)                              AS receita_sem_frete
        FROM orders o
        LEFT JOIN shipment_costs sc
          ON sc.seller_id = o.seller_id AND sc.shipment_id = o.shipment_id
        WHERE o.seller_id = $1
          AND o.status = 'paid'
          AND o.date_closed >= $2::timestamptz
          AND o.date_closed <  $3::timestamptz
        GROUP BY 1
    ),
    -- O frete e do ENVIO, e carrinho e um envio para varios pedidos: somado
    -- por pedido, o carrinho de 7 pedidos da loja real pagaria 7 fretes. Cada
    -- envio entra uma vez, no dia do seu primeiro pedido pago. Esse dia e
    -- calculado sobre a historia inteira, e nao so sobre a janela: senao um
    -- carrinho que atravessa a borda contaria nas duas janelas.
    envios AS (
        SELECT o.shipment_id, MIN(o.date_closed) AS primeiro_pedido
          FROM orders o
         WHERE o.seller_id = $1
           AND o.status = 'paid'
           AND o.shipment_id IS NOT NULL
         GROUP BY o.shipment_id
    ),
    frete_por_dia AS (
        SELECT
            to_char(e.primeiro_pedido AT TIME ZONE '{FUSO_DO_VENDEDOR}', 'YYYY-MM-DD') AS date,
            SUM(sc.custo_vendedor) AS frete
          FROM envios e
          JOIN shipment_costs sc
            ON sc.seller_id = $1 AND sc.shipment_id = e.shipment_id
         WHERE e.primeiro_pedido >= $2::timestamptz
           AND e.primeiro_pedido <  $3::timestamptz
         GROUP BY 1
    ),
    custo_por_dia AS (
        SELECT
            to_char(o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}', 'YYYY-MM-DD') AS date,
            -- SUM ignora NULL: item sem custo vigente simplesmente nao entra na
            -- soma, em vez de virar zero. A diferenca importa -- zero seria a
            -- afirmacao "nao custa nada", e a ausencia nao afirma nada.
            COALESCE(SUM(oi.quantity * pc.custo_unitario), 0)  AS custo_produtos,
            -- O que torna a coluna de cima honesta: quanto da receita do dia
            -- veio de item SEM custo informado. Sem isto, um vendedor com 3 de
            -- 47 produtos preenchidos veria a margem quase intacta e concluiria
            -- que lucra muito.
            COALESCE(
                SUM(oi.quantity * oi.unit_price) FILTER (WHERE pc.custo_unitario IS NULL),
                0
            )                                                  AS receita_sem_custo
        FROM order_items oi
        JOIN orders o
          ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
        -- O custo que vale e o da ULTIMA vigencia anterior ou igual a data do
        -- pedido. LEFT JOIN LATERAL porque o item pode nao ter custo nenhum, e
        -- pedido anterior a primeira vigencia fica SEM custo de proposito: o
        -- vendedor informou o custo de hoje, nao afirmou nada sobre antes.
        --
        -- A data do pedido entra aqui no fuso do VENDEDOR, nao em UTC. Tem que
        -- ser o mesmo dia que bucketiza a linha la em cima, senao um pedido das
        -- 22h de Brasilia compararia contra o dia seguinte.
        LEFT JOIN LATERAL (
            SELECT c.custo_unitario
              FROM product_costs c
             WHERE c.seller_id = oi.seller_id
               AND c.item_id   = oi.item_id
               AND c.vigente_desde <= (o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
             ORDER BY c.vigente_desde DESC
             LIMIT 1
        ) pc ON TRUE
        WHERE oi.seller_id = $1
          AND o.status = 'paid'
          AND o.date_closed >= $2::timestamptz
          AND o.date_closed <  $3::timestamptz
        GROUP BY 1
    )
    SELECT
        d.date,
        d.receita_bruta,
        d.taxas_ml,
        COALESCE(f.frete, 0)             AS frete,
        d.receita_sem_frete,
        -- LEFT JOIN + COALESCE: dia com pedido mas sem nenhuma linha em
        -- order_items (possivel em dado antigo) ainda aparece, com custo zero.
        COALESCE(c.custo_produtos, 0)    AS custo_produtos,
        COALESCE(c.receita_sem_custo, 0) AS receita_sem_custo
    FROM por_dia d
    LEFT JOIN custo_por_dia c ON c.date = d.date
    LEFT JOIN frete_por_dia f ON f.date = d.date
    ORDER BY d.date
"""

_TOP_PRODUTOS_QUERY = """
    SELECT
        oi.item_id                                 AS item_id,
        -- LEFT JOIN nos dois caches: item sem linha em items_cache e anuncio
        -- apagado (a ingestao leva 404 e nunca cacheia). Foi vendido e a
        -- receita e real, entao ele fica no ranking: o SKU e o titulo de
        -- fallback. Com INNER JOIN ele sumia junto com o dinheiro (11,2% numa
        -- loja real) e esta tela divergia da Executive.
        COALESCE(ic.title, oi.item_id)              AS title,
        -- Categoria desconhecida e DESCONHECIDA: rotulo explicito ($5), nunca
        -- uma categoria real emprestada. Ver _TOP_CATEGORIAS_QUERY.
        COALESCE(cc.name, $5)                       AS category_name,
        SUM(oi.quantity)                            AS unidades,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)  AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    LEFT JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    LEFT JOIN categories_cache cc
      ON cc.seller_id = oi.seller_id AND cc.category_id = ic.category_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY oi.item_id, ic.title, cc.name
    -- Desempate por item_id: divergencia INTENCIONAL de src/metrics.py (que
    -- tem o mesmo defeito de ORDER BY sem desempate, mas esta congelado).
    -- Sem isso, empates de receita tem ordem nao-deterministica no Postgres
    -- e o "top produto" alterna entre recarregamentos com LIMIT.
    ORDER BY receita DESC, oi.item_id
    LIMIT $4
"""

# Segunda query separada — não dá pra reaproveitar o LIMIT do ranking de
# produtos aqui: filtrar por top-N produtos distorceria os totais por
# categoria (excluiria receita de produtos fora do top-N).
#
# Item sem categoria conhecida (anuncio apagado, ou categoria que nao entrou
# em categories_cache) NAO some e NAO e jogado numa categoria real: os dois
# erros corrompem o breakdown (o primeiro faz a soma das categorias nao bater
# com a receita total; o segundo atribui venda a quem nao vendeu). Ele forma
# um balde proprio, com category_id NULL (nenhum id real do ML colide) e o
# rotulo SEM_CATEGORIA ($5). Agrupar so por cc.* junta todos os desconhecidos
# num balde unico.
_TOP_CATEGORIAS_QUERY = """
    SELECT
        cc.category_id                              AS category_id,
        COALESCE(cc.name, $5)                        AS category_name,
        SUM(oi.quantity)                             AS unidades,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)   AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    LEFT JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    LEFT JOIN categories_cache cc
      ON cc.seller_id = oi.seller_id AND cc.category_id = ic.category_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY cc.category_id, cc.name
    -- Desempate por category_id: mesma divergencia INTENCIONAL de
    -- src/metrics.py explicada acima em _TOP_PRODUTOS_QUERY.
    ORDER BY receita DESC, cc.category_id
    LIMIT $4
"""


async def fluxo_financeiro(
    pool, seller_id: uuid.UUID, date_from: str, date_to: str
) -> pd.DataFrame:
    """DataFrame por dia com receita, custos do ML, custo de produto e margem.

    Margem de contribuição = receita_bruta - taxas_ml - frete - custo_produtos.

    O custo de produto só entra quando o vendedor o informou para aquele item,
    numa vigência anterior ou igual à data do pedido (ver `product_costs`,
    migration 0008). Nunca é estimado: item sem custo informado não desconta
    nada e aparece em `receita_sem_custo`, que é o que impede a margem de
    parecer completa quando não é.

    Com zero custos cadastrados a função devolve exatamente os números de
    antes da feature — `custo_produtos` zera e a margem não muda. É o que
    `test_fluxo_paridade_com_a_versao_sqlite` continua provando.

    Ainda espelha `src/metrics.py.fluxo_financeiro` nas colunas que as duas
    camadas calculam. `custo_produtos` e `receita_sem_custo` existem só aqui:
    o SQLite legado não tem `product_costs`, e não vai ter.

    `receita_sem_custo` é medida na base de ITENS (quantity * unit_price),
    enquanto `receita_bruta` vem de `orders.total_amount`. As duas coincidem
    quando o total do pedido é a soma dos seus itens — medido nos 344 pedidos
    pagos de `data/demo.db`, divergência máxima de 9e-13. Quem for exibir
    cobertura como porcentagem deve mesmo assim limitar a 100%: a igualdade é
    uma propriedade do dado, não uma garantia do schema.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601, ex: "2026-07-25").
        date_to: fim exclusivo (ISO 8601).

    O frete segue a mesma regra do custo: so entra o que foi colhido, por
    envio (`shipment_costs`), e a receita dos pedidos cujo envio ainda nao tem
    frete aparece em `receita_sem_frete`.

    Returns:
        DataFrame com colunas: date, receita_bruta, taxas_ml, frete,
        receita_sem_frete, custo_produtos, receita_sem_custo,
        margem_contribuicao. Uma linha por dia com pedidos pagos. Vazio se
        nenhum pedido no range.
    """
    rows = await pool.fetch(
        _FLUXO_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )

    if not rows:
        return pd.DataFrame(columns=_FLUXO_COLUMNS)

    df = pd.DataFrame([dict(r) for r in rows])
    numericas = (
        "receita_bruta",
        "taxas_ml",
        "frete",
        "receita_sem_frete",
        "custo_produtos",
        "receita_sem_custo",
    )
    for col in numericas:
        df[col] = df[col].astype(float)

    # Arredondados aqui, e nao no SQL: o custo vem de `quantity * numeric` e a
    # soma de varios itens acumula casas que ninguem pediu.
    for col in ("frete", "receita_sem_frete", "custo_produtos", "receita_sem_custo"):
        df[col] = df[col].round(2)

    df["margem_contribuicao"] = (
        df["receita_bruta"] - df["taxas_ml"] - df["frete"] - df["custo_produtos"]
    ).round(2)

    return df[_FLUXO_COLUMNS]


_CANCELAMENTOS_QUERY = """
    SELECT count(*)::int                         AS pedidos,
           COALESCE(SUM(total_amount), 0)        AS valor
      FROM orders
     WHERE seller_id = $1
       AND status = 'cancelled'
       AND date_closed >= $2::timestamptz
       AND date_closed <  $3::timestamptz
"""


async def cancelamentos(pool, seller_id: uuid.UUID, date_from: str, date_to: str) -> dict:
    """Quantos pedidos da janela foram cancelados ou devolvidos, e quanto somam.

    Existe para a tela fechar a conta contra o painel do Mercado Livre. O
    "vendas brutas" de lá soma o que voltou depois; a `receita_bruta` daqui só
    conta o que continua pago. Medido em 01/09 a 28/09 na conta real: R$ 22.919
    pagos, mais R$ 750 do dia 28 ("Até" exclusivo), mais R$ 5.004 cancelados e
    devolvidos, dão os R$ 28.673 do painel do ML até o centavo. Ver
    docs/specs/2026-10-28-receita-vs-vendas-brutas-design.md.

    Cancelada e devolvida chegam juntas: as duas são `cancelled` na nossa base.
    A janela é a mesma do fluxo (`_parse_boundary`, no fuso do vendedor, com o
    fim exclusivo); outra janela faria a conta não fechar.

    Returns:
        `{"pedidos": int, "valor": float}`. Zero quando não houve cancelamento:
        aqui zero é um fato medido, não ausência de dado.
    """
    linha = await pool.fetchrow(
        _CANCELAMENTOS_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )
    return {"pedidos": linha["pedidos"], "valor": round(float(linha["valor"]), 2)}


async def top_produtos(
    pool, seller_id: uuid.UUID, date_from: str, date_to: str, n: int = 10
) -> dict[str, pd.DataFrame]:
    """Top N produtos e top N categorias por receita.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo.
        n: número de linhas retornadas em cada ranking. Default 10.

    Returns:
        dict com chaves:
        - "produtos": DataFrame [item_id, title, category_name, unidades, receita]
        - "categorias": DataFrame [category_id, category_name, unidades, receita]
        Ambos ordenados por receita desc.

        Item vendido sem linha em `items_cache` (anúncio apagado no ML) entra
        normalmente: `title` cai pro próprio item_id e a categoria vira
        `SEM_CATEGORIA`. Em `categorias` ele forma um balde único com
        `category_id` None — assim a soma das categorias fecha com a receita
        total, sem atribuir venda a uma categoria real.
    """
    dt_from = _parse_boundary(date_from)
    dt_to = _parse_boundary(date_to)
    produtos_rows = await pool.fetch(
        _TOP_PRODUTOS_QUERY, seller_id, dt_from, dt_to, n, SEM_CATEGORIA
    )
    categorias_rows = await pool.fetch(
        _TOP_CATEGORIAS_QUERY, seller_id, dt_from, dt_to, n, SEM_CATEGORIA
    )

    if produtos_rows:
        produtos = pd.DataFrame([dict(r) for r in produtos_rows])
        produtos["receita"] = produtos["receita"].astype(float)
        produtos = produtos[_PRODUTOS_COLUMNS]
    else:
        produtos = pd.DataFrame(columns=_PRODUTOS_COLUMNS)

    if categorias_rows:
        categorias = pd.DataFrame([dict(r) for r in categorias_rows])
        categorias["receita"] = categorias["receita"].astype(float)
        categorias = categorias[_CATEGORIAS_COLUMNS]
    else:
        categorias = pd.DataFrame(columns=_CATEGORIAS_COLUMNS)

    return {"produtos": produtos, "categorias": categorias}
