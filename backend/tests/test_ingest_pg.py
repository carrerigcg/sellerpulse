"""Testes da ingestao em Postgres — port de src/ingest.py."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import pytest

from backend.ml.ingest_pg import extrai_taxa_e_frete, ingest_janela

JANELA = (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC))


def _pedido(
    order_id,
    *,
    item_id="MLB1",
    status="paid",
    total=100.0,
    buyer=555,
    sale_fee=6.0,
    quantity=2,
    shipping_cost=None,
):
    """Pedido no FORMATO REAL da API do ML (conferido contra `raw_json` de producao).

    Este fixture ja teve as chaves que o codigo esperava (`payments[].marketplace_fee`,
    `shipping.list_cost`) em vez das que o ML de fato manda — e por isso o bug de
    taxa/frete zerados passou por todos os testes desde a Fase 1: o teste so
    provava que o codigo concordava com ele mesmo. Cada campo abaixo que o codigo
    le tem que existir assim num payload real:

    - `sale_fee` mora em `order_items[]`, e e POR UNIDADE.
    - `shipping` e so `{"id": ...}`; o custo fica em `shipping_cost` na raiz, que
      no ML e `null` na maioria dos pedidos.
    - `payments[]` existe mas NAO tem `marketplace_fee`.
    """
    return {
        "id": order_id,
        "status": status,
        "date_closed": "2026-07-15T10:00:00.000-03:00",
        "total_amount": total,
        "shipping_cost": shipping_cost,
        "payments": [
            {
                "transaction_amount": total,
                "total_paid_amount": total,
                "taxes_amount": 0,
                "shipping_cost": 0,
            }
        ],
        "shipping": {"id": 47163566960},
        "buyer": {"id": buyer},
        "order_items": [
            {
                "item": {"id": item_id},
                "quantity": quantity,
                "unit_price": 50.0,
                "sale_fee": sale_fee,
            }
        ],
    }


class ClienteFake:
    """MLClient de mentira. Conta chamadas pra provar cache e nao-duplicacao."""

    def __init__(self, *, paid=None, cancelled=None, items=None, categories=None, claims=None):
        self.paid = paid or []
        self.cancelled = cancelled or []
        self.items = items or {}
        self.categories = categories or {}
        self.claims = claims or []
        self.chamadas_get_item: list[str] = []
        self.chamadas_get_orders: list[dict] = []

    def get_orders(self, *, seller_id, status, date_from, date_to, campo_data="date_created"):
        self.chamadas_get_orders.append(
            {"status": status, "de": date_from, "ate": date_to, "campo": campo_data}
        )
        return self.paid if status == "paid" else self.cancelled

    def get_item(self, item_id):
        self.chamadas_get_item.append(item_id)
        if item_id not in self.items:
            raise RuntimeError(f"item {item_id} nao existe")
        return self.items[item_id]

    def get_category(self, category_id):
        return self.categories.get(category_id, {"name": "Categoria Desconhecida"})

    def get_claims(self, *, seller_id, date_from, date_to=None):
        return self.claims


async def _ingere(pool, seller_id, cliente, **kw):
    return await ingest_janela(
        pool,
        seller_id,
        client=cliente,
        ml_seller_id=987654,
        date_from=JANELA[0],
        date_to=JANELA[1],
        **kw,
    )


async def test_grava_pedido_itens_e_caches(pg_pool, test_seller):
    _u, seller_id = test_seller
    cliente = ClienteFake(
        paid=[_pedido(1, shipping_cost=7.5)],
        items={"MLB1": {"title": "Fone Bluetooth", "category_id": "MLB1055"}},
        categories={"MLB1055": {"name": "Celulares"}},
    )
    resultado = await _ingere(pg_pool, seller_id, cliente)

    assert resultado.total_orders == 1
    assert resultado.distinct_items == 1
    assert resultado.warnings == []

    async with pg_pool.acquire() as conn:
        pedido = await conn.fetchrow(
            "SELECT * FROM orders WHERE seller_id = $1 AND order_id = 1", seller_id
        )
        item = await conn.fetchrow(
            "SELECT * FROM order_items WHERE seller_id = $1 AND order_id = 1", seller_id
        )
        cache = await conn.fetchrow(
            "SELECT * FROM items_cache WHERE seller_id = $1 AND item_id = 'MLB1'", seller_id
        )
        cat = await conn.fetchrow("SELECT * FROM categories_cache WHERE seller_id = $1", seller_id)
    assert float(pedido["total_amount"]) == 100.0
    assert float(pedido["marketplace_fee"]) == 12.0  # sale_fee 6.0 x 2 unidades
    assert float(pedido["shipping_cost"]) == 7.5
    assert pedido["buyer_id"] == 555
    assert item["quantity"] == 2
    assert cache["title"] == "Fone Bluetooth"
    assert cat["name"] == "Celulares"


async def _grava_e_le(pg_pool, seller_id, pedido):
    cliente = ClienteFake(
        paid=[pedido], items={"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    )
    resultado = await _ingere(pg_pool, seller_id, cliente)
    async with pg_pool.acquire() as conn:
        linha = await conn.fetchrow(
            "SELECT marketplace_fee, shipping_cost FROM orders "
            "WHERE seller_id = $1 AND order_id = $2",
            seller_id,
            pedido["id"],
        )
    return resultado, float(linha["marketplace_fee"]), float(linha["shipping_cost"])


async def test_payload_no_formato_real_do_ml_grava_taxa_diferente_de_zero(pg_pool, test_seller):
    """Regressao do bug de producao: R$ 16 mil de taxa gravados como zero.

    O codigo lia `payments[].marketplace_fee` e `shipping.list_cost`, campos que
    NUNCA existiram na API do ML — nao foi renomeacao. Cada pedido real entrava
    com taxa 0 e o dashboard mostrava margem inflada sem erro nenhum.
    """
    _u, seller_id = test_seller
    pedido = _pedido(1, sale_fee=172.5, quantity=1, total=1500.0)

    _r, taxa, _frete = await _grava_e_le(pg_pool, seller_id, pedido)

    assert taxa != 0.0, "taxa do ML zerada: o codigo nao esta lendo order_items[].sale_fee"
    assert taxa == 172.5


async def test_taxa_e_sale_fee_vezes_quantidade(pg_pool, test_seller):
    """`sale_fee` e por unidade: 2 pares a R$ 36 vieram com sale_fee 4.32 (12% de 36).

    Somar sem multiplicar pela quantidade subconta toda venda de mais de uma
    unidade. Duas linhas no mesmo pedido somam entre si.
    """
    _u, seller_id = test_seller
    pedido = _pedido(1, sale_fee=4.32, quantity=2)
    pedido["order_items"].append(
        {"item": {"id": "MLB2"}, "quantity": 3, "unit_price": 10.0, "sale_fee": 1.0}
    )

    _r, taxa, _f = await _grava_e_le(pg_pool, seller_id, pedido)

    assert taxa == pytest.approx(4.32 * 2 + 1.0 * 3)


async def test_campos_que_nunca_existiram_no_ml_nao_sao_lidos(pg_pool, test_seller):
    """Sem fallback: `marketplace_fee`/`list_cost` presentes NAO viram taxa/frete.

    Um fallback pra campo que nunca vem e exatamente o que escondeu o bug por
    meses: o valor sai zero e ninguem ve. Se um dia esses campos aparecerem, e
    decisao consciente ler, nao um acidente.
    """
    _u, seller_id = test_seller
    pedido = _pedido(1, sale_fee=None)
    del pedido["order_items"][0]["sale_fee"]
    pedido["payments"][0]["marketplace_fee"] = 99.0
    pedido["shipping"]["list_cost"] = 99.0

    _r, taxa, frete = await _grava_e_le(pg_pool, seller_id, pedido)

    assert (taxa, frete) == (0.0, 0.0)


def test_extrai_taxa_e_frete_tolera_nulos_do_ml():
    """`shipping_cost` e `sale_fee` chegam como `null` em muitos pedidos reais."""
    pedido = _pedido(1, sale_fee=None, shipping_cost=None)
    assert extrai_taxa_e_frete(pedido) == (0.0, 0.0)
    assert extrai_taxa_e_frete({"id": 1}) == (0.0, 0.0)
    assert extrai_taxa_e_frete(_pedido(1, sale_fee=3.0, quantity=2, shipping_cost=8.0)) == (
        6.0,
        8.0,
    )


async def test_avisa_quando_nenhum_pedido_da_janela_tem_sale_fee(pg_pool, test_seller):
    """Um aviso agregado por janela, nao um por pedido.

    Pedido isolado sem `sale_fee` acontece e nao merece alarme (com milhares de
    pedidos viraria ruido). Todos os pedidos da janela sem ele e a assinatura de
    o ML ter mudado o payload — o mesmo modo de falha silencioso do bug original.
    """
    _u, seller_id = test_seller
    sem_taxa = _pedido(1, sale_fee=None)
    del sem_taxa["order_items"][0]["sale_fee"]
    resultado, taxa, _f = await _grava_e_le(pg_pool, seller_id, sem_taxa)

    assert taxa == 0.0
    assert len([w for w in resultado.warnings if "sale_fee" in w]) == 1


async def test_pedido_isolado_sem_sale_fee_nao_gera_aviso(pg_pool, test_seller):
    _u, seller_id = test_seller
    sem_taxa = _pedido(2, sale_fee=None)
    del sem_taxa["order_items"][0]["sale_fee"]
    cliente = ClienteFake(
        paid=[_pedido(1), sem_taxa],
        items={"MLB1": {"title": "Fone", "category_id": "MLB1055"}},
    )
    resultado = await _ingere(pg_pool, seller_id, cliente)
    assert not [w for w in resultado.warnings if "sale_fee" in w]


async def test_ingestao_e_idempotente(pg_pool, test_seller):
    """Reprocessar a mesma janela nao duplica linha nenhuma.

    Importa porque um job repescado depois de lease vencido reprocessa a
    janela que estava no meio.
    """
    _u, seller_id = test_seller
    cliente = ClienteFake(
        paid=[_pedido(1)], items={"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    )
    await _ingere(pg_pool, seller_id, cliente)
    await _ingere(pg_pool, seller_id, cliente)

    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", seller_id) == 1
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM order_items WHERE seller_id = $1", seller_id)
            == 1
        )


async def test_mudanca_de_status_e_aplicada(pg_pool, test_seller):
    """paid -> cancelled TEM que atualizar a linha existente.

    Este e o bug que o filtro por date_created esconderia: sem o update, uma
    venda cancelada continuaria contando como receita pra sempre.
    """
    _u, seller_id = test_seller
    items = {"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    await _ingere(pg_pool, seller_id, ClienteFake(paid=[_pedido(1)], items=items))
    await _ingere(
        pg_pool, seller_id, ClienteFake(cancelled=[_pedido(1, status="cancelled")], items=items)
    )
    async with pg_pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM orders WHERE seller_id = $1 AND order_id = 1", seller_id
        )
    assert status == "cancelled"


async def test_nunca_grava_linha_de_outro_tenant(pg_pool, test_seller, outro_seller):
    """Ingerir pro seller A nao pode deixar NADA na conta do seller B.

    Um `seller_id` esquecido em qualquer um dos 5 INSERTs passaria em todos os
    outros testes — foi exatamente assim que o JOIN de categories_cache
    escapou na Sprint 1.
    """
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    cliente = ClienteFake(
        paid=[_pedido(1)],
        items={"MLB1": {"title": "Fone", "category_id": "MLB1055"}},
        claims=[{"id": 9, "resource_id": 1, "status": "opened", "date_created": "2026-07-20"}],
    )
    await _ingere(pg_pool, seller_a, cliente, incluir_claims=True)

    async with pg_pool.acquire() as conn:
        for tabela in ("orders", "order_items", "items_cache", "categories_cache", "claims"):
            n = await conn.fetchval(
                f"SELECT count(*) FROM {tabela} WHERE seller_id = $1",  # noqa: S608
                seller_b,
            )
            assert n == 0, f"{tabela} vazou pro outro tenant"


async def test_cache_de_item_e_por_seller(pg_pool, test_seller, outro_seller):
    """O cache de um seller nao serve pro outro.

    Se o lookup ignorasse seller_id, o seller B herdaria o titulo cacheado por
    A — e seu dashboard mostraria produto que ele nao vende.
    """
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    items = {"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    await _ingere(pg_pool, seller_a, ClienteFake(paid=[_pedido(1)], items=items))

    cliente_b = ClienteFake(paid=[_pedido(2)], items=items)
    await _ingere(pg_pool, seller_b, cliente_b)

    assert cliente_b.chamadas_get_item == ["MLB1"], "o cache de outro tenant foi reaproveitado"
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM items_cache WHERE seller_id = $1", seller_b)
            == 1
        )


async def test_cache_evita_segunda_chamada_no_mesmo_seller(pg_pool, test_seller):
    _u, seller_id = test_seller
    items = {"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    cliente = ClienteFake(paid=[_pedido(1), _pedido(2)], items=items)
    await _ingere(pg_pool, seller_id, cliente)
    assert cliente.chamadas_get_item == ["MLB1"]


async def test_falha_de_enriquecimento_nao_descarta_o_pedido(pg_pool, test_seller):
    """API do ML falhou no item: o pedido ja persistido NAO e perdido.

    Mesmo comportamento do src/ingest.py original: acumula warning e segue.
    """
    _u, seller_id = test_seller
    cliente = ClienteFake(paid=[_pedido(1, item_id="MLB_INEXISTENTE")], items={})
    resultado = await _ingere(pg_pool, seller_id, cliente)

    assert resultado.total_orders == 1
    assert len(resultado.warnings) == 1
    assert "MLB_INEXISTENTE" in resultado.warnings[0]
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", seller_id) == 1
        )


async def test_claims_so_quando_pedido(pg_pool, test_seller):
    _u, seller_id = test_seller
    cliente = ClienteFake(
        claims=[{"id": 9, "resource_id": 1, "status": "opened", "date_created": "2026-07-20"}]
    )
    resultado = await _ingere(pg_pool, seller_id, cliente)
    assert resultado.total_claims == 0

    resultado = await _ingere(pg_pool, seller_id, cliente, incluir_claims=True)
    assert resultado.total_claims == 1
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM claims WHERE seller_id = $1", seller_id) == 1
        )


async def test_repassa_campo_data_pro_cliente(pg_pool, test_seller):
    _u, seller_id = test_seller
    cliente = ClienteFake()
    await _ingere(pg_pool, seller_id, cliente, campo_data="date_last_updated")
    assert all(c["campo"] == "date_last_updated" for c in cliente.chamadas_get_orders)


async def test_nao_bloqueia_o_event_loop(pg_pool, test_seller):
    """O worker compartilha processo com a API: HTTP tem que ir pra thread.

    `MLClient` usa `requests`, que e bloqueante. Chamado direto de dentro do
    loop, ele congelaria a API inteira durante a ingestao. O relogio abaixo so
    avanca se o loop continuou girando.
    """
    _u, seller_id = test_seller

    class ClienteLento(ClienteFake):
        def get_orders(self, **kw):
            time.sleep(0.4)  # bloqueante DE PROPOSITO
            return []

    batidas = 0

    async def relogio():
        nonlocal batidas
        while True:
            await asyncio.sleep(0.01)
            batidas += 1

    tarefa = asyncio.create_task(relogio())
    try:
        await _ingere(pg_pool, seller_id, ClienteLento())
    finally:
        tarefa.cancel()

    # Duas chamadas de 0.4s bloqueantes = 0.8s. Se foram pra thread, o relogio
    # bateu dezenas de vezes; se travaram o loop, bateu ~0.
    assert batidas > 20, f"o event loop ficou travado (batidas={batidas})"


async def test_falha_ao_baixar_pedidos_aborta_a_janela(pg_pool, test_seller):
    """Falha de rede em get_orders NAO pode virar janela "concluida".

    Se a busca de cancelados falhar e a janela for dada como pronta, as
    cancelacoes somem e a receita fica inflada. O delta seguinte filtra por
    date_last_updated numa janela nova e nunca volta pra buscar — numero errado
    pra sempre. Estourando, a fila repesca o job.
    """
    _u, seller_id = test_seller

    class FalhaNosCancelados(ClienteFake):
        def get_orders(self, *, status, **kw):
            if status == "cancelled":
                raise RuntimeError("timeout na API do ML")
            return super().get_orders(status=status, **kw)

    cliente = FalhaNosCancelados(
        paid=[_pedido(1)], items={"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    )
    with pytest.raises(RuntimeError):
        await _ingere(pg_pool, seller_id, cliente)


async def test_falha_em_claims_so_avisa(pg_pool, test_seller):
    """Claim e enriquecimento, nao receita: falhar ali nao invalida a janela.

    A distincao e essa — o que muda um numero que o usuario usa pra decidir
    aborta; o que degrada um rotulo vira aviso.
    """
    _u, seller_id = test_seller

    class FalhaNosClaims(ClienteFake):
        def get_claims(self, **kw):
            raise RuntimeError("500 do ML")

    cliente = FalhaNosClaims(
        paid=[_pedido(1)], items={"MLB1": {"title": "Fone", "category_id": "MLB1055"}}
    )
    resultado = await _ingere(pg_pool, seller_id, cliente, incluir_claims=True)

    assert resultado.total_orders == 1, "o pedido tinha que ter sido gravado"
    assert any("claims" in w for w in resultado.warnings)


async def test_claim_com_resource_id_zero_nao_e_descartado(pg_pool, test_seller):
    """`0` e falsy em Python, mas e um id presente.

    Com `if claim.get("resource_id")`, um resource_id de 0 cairia no order_id —
    que aqui e outro numero. O teste fixa que a checagem e de presenca.
    """
    _u, seller_id = test_seller
    cliente = ClienteFake(
        claims=[
            {
                "id": 9,
                "resource_id": 0,
                "order_id": 12345,
                "status": "opened",
                "date_created": "2026-07-20",
            }
        ]
    )
    await _ingere(pg_pool, seller_id, cliente, incluir_claims=True)
    async with pg_pool.acquire() as conn:
        gravado = await conn.fetchval(
            "SELECT order_id FROM claims WHERE seller_id = $1 AND claim_id = 9", seller_id
        )
    assert gravado == 0, "resource_id 0 foi descartado por truthiness"
