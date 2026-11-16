"""MCP da conta real (Premium).

Spec: docs/specs/2026-11-09-premium-mcp-conta-real-design.md. O que importa
aqui é a fronteira: o token de um login nunca lê a loja de outro, o token da
IA não serve na API REST (e a sessão do site não serve no MCP), desconectar
corta na hora, e o plano é lido a cada chamada.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, date, datetime, timedelta

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from backend import main, mcp_conta
from backend.db import close_pool
from backend.main import app

from .conftest import TEST_DATABASE_URL, da_plano

SEGREDO = "segredo-do-supabase-de-teste"

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3, 'paid', $4, 10, 5, 1, '{}'::jsonb, now())
"""


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SEGREDO)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")
    monkeypatch.setenv("DEMO_REFRESH_IN_PROCESS", "0")
    mcp_conta._chamadas.clear()


@pytest.fixture(autouse=True)
async def _pool_global_limpo():
    # Mesmo motivo de test_mcp_server: as ferramentas chamam `get_pool()` direto.
    yield
    await close_pool()


def _token(user_id, sessao, *, cliente: str | None = "claude", aal: str | None = None) -> str:
    claims = {
        "sub": str(user_id),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "session_id": str(sessao),
    }
    if cliente:
        claims["client_id"] = cliente
    if aal:
        claims["aal"] = aal
    return jwt.encode(claims, SEGREDO, algorithm="HS256")


async def _sessao(pool, user_id) -> uuid.UUID:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO auth.sessions (user_id) VALUES ($1) RETURNING id", user_id
        )


async def _loja(pool, seller_id, apelido: str, ml_id: int, receita: float) -> None:
    """Conecta a conta ao ML com um apelido e uma venda de ontem."""
    ontem = datetime.now(UTC) - timedelta(days=1)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET ml_seller_id = $2, ml_nickname = $3 WHERE id = $1",
            seller_id,
            ml_id,
            apelido,
        )
        await conn.execute(_INSERT_ORDER, ml_id * 1000 + 1, seller_id, ontem, receita)


async def _como(token: str, nome: str, **kwargs):
    """Chama a ferramenta como o cliente de IA, já autenticado pelo verificador."""
    acesso = await mcp_conta.VerificadorSupabase().verify_token(token)
    assert acesso is not None, "o verificador recusou um token que devia passar"
    marca = auth_context_var.set(AuthenticatedUser(acesso))
    try:
        resultado = await mcp_conta.mcp.call_tool(nome, kwargs)
    except Exception as exc:
        raise (exc.__cause__ or exc) from None
    finally:
        auth_context_var.reset(marca)
    return resultado.structured_content


# --------------------------------------------------------------------------
# O token
# --------------------------------------------------------------------------


async def test_sessao_do_site_nao_entra_no_mcp(pg_pool, test_seller):
    user_id, _ = test_seller
    sessao = await _sessao(pg_pool, user_id)
    token = _token(user_id, sessao, cliente=None)
    assert await mcp_conta.VerificadorSupabase().verify_token(token) is None


async def test_desconectar_corta_na_chamada_seguinte(pg_pool, test_seller):
    user_id, _ = test_seller
    sessao = await _sessao(pg_pool, user_id)
    token = _token(user_id, sessao)
    assert await mcp_conta.VerificadorSupabase().verify_token(token) is not None

    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.sessions WHERE id = $1", sessao)

    assert await mcp_conta.VerificadorSupabase().verify_token(token) is None


async def test_quem_ativou_o_app_autenticador_precisa_do_codigo(pg_pool, test_seller):
    user_id, _ = test_seller
    sessao = await _sessao(pg_pool, user_id)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.mfa_factors (user_id, factor_type, status) "
            "VALUES ($1, 'totp', 'verified')",
            user_id,
        )
    verificador = mcp_conta.VerificadorSupabase()
    assert await verificador.verify_token(_token(user_id, sessao, aal="aal1")) is None
    assert await verificador.verify_token(_token(user_id, sessao, aal="aal2")) is not None


