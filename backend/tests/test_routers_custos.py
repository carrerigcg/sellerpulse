"""Endpoints de custo de produto — o primeiro ponto de escrita do vendedor.

O que estes testes protegem não é a feature, é a fronteira: até esta sprint
nenhum cliente escrevia no banco. Um `seller_id` aceito do corpo, ou um
`item_id` não validado, seria escrita cruzada entre tenants num SaaS.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.main import app

from .conftest import TEST_DATABASE_URL

TEST_JWT_SECRET = "test-secret-do-supabase"

pytestmark = pytest.mark.asyncio

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, 'paid', $4, 0, 0, 1001, '{}'::jsonb, now())
"""


def _token(user_id) -> dict[str, str]:
    agora = int(time.time())
    payload = {"sub": str(user_id), "aud": "authenticated", "exp": agora + 3600}
    codificado = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {codificado}"}


async def _vendeu(pool, seller_id, order_id, item_id, titulo, qtd, preco, quando):
    dt = datetime.fromisoformat(quando)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO categories_cache (seller_id, category_id, name, fetched_at)"
            " VALUES ($1,'CAT1','Categoria',now()) ON CONFLICT DO NOTHING",
            seller_id,
        )
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at)"
            " VALUES ($1,$2,$3,'CAT1',now()) ON CONFLICT DO NOTHING",
            seller_id,
            item_id,
            titulo,
        )
        await conn.execute(_INSERT_ORDER, order_id, seller_id, dt, qtd * preco)
        await conn.execute(
            "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price)"
            " VALUES ($1,$2,$3,$4,$5)",
            seller_id,
            order_id,
            item_id,
            qtd,
            preco,
        )


async def _linhas_de_custo(pool, seller_id, item_id):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT vigente_desde, custo_unitario FROM product_costs"
            " WHERE seller_id=$1 AND item_id=$2 ORDER BY vigente_desde",
            seller_id,
            item_id,
        )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")
    with TestClient(app) as c:
        yield c


_JANELA = {"date_from": "2026-07-01", "date_to": "2026-08-01"}


# ---------- leitura ----------


async def test_get_lista_produtos_vendidos_sem_custo_como_none(client, pg_pool, test_seller):
    """Ausência de custo é `null`, nunca `0`. A tela depende dessa distinção."""
    user_id, sid = test_seller
    # Dois produtos, e nao um: com um so, a receita acumulada dele e 100% e a
    # classe sai C pela regra 80/15/5. Correto, e inutil como fixture.
    await _vendeu(pg_pool, sid, 1, "MLB1", "Cabeca", 2, 400.0, "2026-07-25T13:00:00+00:00")
    await _vendeu(pg_pool, sid, 2, "MLB2", "Cauda", 1, 200.0, "2026-07-26T13:00:00+00:00")

    resp = client.get("/custos", params=_JANELA, headers=_token(user_id))

    assert resp.status_code == 200
    corpo = resp.json()
    assert [linha["sku"] for linha in corpo] == ["MLB1", "MLB2"], "receita decrescente"

    linha = corpo[0]
    assert linha["titulo"] == "Cabeca"
    assert linha["classe"] == "A"
    assert linha["receita"] == pytest.approx(800.0)
    assert linha["unidades"] == 2
    assert linha["custo_unitario"] is None
    assert linha["vigente_desde"] is None


async def test_get_reflete_o_custo_gravado(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 2, 50.0, "2026-07-25T13:00:00+00:00")

    gravou = client.put("/custos/MLB1", json={"custo_unitario": 12.5}, headers=_token(user_id))
    assert gravou.status_code == 200

    linha = client.get("/custos", params=_JANELA, headers=_token(user_id)).json()[0]
    assert linha["custo_unitario"] == pytest.approx(12.5)
    assert linha["vigente_desde"] is not None


# ---------- escrita ----------


async def test_dois_put_no_mesmo_dia_geram_uma_linha(client, pg_pool, test_seller):
    """Upsert na chave (seller_id, item_id, vigente_desde) — não duas vigências."""
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    client.put("/custos/MLB1", json={"custo_unitario": 10.0}, headers=_token(user_id))
    client.put("/custos/MLB1", json={"custo_unitario": 11.0}, headers=_token(user_id))

    linhas = await _linhas_de_custo(pg_pool, sid, "MLB1")
    assert len(linhas) == 1
    assert float(linhas[0]["custo_unitario"]) == 11.0


async def test_custo_zero_e_aceito(client, pg_pool, test_seller):
    """Zero é afirmação legítima e tem que ser gravável — diferente de vazio."""
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Brinde", 1, 50.0, "2026-07-25T13:00:00+00:00")

    resp = client.put("/custos/MLB1", json={"custo_unitario": 0}, headers=_token(user_id))

    assert resp.status_code == 200
    linha = client.get("/custos", params=_JANELA, headers=_token(user_id)).json()[0]
    assert linha["custo_unitario"] == 0.0, "zero gravado volta como 0.0, não como null"


@pytest.mark.parametrize("valor", [-1, -0.01, 1e12])
async def test_valor_invalido_e_recusado(client, pg_pool, test_seller, valor):
    """Negativo, absurdo e infinito não entram.

    O teto não é regra de negócio: é a trava contra 48,00 virar 4800000,00 num
    escorregão de teclado e derrubar a margem do mês sem nada reclamar.
    """
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    resp = client.put("/custos/MLB1", json={"custo_unitario": valor}, headers=_token(user_id))

    assert resp.status_code == 422
    assert await _linhas_de_custo(pg_pool, sid, "MLB1") == []


