"""Testes dos endpoints de conexao com o Mercado Livre."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import asyncpg
import jwt
import pytest
import responses as responses_lib
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.jobs import queue
from backend.main import app
from backend.ml import oauth
from backend.ml import tokens as tokens_mod
from backend.ml.tokens import PostgresTokenStore
from src.auth import TokenSet

from .conftest import TEST_DATABASE_URL

TEST_JWT_SECRET = "test-secret-do-supabase"


def _make_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": str(user_id), "aud": "authenticated", "exp": int(time.time()) + 3600},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(str(user_id))}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("STATE_SECRET", "segredo-de-teste-do-state")
    monkeypatch.setenv("ML_CLIENT_ID", "1234567890")
    monkeypatch.setenv("ML_CLIENT_SECRET", "secret-do-app-ml")
    monkeypatch.setenv("ML_REDIRECT_URI", "https://api.exemplo.dev/ml/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://app.exemplo.dev")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    # O worker in-process (task posterior) fica DESLIGADO nos testes de router:
    # senao ele drenaria os jobs que os testes acabaram de enfileirar e as
    # assercoes sobre a fila ficariam nao-deterministicas.
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")
    tokens_mod._fernet.cache_clear()
    with TestClient(app) as c:
        yield c
    tokens_mod._fernet.cache_clear()


def _mock_ml_conexao(rsps, *, ml_user_id=987654, nickname="LOJA_TESTE"):
    rsps.add(
        responses_lib.POST,
        "https://api.mercadolibre.com/oauth/token",
        json={
            "access_token": "APP_USR-do-callback",
            "refresh_token": "TG-do-callback",
            "expires_in": 21600,
        },
    )
    rsps.add(
        responses_lib.GET,
        "https://api.mercadolibre.com/users/me",
        json={"id": ml_user_id, "nickname": nickname},
    )


# ---------- start ----------


async def test_start_devolve_url_de_consentimento(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    resp = client.post("/ml/connect/start", headers=_auth(user_id))
    assert resp.status_code == 200
    url = resp.json()["url"]
    assert url.startswith("https://auth.mercadolivre.com.br/authorization?")
    assert "secret-do-app-ml" not in url


async def test_start_exige_autenticacao(client):
    # 401, nao 403: mesmo Depends(get_current_seller_id) -> HTTPBearer() dos
    # endpoints de /metrics, ja confirmado nesta versao do FastAPI (0.141.1)
    # por test_routers.py::test_sem_token_devolve_401.
    assert client.post("/ml/connect/start").status_code == 401


# ---------- callback ----------


async def test_callback_grava_token_cifrado_e_dados_do_seller(client, pg_pool, test_seller):
    _u, seller_id = test_seller
    state = oauth.emite_state(str(seller_id))

    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps)
        resp = client.get(
            "/ml/callback",
            params={"code": "TG-code-do-ml", "state": state},
            follow_redirects=False,
        )

    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://app.exemplo.dev/")

    guardado = await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load()
    assert guardado.access_token == "APP_USR-do-callback"

    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT ml_seller_id, ml_nickname FROM sellers WHERE id = $1", seller_id
        )
    assert row["ml_seller_id"] == 987654
    assert row["ml_nickname"] == "LOJA_TESTE"


async def test_callback_enfileira_backfill(client, pg_pool, test_seller):
    """Conectar sem enfileirar deixaria o usuario numa tela vazia para sempre."""
    _u, seller_id = test_seller
    state = oauth.emite_state(str(seller_id))
    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps)
        client.get(
            "/ml/callback",
            params={"code": "TG-code", "state": state},
            follow_redirects=False,
        )
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT kind, status FROM sync_jobs WHERE seller_id = $1", seller_id
        )
    assert row["kind"] == "backfill"
    assert row["status"] == "queued"


async def test_callback_com_state_invalido_nao_grava_nada(client, pg_pool, test_seller):
    """State malformado e recusado. NAO prova a checagem de assinatura —
    quem prova isso e test_callback_com_state_forjado_de_uuid_cru_nao_grava_nada."""
    _u, seller_id = test_seller
    resp = client.get(
        "/ml/callback",
        params={"code": "TG-code", "state": "lixo"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "erro=state" in resp.headers["location"]
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is None


async def test_callback_com_state_forjado_de_uuid_cru_nao_grava_nada(client, pg_pool, test_seller):
    """O ataque de verdade: UUID bem-formado e SEM assinatura como state.

    `state="lixo"` nao prova nada — ele morre no uuid.UUID() antes de chegar na
    validacao de assinatura, e o teste passa igual se a validacao for removida
    (verificado por mutacao). Este aqui passa pelo parse e so e recusado porque
    a assinatura E checada. Sem essa checagem, quem descobrisse o seller_id de
    uma vitima plugaria a PROPRIA conta do Mercado Livre no dashboard DELA.

    O RequestsMock sem nada registrado e de proposito: se o callback seguir
    adiante, a chamada ao ML estoura aqui em vez de sair pra internet de
    verdade no meio de um teste.
    """
    _u, seller_id = test_seller
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False):
        resp = client.get(
            "/ml/callback",
            params={"code": "TG-code", "state": str(seller_id)},
            follow_redirects=False,
        )
    assert resp.status_code == 307
    assert "erro=state" in resp.headers["location"]
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is None


async def test_callback_com_consentimento_negado_redireciona_sem_job(client, pg_pool, test_seller):
    _u, seller_id = test_seller
    resp = client.get(
        "/ml/callback",
        params={"error": "access_denied", "state": oauth.emite_state(str(seller_id))},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "erro=recusado" in resp.headers["location"]
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sync_jobs") == 0


async def test_callback_recusa_conta_ml_ja_conectada_em_outro_seller(
    client, pg_pool, test_seller, outro_seller
):
    """Duas contas do SellerPulse nao podem ingerir a mesma loja do ML.

    Sem esta trava, dois tenants gravariam o mesmo historico e cada um veria
    numeros que nao sao dele — sem nenhum erro aparecendo em lugar nenhum.
    """
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET ml_seller_id = 987654 WHERE id = $1", seller_a)

    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps, ml_user_id=987654)
        resp = client.get(
            "/ml/callback",
            params={"code": "TG-code", "state": oauth.emite_state(str(seller_b))},
            follow_redirects=False,
        )

    assert "erro=ja-conectada" in resp.headers["location"]
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_b).load() is None


async def test_banco_recusa_dois_sellers_com_a_mesma_conta_ml(pg_pool, test_seller, outro_seller):
    """A trava final e do banco, nao do SELECT no callback.

    O SELECT no callback e check-then-write: sob corrida, os dois passam. Esta
    constraint e o que impede de verdade dois tenants ingerirem a mesma loja.
    """
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET ml_seller_id = 555 WHERE id = $1", seller_a)
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await conn.execute("UPDATE sellers SET ml_seller_id = 555 WHERE id = $1", seller_b)


async def test_varios_sellers_sem_conta_ml_convivem(pg_pool, test_seller, outro_seller):
    """NULL nao colide: a constraint nao pode impedir contas sem ML conectado.

    Se ela impedisse, o segundo cadastro do produto quebraria no signup — e as
    duas fixtures deste teste ja nascem com ml_seller_id nulo.
    """
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        nulos = await conn.fetchval(
            "SELECT count(*) FROM sellers WHERE id = any($1::uuid[]) AND ml_seller_id IS NULL",
            [seller_a, seller_b],
        )
    assert nulos == 2


# ---------- disconnect ----------


async def test_disconnect_apaga_token_e_preserva_dados(client, pg_pool, test_seller):
    """Desconectar para a sincronizacao; nao apaga o historico ja ingerido."""
    user_id, seller_id = test_seller
    state = oauth.emite_state(str(seller_id))
    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps)
        client.get("/ml/callback", params={"code": "TG-c", "state": state}, follow_redirects=False)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount, "
            "marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at) "
            "VALUES (1, $1, now(), 'paid', 100, 0, 0, 1, '{}'::jsonb, now())",
            seller_id,
        )

    resp = client.delete("/ml/connection", headers=_auth(user_id))
    assert resp.status_code == 204
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is None
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", seller_id) == 1
        )


async def test_disconnect_de_outro_seller_nao_afeta_o_meu(
    client, pg_pool, test_seller, outro_seller
):
    user_a, _sa = test_seller
    _ub, seller_b = outro_seller
    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps, ml_user_id=111)
        client.get(
            "/ml/callback",
            params={"code": "TG-c", "state": oauth.emite_state(str(seller_b))},
            follow_redirects=False,
        )
    client.delete("/ml/connection", headers=_auth(user_a))
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_b).load() is not None


# ---------- sync ----------


async def _conectado(pool, seller_id, *, ultimo_sync=None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET ml_seller_id = 987654, ml_nickname = 'LOJA', "
            "last_synced_at = $2 WHERE id = $1",
            seller_id,
            ultimo_sync,
        )
    await PostgresTokenStore(pool, seller_id).save(
        TokenSet(
            access_token="APP_USR-x",
            refresh_token="TG-x",
            expires_at=datetime.now(UTC) + timedelta(hours=5),
        )
    )


async def test_sync_no_login_enfileira_quando_o_dado_esta_velho(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(hours=9))
    resp = client.post("/ml/sync", params={"motivo": "login"}, headers=_auth(user_id))
    assert resp.status_code == 200
    assert resp.json()["enfileirado"] is True


async def test_sync_no_login_nao_enfileira_quando_o_dado_esta_fresco(client, pg_pool, test_seller):
    """A janela de 6h evita queimar rate limit do ML a cada F5 do usuario."""
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(minutes=30))
    resp = client.post("/ml/sync", params={"motivo": "login"}, headers=_auth(user_id))
    assert resp.json() == {"enfileirado": False, "motivo": "recente"}
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sync_jobs") == 0


async def test_sync_no_login_enfileira_se_nunca_sincronizou(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=None)
    corpo = client.post("/ml/sync", params={"motivo": "login"}, headers=_auth(user_id)).json()
    assert corpo["enfileirado"] is True


async def test_sync_manual_ignora_a_janela_de_6h(client, pg_pool, test_seller):
    """O botao e do usuario: se ele pediu, sincroniza."""
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(minutes=2))
    resp = client.post("/ml/sync", params={"motivo": "manual"}, headers=_auth(user_id))
    assert resp.json()["enfileirado"] is True


async def test_sync_sem_conexao_devolve_409(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    resp = client.post("/ml/sync", params={"motivo": "manual"}, headers=_auth(user_id))
    assert resp.status_code == 409


async def test_sync_com_job_em_andamento_nao_duplica(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id)
    await queue.enqueue(pg_pool, seller_id, "backfill")
    resp = client.post("/ml/sync", params={"motivo": "manual"}, headers=_auth(user_id))
    assert resp.json() == {"enfileirado": False, "motivo": "ja-em-andamento"}


async def test_sync_com_motivo_invalido_devolve_400(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id)
    resp = client.post("/ml/sync", params={"motivo": "sei-la"}, headers=_auth(user_id))
    assert resp.status_code == 400


async def test_status_sem_conexao(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    corpo = client.get("/ml/sync/status", headers=_auth(user_id)).json()
    assert corpo["conectado"] is False
    assert corpo["job"] is None


async def test_status_devolve_progresso_do_job(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id)
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.claim_next(pg_pool)
    await queue.heartbeat(pg_pool, job_id, fase="Baixando pedidos", processados=3, total=6)

    corpo = client.get("/ml/sync/status", headers=_auth(user_id)).json()
    assert corpo["conectado"] is True
    assert corpo["apelido"] == "LOJA"
    assert corpo["job"]["status"] == "running"
    assert corpo["job"]["fase"] == "Baixando pedidos"
    assert corpo["job"]["processados"] == 3


async def test_status_nao_mostra_job_de_outro_seller(client, pg_pool, test_seller, outro_seller):
    """Um WHERE esquecido aqui exporia atividade de outro tenant."""
    user_a, _sa = test_seller
    _ub, seller_b = outro_seller
    await queue.enqueue(pg_pool, seller_b, "backfill")
    corpo = client.get("/ml/sync/status", headers=_auth(user_a)).json()
    assert corpo["job"] is None