async def test_token_da_ia_nao_serve_na_api_rest(pg_pool, test_seller):
    """Na REST ele gravaria custo e cancelaria a assinatura (decisão 4)."""
    user_id, _ = test_seller
    sessao = await _sessao(pg_pool, user_id)
    with TestClient(app) as c:
        resp = c.get(
            "/conta/acesso", headers={"Authorization": f"Bearer {_token(user_id, sessao)}"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"]["codigo"] == "token-de-ia"


# --------------------------------------------------------------------------
# De quem é o dado
# --------------------------------------------------------------------------


async def test_cada_login_le_so_a_propria_loja(pg_pool, test_seller, outro_seller):
    user_a, seller_a = test_seller
    user_b, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await da_plano(conn, seller_b, "premium")
    await _loja(pg_pool, seller_a, "LOJA_A", 11, 100.0)
    await _loja(pg_pool, seller_b, "LOJA_B", 22, 900.0)
    token_a = _token(user_a, await _sessao(pg_pool, user_a))

    resposta = await _como(token_a, "visao_geral")

    assert resposta["contas"] == ["LOJA_A"]
    assert resposta["dados"]["receita_bruta"] == 100.0


async def test_o_apelido_de_outro_login_nao_abre(pg_pool, test_seller, outro_seller):
    user_a, seller_a = test_seller
    _user_b, seller_b = outro_seller
    await _loja(pg_pool, seller_a, "LOJA_A", 11, 100.0)
    await _loja(pg_pool, seller_b, "LOJA_B", 22, 900.0)
    token_a = _token(user_a, await _sessao(pg_pool, user_a))

    with pytest.raises(ValueError, match="LOJA_A"):
        await _como(token_a, "visao_geral", conta="LOJA_B")


async def test_todas_soma_so_as_contas_do_login(pg_pool, test_seller, outro_seller):
    user_a, seller_a = test_seller
    _user_b, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        extra = await conn.fetchval(
            "INSERT INTO sellers (user_id, principal) VALUES ($1, false) RETURNING id", user_a
        )
    await _loja(pg_pool, seller_a, "LOJA_A", 11, 100.0)
    await _loja(pg_pool, extra, "LOJA_A2", 12, 50.0)
    await _loja(pg_pool, seller_b, "LOJA_B", 22, 900.0)
    token_a = _token(user_a, await _sessao(pg_pool, user_a))

    resposta = await _como(token_a, "visao_geral", conta="todas")
    assert resposta["soma_das_contas"] is True
    assert sorted(resposta["contas"]) == ["LOJA_A", "LOJA_A2"]
    assert resposta["dados"]["receita_bruta"] == 150.0

    so_a2 = await _como(token_a, "visao_geral", conta="loja_a2")
    assert so_a2["contas"] == ["LOJA_A2"]
    assert so_a2["dados"]["receita_bruta"] == 50.0


async def test_fora_do_premium_a_resposta_aponta_a_assinatura(pg_pool, test_seller):
    user_id, seller_id = test_seller
    async with pg_pool.acquire() as conn:
        await da_plano(conn, seller_id, "exclusive")
    token = _token(user_id, await _sessao(pg_pool, user_id))

    with pytest.raises(ValueError, match="Premium"):
        await _como(token, "visao_geral")


async def test_a_chamada_entra_no_registro_de_acesso(pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _loja(pg_pool, seller_id, "LOJA_A", 11, 100.0)
    token = _token(user_id, await _sessao(pg_pool, user_id))

    await _como(token, "fluxo_financeiro")

    async with pg_pool.acquire() as conn:
        linhas = await conn.fetchval(
            "SELECT count(*) FROM registros_de_acesso WHERE user_id = $1", user_id
        )
    assert linhas == 1


async def test_o_periodo_antes_do_historico_e_cortado_e_dito(pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _loja(pg_pool, seller_id, "LOJA_A", 11, 100.0)
    token = _token(user_id, await _sessao(pg_pool, user_id))
    hoje = date.today()

    resposta = await _como(
        token,
        "fluxo_financeiro",
        date_from=(hoje - timedelta(days=500)).isoformat(),
        date_to=hoje.isoformat(),
    )

    assert "historico_desde" in resposta
    assert resposta["periodo"]["de"] == resposta["historico_desde"]


# --------------------------------------------------------------------------
# Limite de uso
# --------------------------------------------------------------------------


def test_a_chamada_301_da_hora_e_recusada():
    for i in range(mcp_conta.LIMITE_POR_HORA):
        assert mcp_conta.conta_chamada("u", agora=1000.0 + i)
    assert not mcp_conta.conta_chamada("u", agora=1400.0)
    # Uma hora depois da primeira, abre uma vaga.
    assert mcp_conta.conta_chamada("u", agora=4600.5)
    # Outro login tem o próprio limite.
    assert mcp_conta.conta_chamada("outro", agora=1400.0)


# --------------------------------------------------------------------------
# Pelo HTTP, como o Claude chega
# --------------------------------------------------------------------------


def _post_mcp(c, token: str | None, metodo: str, params: dict):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return c.post(
        "/mcp/conta",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params},
    )


def test_sem_token_o_claude_e_mandado_para_o_login(monkeypatch):
    monkeypatch.setattr(main, "_MCP_HOSTS", ["testserver"])
    with TestClient(app) as c:
        resp = _post_mcp(c, None, "tools/list", {})
        assert resp.status_code == 401
        assert "resource_metadata=" in resp.headers["www-authenticate"]
        assert (
            "/.well-known/oauth-protected-resource/mcp/conta" in (resp.headers["www-authenticate"])
        )

        meta = c.get("/.well-known/oauth-protected-resource/mcp/conta")
        assert meta.status_code == 200
        assert meta.json()["resource"] == mcp_conta.URL_DO_RECURSO
        assert meta.json()["authorization_servers"] == [mcp_conta.emissor()]


async def test_com_token_o_protocolo_responde_em_mcp_conta(monkeypatch, pg_pool, test_seller):
    """Prova o mount: /mcp/conta não cai no /mcp da demo, e o token passa."""
    monkeypatch.setattr(main, "_MCP_HOSTS", ["testserver"])
    user_id, _ = test_seller
    token = _token(user_id, await _sessao(pg_pool, user_id))
    await close_pool()  # o TestClient abre o próprio, no loop dele
    with TestClient(app) as c:
        resp = _post_mcp(
            c,
            token,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        )
        assert resp.status_code == 200, resp.text
        dados = next(
            json.loads(linha[5:]) for linha in resp.text.splitlines() if linha.startswith("data:")
        )
        assert dados["result"]["serverInfo"]["name"] == "sellerpulse"