async def test_infinito_no_corpo_cru_nao_grava_nada(client, pg_pool, test_seller):
    """`Infinity` so chega como corpo CRU: JSON nao tem infinito.

    `json.dumps` do Python emite `Infinity` por padrao (allow_nan=True) e
    varios parsers o aceitam, entao a string circula no mundo real mesmo nao
    sendo JSON valido.

    O que este teste fixa e o comportamento ATUAL, que tem uma aspereza de
    terceiros: o pydantic recusa o valor corretamente, mas o FastAPI estoura
    ao serializar a propria resposta de erro, porque ela ecoa o valor recebido
    (`json.dumps(inf)` -> "Out of range float values are not JSON compliant").
    O cliente recebe 500 em vez de 422 — ver fastapi#14680.

    A propriedade que importa continua valida e e a que esta asseverada: NADA
    e gravado. O dia em que uma versao nova do FastAPI consertar isso, este
    teste falha e avisa — que e exatamente o sinal desejado.
    """
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    with pytest.raises(ValueError, match="not JSON compliant"):
        client.put(
            "/custos/MLB1",
            content=b'{"custo_unitario": Infinity}',
            headers={**_token(user_id), "Content-Type": "application/json"},
        )

    assert await _linhas_de_custo(pg_pool, sid, "MLB1") == [], "nada gravado, que e o ponto"


# ---------- isolamento entre vendedores ----------


async def test_item_de_outro_vendedor_e_recusado(client, pg_pool, test_seller, outro_seller):
    """404, não 403: dizer que existe mas não é seu já vaza a existência do item."""
    user_id, sid = test_seller
    _, outro_sid = outro_seller
    await _vendeu(
        pg_pool, outro_sid, 1, "ALHEIO", "Do vizinho", 1, 50.0, "2026-07-25T13:00:00+00:00"
    )

    resp = client.put("/custos/ALHEIO", json={"custo_unitario": 10.0}, headers=_token(user_id))

    assert resp.status_code == 404
    assert await _linhas_de_custo(pg_pool, outro_sid, "ALHEIO") == []
    assert await _linhas_de_custo(pg_pool, sid, "ALHEIO") == []


async def test_seller_id_no_corpo_nao_tem_efeito(client, pg_pool, test_seller, outro_seller):
    """O corpo não tem campo `seller_id`; mandá-lo não redireciona a escrita."""
    user_id, sid = test_seller
    _, outro_sid = outro_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    resp = client.put(
        "/custos/MLB1",
        json={"custo_unitario": 7.0, "seller_id": str(outro_sid)},
        headers=_token(user_id),
    )

    assert resp.status_code == 200
    assert len(await _linhas_de_custo(pg_pool, sid, "MLB1")) == 1, "gravou no dono do token"
    assert await _linhas_de_custo(pg_pool, outro_sid, "MLB1") == [], "e em mais ninguém"


async def test_sem_token_nao_passa(client, pg_pool, test_seller):
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    assert client.get("/custos", params=_JANELA).status_code == 401
    assert client.put("/custos/MLB1", json={"custo_unitario": 1.0}).status_code == 401
    assert await _linhas_de_custo(pg_pool, sid, "MLB1") == []


# ---------- remoção ----------


async def test_delete_remove_so_a_vigencia_de_hoje(client, pg_pool, test_seller):
    """Desfaz o erro do dia sem tocar no histórico."""
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO product_costs (seller_id, item_id, vigente_desde, custo_unitario)"
            " VALUES ($1,'MLB1',$2,9.0)",
            sid,
            date(2026, 7, 1),
        )
    client.put("/custos/MLB1", json={"custo_unitario": 99.0}, headers=_token(user_id))

    resp = client.delete("/custos/MLB1", headers=_token(user_id))

    assert resp.status_code == 200
    assert resp.json()["removido"] is True
    linhas = await _linhas_de_custo(pg_pool, sid, "MLB1")
    assert [float(linha["custo_unitario"]) for linha in linhas] == [9.0], "o passado fica"


async def test_delete_sem_nada_gravado_hoje_nao_e_erro(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    resp = client.delete("/custos/MLB1", headers=_token(user_id))

    assert resp.status_code == 200
    assert resp.json()["removido"] is False


async def test_put_retroativo_grava_tambem_o_inicio_do_historico(client, pg_pool, test_seller):
    """A opção da tela chega ao banco (docs/specs/2026-10-28-custo-retroativo-design.md)."""
    from backend.analytics.custos_pg import VIGENCIA_DO_HISTORICO

    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    resp = client.put(
        "/custos/MLB1", json={"custo_unitario": 12.0, "retroativo": True}, headers=_token(user_id)
    )

    assert resp.status_code == 200
    linhas = await _linhas_de_custo(pg_pool, sid, "MLB1")
    assert linhas[0]["vigente_desde"] == VIGENCIA_DO_HISTORICO
    assert [float(x["custo_unitario"]) for x in linhas] == [12.0, 12.0]


async def test_put_sem_o_campo_retroativo_continua_so_de_hoje(client, pg_pool, test_seller):
    """Cliente antigo, que não manda o campo, mantém o comportamento de antes."""
    user_id, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", "Produto 1", 1, 50.0, "2026-07-25T13:00:00+00:00")

    client.put("/custos/MLB1", json={"custo_unitario": 12.0}, headers=_token(user_id))

    assert len(await _linhas_de_custo(pg_pool, sid, "MLB1")) == 1
