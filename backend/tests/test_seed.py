# backend/tests/test_seed.py
from __future__ import annotations

from datetime import timedelta

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos
from backend.seed import seed_postgres
from src.demo_data import ANCHOR_DATE, DEFAULT_SEED, generate_catalog, generate_orders

# Parametros pequenos pra manter os testes rapidos (default e weeks_back=12,
# ~360 pedidos -- bom demais pro seed real, lento demais pro teste unitario).
_SMALL = {"n_categories": 5, "n_products": 10, "weeks_back": 2, "claim_rate": 0.04}

_TABELAS = ("categories_cache", "items_cache", "orders", "order_items", "claims")


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

    contagens_db = await _contagens(pg_pool, sid)
    assert contagens_db == {
        "categories_cache": resumo["categories"],
        "items_cache": resumo["items"],
        "orders": resumo["orders"],
        "order_items": resumo["order_items"],
        "claims": resumo["claims"],
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
