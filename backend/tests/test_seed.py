# backend/tests/test_seed.py
from __future__ import annotations

from datetime import date, timedelta

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos
from backend.seed import custo_de_demonstracao, seed_postgres, visitas_de_demonstracao
from src.demo_data import ANCHOR_DATE, DEFAULT_SEED, generate_catalog, generate_orders

# Parametros pequenos pra manter os testes rapidos (default e weeks_back=12,
# ~360 pedidos -- bom demais pro seed real, lento demais pro teste unitario).
_SMALL = {"n_categories": 5, "n_products": 10, "weeks_back": 2, "claim_rate": 0.04}

_TABELAS = (
    "categories_cache",
    "items_cache",
    "orders",
    "order_items",
    "claims",
    "product_costs",
    "item_visits",
)


def _janela(weeks_back: int) -> tuple[str, str]:
    """Janela [date_from, date_to) que cobre TODOS os pedidos gerados.

    generate_orders() distribui os pedidos nas `weeks_back` semanas
    anteriores a ANCHOR_DATE -- todas estritamente antes de ANCHOR_DATE.
    """
    date_from = (ANCHOR_DATE - timedelta(weeks=weeks_back)).date().isoformat()
    date_to = ANCHOR_DATE.date().isoformat()
    return date_from, date_to


async def _contagens(pg_pool, seller_id) -> dict[str, int]:
    async with pg_pool.acquire() as conn:
        return {
            tabela: await conn.fetchval(
                f"SELECT count(*) FROM {tabela} WHERE seller_id=$1", seller_id
            )
            for tabela in _TABELAS
        }


async def test_contagem_bate_com_o_gerador(pg_pool, test_seller):
    """As contagens inseridas tem que bater com o que generate_catalog/
    generate_orders produziriam com os mesmos parametros."""
    _, sid = test_seller
    resumo = await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, **_SMALL)

    catalog = generate_catalog(
        seed=DEFAULT_SEED, n_categories=_SMALL["n_categories"], n_products=_SMALL["n_products"]
    )
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=_SMALL["weeks_back"])

    # order_items esperado: dedupe por item_id dentro do mesmo pedido (a PK e
    # composta e rng.choices pode escolher o mesmo item_id duas vezes no
    # mesmo pedido) -- mesma logica que generate_demo_db aplica.
    n_order_items_esperado = sum(
        len({item["item_id"] for item in order["items"]}) for order in orders
    )

    assert resumo["categories"] == len(catalog["categories"]) == _SMALL["n_categories"]
    assert resumo["items"] == len(catalog["products"]) == _SMALL["n_products"]
    assert resumo["orders"] == len(orders)
    assert resumo["order_items"] == n_order_items_esperado
    assert resumo["claims"] >= 1

    # Custo de produto: um por item que `custo_de_demonstracao` nao deixa de
    # fora. A fatia sem custo e deliberada -- semear 100% faria o indicador de
    # cobertura nunca aparecer na demonstracao, escondendo a feature que ele e.
    custos_esperados = sum(
        1
        for prod in catalog["products"]
        if custo_de_demonstracao(prod["item_id"], prod["unit_price"]) is not None
    )
    assert resumo["product_costs"] == custos_esperados
    assert 0 < custos_esperados < len(catalog["products"]), (
        "nem tudo coberto, nem nada coberto: a demo precisa dos dois estados"
    )

    assert resumo["item_visits"] > 0

    contagens_db = await _contagens(pg_pool, sid)
    assert contagens_db == {
        "categories_cache": resumo["categories"],
        "items_cache": resumo["items"],
        "orders": resumo["orders"],
        "order_items": resumo["order_items"],
        "claims": resumo["claims"],
        "product_costs": resumo["product_costs"],
        "item_visits": resumo["item_visits"],
    }


async def test_idempotente(pg_pool, test_seller):
    """Rodar duas vezes nao duplica nenhuma tabela."""
    _, sid = test_seller
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, **_SMALL)
    contagens_apos_primeira = await _contagens(pg_pool, sid)

    segundo_resumo = await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, **_SMALL)
    contagens_apos_segunda = await _contagens(pg_pool, sid)

    assert segundo_resumo == {
        "categories": 0,
        "items": 0,
        "orders": 0,
        "order_items": 0,
        "claims": 0,
        # O custo de produto entra na idempotencia como o resto: o upsert bate
        # na chave (seller_id, item_id, vigente_desde) e a vigencia deriva do
        # pedido mais antigo, que e o mesmo nas duas chamadas.
        "product_costs": 0,
        # Idem visitas: a chave e (seller_id, item_id, dia) e os dias
        # derivam dos pedidos, que sao os mesmos nas duas chamadas.
        "item_visits": 0,
        # Idem frete: um envio por pedido, chave (seller_id, shipment_id).
        "shipment_costs": 0,
    }
    assert contagens_apos_segunda == contagens_apos_primeira
    assert all(n > 0 for n in contagens_apos_primeira.values())


