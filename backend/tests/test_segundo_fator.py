"""Verificação em duas etapas: o backend não aceita só a senha de quem a ativou.

Spec: docs/specs/2026-11-04-telefone-e-verificacao-em-duas-etapas-design.md,
decisão 10. Sem esta trava, a verificação seria só de tela: com a senha, o
token `aal1` chamaria a API direto.
"""

from __future__ import annotations

import time

import jwt

from .test_routers_ml import TEST_JWT_SECRET
from .test_routers_ml import client as _client_ml

client = _client_ml


def _auth(user_id, aal: str | None = "aal1") -> dict[str, str]:
    claims = {"sub": str(user_id), "aud": "authenticated", "exp": int(time.time()) + 3600}
    if aal:
        claims["aal"] = aal
    return {"Authorization": f"Bearer {jwt.encode(claims, TEST_JWT_SECRET, algorithm='HS256')}"}


async def _fator(pool, user_id, status="verified"):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.mfa_factors (user_id, factor_type, status) VALUES ($1, 'totp', $2)",
            user_id,
            status,
        )


async def test_com_o_fator_ativo_so_a_senha_nao_entra(client, pg_pool, test_seller):
    user_id, _ = test_seller
    await _fator(pg_pool, user_id)

    resp = client.get("/conta/acesso", headers=_auth(user_id, "aal1"))

    assert resp.status_code == 401
    assert resp.json()["detail"]["codigo"] == "segundo-fator"


async def test_com_o_fator_ativo_e_o_codigo_entra(client, pg_pool, test_seller):
    user_id, _ = test_seller
    await _fator(pg_pool, user_id)
    assert client.get("/conta/acesso", headers=_auth(user_id, "aal2")).status_code == 200


async def test_fator_nao_confirmado_nao_exige_codigo(client, pg_pool, test_seller):
    """A pessoa começou a ativar e fechou a tela: ainda não há o que pedir."""
    user_id, _ = test_seller
    await _fator(pg_pool, user_id, status="unverified")
    assert client.get("/conta/acesso", headers=_auth(user_id, "aal1")).status_code == 200


async def test_sem_fator_o_token_de_sempre_entra(client, test_seller):
    user_id, _ = test_seller
    assert client.get("/conta/acesso", headers=_auth(user_id, None)).status_code == 200


async def test_rota_que_so_le_o_token_tambem_exige(client, pg_pool, test_seller):
    user_id, _ = test_seller
    await _fator(pg_pool, user_id)

    resp = client.post("/conta/registro-de-acesso", headers=_auth(user_id, "aal1"))

    assert resp.status_code == 401
    assert resp.json()["detail"]["codigo"] == "segundo-fator"
