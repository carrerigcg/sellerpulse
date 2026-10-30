"""Registro de acesso do Marco Civil. Decisões em
docs/specs/2026-10-30-registro-de-acesso-design.md."""

from __future__ import annotations

import pytest

from .test_routers_ml import _auth
from .test_routers_ml import client as _client_ml

client = _client_ml

URL = "/conta/registro-de-acesso"


async def _registros(pool, user_id):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT ip FROM registros_de_acesso WHERE user_id = $1 ORDER BY ip", user_id
        )


@pytest.fixture(autouse=True)
async def _limpa(pg_pool):
    yield
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM registros_de_acesso")


async def test_grava_o_ip_do_navegador(client, pg_pool, test_seller):
    user_id, _ = test_seller
    cabecalhos = {**_auth(user_id), "X-Forwarded-For": "203.0.113.9, 10.0.0.1"}
    assert client.post(URL, headers=cabecalhos).status_code == 204
    linhas = await _registros(pg_pool, user_id)
    assert [linha["ip"] for linha in linhas] == ["203.0.113.9, 10.0.0.1"]


async def test_mesma_hora_e_mesmo_ip_nao_duplicam(client, pg_pool, test_seller):
    user_id, _ = test_seller
    cabecalhos = {**_auth(user_id), "X-Forwarded-For": "203.0.113.9"}
    client.post(URL, headers=cabecalhos)
    client.post(URL, headers=cabecalhos)
    assert len(await _registros(pg_pool, user_id)) == 1


async def test_outro_ip_na_mesma_hora_gera_outra_linha(client, pg_pool, test_seller):
    user_id, _ = test_seller
    client.post(URL, headers={**_auth(user_id), "X-Forwarded-For": "203.0.113.9"})
    client.post(URL, headers={**_auth(user_id), "X-Forwarded-For": "203.0.113.10"})
    assert len(await _registros(pg_pool, user_id)) == 2


def test_sem_token_nao_grava(client):
    assert client.post(URL).status_code in (401, 403)


async def test_apaga_so_o_que_passou_de_seis_meses(client, pg_pool, test_seller):
    user_id, _ = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO registros_de_acesso (user_id, ip, hora) VALUES
                ($1, 'velho', now() - interval '6 months' - interval '1 day'),
                ($1, 'dentro', now() - interval '6 months' + interval '1 day')
            """,
            user_id,
        )
    client.post(URL, headers={**_auth(user_id), "X-Forwarded-For": "203.0.113.9"})
    linhas = await _registros(pg_pool, user_id)
    assert [linha["ip"] for linha in linhas] == ["203.0.113.9", "dentro"]


async def test_o_registro_sobrevive_a_exclusao_da_conta(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    client.post(URL, headers={**_auth(user_id), "X-Forwarded-For": "203.0.113.9"})
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM sellers WHERE id = $1", seller_id)
    assert len(await _registros(pg_pool, user_id)) == 1