async def test_isola_por_seller(pg_pool, test_seller, outro_seller):
    """Semear o seller A nao coloca nada no seller B."""
    _, sid_a = test_seller
    _, sid_b = outro_seller
    await seed_postgres(pg_pool, sid_a, seed=DEFAULT_SEED, **_SMALL)

    contagens_b = await _contagens(pg_pool, sid_b)
    assert contagens_b == {tabela: 0 for tabela in _TABELAS}


async def test_dados_semeados_alimentam_as_funcoes_analiticas(pg_pool, test_seller):
    """O proposito do seed: fluxo_financeiro e top_produtos tem que devolver
    linhas com receita > 0 sobre a janela semeada."""
    _, sid = test_seller
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, **_SMALL)
    date_from, date_to = _janela(_SMALL["weeks_back"])

    fluxo = await fluxo_financeiro(pg_pool, sid, date_from, date_to)
    assert not fluxo.empty
    assert (fluxo["receita_bruta"] > 0).all()

    top = await top_produtos(pg_pool, sid, date_from, date_to)
    assert not top["produtos"].empty
    assert (top["produtos"]["receita"] > 0).all()
    assert not top["categorias"].empty
    assert (top["categorias"]["receita"] > 0).all()


async def test_acentos_sobrevivem(pg_pool, test_seller):
    """Faker pt_BR gera titulos acentuados -- o banco (UTF8) tem que devolver
    exatamente o mesmo texto que o gerador produziu."""
    _, sid = test_seller
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, **_SMALL)

    catalog = generate_catalog(
        seed=DEFAULT_SEED, n_categories=_SMALL["n_categories"], n_products=_SMALL["n_products"]
    )
    produto = catalog["products"][0]
    assert any(ord(ch) > 127 for ch in produto["title"]), (
        "produto de teste sem acento -- ajuste o indice"
    )

    async with pg_pool.acquire() as conn:
        titulo_db = await conn.fetchval(
            "SELECT title FROM items_cache WHERE seller_id=$1 AND item_id=$2",
            sid,
            produto["item_id"],
        )
    assert titulo_db == produto["title"]


async def test_demo_deixa_produto_sem_visita_de_proposito():
    """O estado "—" precisa aparecer na vitrine.

    E metade do valor da feature: distingue "nao medimos" de "medimos e deu
    zero". Com todo produto coberto ele ficaria invisivel justamente onde
    alguem vai olhar.

    A asserção e sobre o catalogo REAL da demonstracao (50 produtos), nao
    sobre o reduzido que os outros testes usam: medido, o pequeno nao sorteia
    nenhum item pra fora, e um teste sobre ele daria falso verde.
    """
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=26)

    com_visita = {item for item, _, _ in visitas_de_demonstracao(orders, hoje=date.today())}
    vendidos = {i["item_id"] for o in orders if o["status"] == "paid" for i in o["items"]}

    assert com_visita, "sem visita nenhuma a coluna fica vazia e a feature parece quebrada"
    assert com_visita < vendidos, "todo produto coberto esconde o estado de ausencia"


async def test_demo_subconta_os_dois_ultimos_dias():
    """Os dias nao consolidados sao menores de proposito.

    Assim o aviso que a tela mostra corresponde a algo real na demonstracao,
    em vez de ser texto decorativo.
    """
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=26)
    ultimo = max(_dia_do_pedido(o) for o in orders if o["status"] == "paid")

    por_dia: dict[date, list[int]] = {}
    for _, dia, visitas in visitas_de_demonstracao(orders, hoje=ultimo):
        por_dia.setdefault(dia, []).append(visitas)

    def media(dia):
        valores = por_dia.get(dia, [])
        return sum(valores) / len(valores) if valores else 0.0

    recentes = [media(ultimo), media(ultimo - timedelta(days=1))]
    antigos = [media(ultimo - timedelta(days=n)) for n in range(5, 15)]
    antigos = [m for m in antigos if m > 0]

    assert antigos, "sem dias antigos pra comparar o teste nao mede nada"
    assert max(recentes) < sum(antigos) / len(antigos), (
        "os dois ultimos dias tem que sair subcontados, como o ML entrega"
    )


def _dia_do_pedido(pedido):
    from backend.analytics._common import _parse_boundary

    return _parse_boundary(pedido["date_closed"]).date()
