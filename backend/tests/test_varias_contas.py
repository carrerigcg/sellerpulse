"""Premium: até 3 contas do Mercado Livre num login só.

Spec: docs/specs/2026-11-06-premium-varias-contas-design.md
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import responses as responses_lib

from backend import retencao
from backend.ml import oauth
from backend.planos import plano_vigente
from backend.scripts.exclui_conta import exclui_conta

from .conftest import da_plano
from .test_routers import _order
from .test_routers_ml import SEGREDO, _auth, _cabecalho, _conectado, _mock_ml_conexao
from .test_routers_ml import client as _client

client = _client

EMAIL = "teste@sellerpulse.dev"


async def _extra(pool, user_id, *, ml_seller_id=None, apelido="LOJA_2") -> uuid.UUID:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO sellers (user_id, principal, ml_seller_id, ml_nickname) "
            "VALUES ($1, false, $2, $3) RETURNING id",
            user_id,
            ml_seller_id,
            apelido,
        )


def _conta(conta_id) -> dict[str, str]:
    return {"X-Conta": str(conta_id)}


def _fluxo(client, user_id, conta_id=None):
    headers = _auth(user_id) | (_conta(conta_id) if conta_id else {})
    return client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=headers,
    )


# ---------- banco ----------


async def test_um_usuario_tem_uma_principal_so(pg_pool, test_seller):
    user_id, _sid = test_seller
    async with pg_pool.acquire() as conn:
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await conn.execute("INSERT INTO sellers (user_id) VALUES ($1)", user_id)


# ---------- conta aberta ----------


async def test_sem_cabecalho_abre_a_principal(client, pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0)
    await _order(pg_pool, extra, 2, "2026-07-25T10:00:00+00:00", 700.0)

    resp = _fluxo(client, user_id)

    assert resp.status_code == 200
    assert resp.json()[0]["receita_bruta"] == pytest.approx(100.0)


async def test_cabecalho_abre_a_conta_extra(client, pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0)
    await _order(pg_pool, extra, 2, "2026-07-25T10:00:00+00:00", 700.0)

    resp = _fluxo(client, user_id, extra)

    assert resp.status_code == 200
    assert resp.json()[0]["receita_bruta"] == pytest.approx(700.0)


async def test_conta_de_outro_usuario_e_recusada(client, pg_pool, test_seller, outro_seller):
    """Nunca a principal no lugar: o número de uma conta sairia com o nome de outra."""
    user_id, _sid = test_seller
    _outro, alheia = outro_seller
    await _order(pg_pool, alheia, 1, "2026-07-25T10:00:00+00:00", 999.0)

    resp = _fluxo(client, user_id, alheia)

    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "conta-invalida"


async def test_cabecalho_que_nao_e_id_e_recusado(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    resp = _fluxo(client, user_id, "nao-e-uuid")
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "conta-invalida"


async def test_fora_do_premium_a_conta_extra_nao_abre(client, pg_pool, test_seller):
    """Decisão 2.1: os dados ficam, mas a conta extra some até o Premium voltar."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")

    assert _fluxo(client, user_id, extra).status_code == 403
    assert _fluxo(client, user_id).status_code == 200
    # O `/acesso` também recusa: é por ele que o front descobre e apaga a escolha.
    resp = client.get("/conta/acesso", headers=_auth(user_id) | _conta(extra))
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "conta-invalida"


async def test_conta_extra_usa_o_plano_e_o_aceite_da_principal(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    extra = await _extra(pg_pool, user_id)

    resp = client.get("/conta/acesso", headers=_auth(user_id) | _conta(extra))

    corpo = resp.json()
    assert corpo["plano"] == "premium"
    assert corpo["termos"]["aceito"] is True
    assert corpo["conta_aberta"] == str(extra)


async def test_acesso_lista_as_contas_e_quais_abrem(client, pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id, ml_seller_id=77002, apelido="SEGUNDA")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET ml_seller_id = 77001, ml_nickname = 'PRIMEIRA' WHERE id = $1", sid
        )

    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert corpo["conta_aberta"] == str(sid)
    assert corpo["max_contas"] == 3
    chaves = ("id", "apelido", "principal", "ativa")
    assert [{k: c[k] for k in chaves} for c in corpo["contas"]] == [
        {"id": str(sid), "apelido": "PRIMEIRA", "principal": True, "ativa": True},
        {"id": str(extra), "apelido": "SEGUNDA", "principal": False, "ativa": True},
    ]

    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert [c["ativa"] for c in corpo["contas"]] == [True, False]


async def test_conta_desconectada_aparece_sem_o_nome_da_loja(client, pg_pool, test_seller):
    """Desconectar zera o `ml_seller_id` e guarda o apelido. Com o nome da loja,
    o seletor mostrava como aberta uma conta que não sincroniza mais."""
    user_id, _sid = test_seller
    extra = await _extra(pg_pool, user_id, ml_seller_id=None, apelido="LOJA_ANTIGA")
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert next(c for c in corpo["contas"] if c["id"] == str(extra))["apelido"] is None


async def test_acesso_diz_quando_cada_conta_sincronizou(client, pg_pool, test_seller):
    """Na soma, uma conta parada ou ainda importando entra com dias a menos,
    e a tela precisa saber para avisar: ausência não pode virar queda."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id, ml_seller_id=77003, apelido="NOVA")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET last_synced_at = '2026-11-08 12:00+00' WHERE id = $1", sid
        )
        await conn.execute(
            "INSERT INTO sync_jobs (seller_id, kind, status, finished_at) "
            "VALUES ($1, 'backfill', 'done', now())",
            sid,
        )
        # Backfill que falhou não completa a importação.
        await conn.execute(
            "INSERT INTO sync_jobs (seller_id, kind, status, finished_at) "
            "VALUES ($1, 'backfill', 'failed', now())",
            extra,
        )
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    por_id = {c["id"]: c for c in corpo["contas"]}
    assert por_id[str(sid)]["sincronizada_em"].startswith("2026-11-08T12:00")
    assert por_id[str(sid)]["importacao_completa"] is True
    assert por_id[str(extra)]["sincronizada_em"] is None
    assert por_id[str(extra)]["importacao_completa"] is False


# ---------- adicionar conta ----------


async def test_adicionar_conta_exige_premium(client, pg_pool, test_seller):
    user_id, sid = test_seller
    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")
    resp = client.post("/ml/contas/nova", headers=_auth(user_id))
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "fora-do-plano"


async def test_adicionar_conta_recusa_quem_ja_tem_tres(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    await _extra(pg_pool, user_id)
    await _extra(pg_pool, user_id)
    resp = client.post("/ml/contas/nova", headers=_auth(user_id))
    assert resp.status_code == 409
    assert resp.json()["detail"]["codigo"] == "limite-de-contas"


async def test_callback_de_conta_nova_cria_a_conta_extra(client, pg_pool, test_seller):
    user_id, sid = test_seller
    state = oauth.emite_state(f"nova:{sid}")

    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps, ml_user_id=555, nickname="LOJA_NOVA")
        resp = client.get(
            "/ml/callback", params={"code": "c", "state": state}, follow_redirects=False
        )

    assert resp.headers["location"].endswith("/dashboard/conectar?conectado=1")
    async with pg_pool.acquire() as conn:
        nova = await conn.fetchrow(
            "SELECT id, principal, ml_nickname FROM sellers WHERE ml_seller_id = 555"
        )
        job = await conn.fetchval("SELECT kind FROM sync_jobs WHERE seller_id = $1", nova["id"])
        principal = await conn.fetchval("SELECT ml_seller_id FROM sellers WHERE id = $1", sid)
    assert nova["principal"] is False
    assert nova["ml_nickname"] == "LOJA_NOVA"
    assert job == "backfill"
    # A principal não foi tocada: conectar uma conta nova não troca a dela.
    assert principal is None


async def test_callback_de_conta_nova_respeita_o_limite(client, pg_pool, test_seller):
    """O limite vale também no callback: dois consentimentos abertos não passam de 3."""
    user_id, sid = test_seller
    state = oauth.emite_state(f"nova:{sid}")
    await _extra(pg_pool, user_id)
    await _extra(pg_pool, user_id)

    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps, ml_user_id=556)
        resp = client.get(
            "/ml/callback", params={"code": "c", "state": state}, follow_redirects=False
        )

    assert resp.headers["location"].endswith("/dashboard/conectar?erro=limite-de-contas")
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sellers WHERE user_id = $1", user_id) == 3


async def test_callback_de_conta_nova_recusa_conta_ja_conectada(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _conectado(pg_pool, sid, ml_seller_id=777)
    state = oauth.emite_state(f"nova:{sid}")

    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps, ml_user_id=777)
        resp = client.get(
            "/ml/callback", params={"code": "c", "state": state}, follow_redirects=False
        )

    assert resp.headers["location"].endswith("/dashboard/conectar?erro=ja-conectada")
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sellers WHERE user_id = $1", user_id) == 1


async def test_reconectar_conta_extra_usa_o_plano_da_principal(client, pg_pool, test_seller):
    """A extra não tem assinatura própria: lida pela própria linha, pareceria sem plano."""
    user_id, _sid = test_seller
    extra = await _extra(pg_pool, user_id)
    state = oauth.emite_state(str(extra))

    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps, ml_user_id=888)
        resp = client.get(
            "/ml/callback", params={"code": "c", "state": state}, follow_redirects=False
        )

    assert resp.headers["location"].endswith("/dashboard/conectar?conectado=1")
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT ml_seller_id FROM sellers WHERE id = $1", extra) == 888


# ---------- desconectar e remover ----------


async def test_desconectar_com_a_extra_aberta_desconecta_so_ela(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _conectado(pg_pool, sid, ml_seller_id=101)
    extra = await _extra(pg_pool, user_id, ml_seller_id=202)

    resp = client.delete("/ml/connection", headers=_auth(user_id) | _conta(extra))

    assert resp.status_code == 204
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT ml_seller_id FROM sellers WHERE id = $1", sid) == 101
        assert await conn.fetchval("SELECT ml_seller_id FROM sellers WHERE id = $1", extra) is None


async def test_status_segue_a_conta_aberta(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _conectado(pg_pool, sid, ml_seller_id=101)
    extra = await _extra(pg_pool, user_id, ml_seller_id=202, apelido="LOJA_2")

    corpo = client.get("/ml/sync/status", headers=_auth(user_id) | _conta(extra)).json()
    assert corpo["apelido"] == "LOJA_2"


async def test_remover_conta_extra_apaga_ela_e_os_dados(client, pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, extra, 1, "2026-07-25T10:00:00+00:00", 100.0)
    await _order(pg_pool, sid, 2, "2026-07-25T10:00:00+00:00", 100.0)

    resp = client.delete(f"/ml/contas/{extra}", headers=_auth(user_id))

    assert resp.status_code == 204
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sellers WHERE id = $1", extra) == 0
        assert await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", extra) == 0
        assert await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", sid) == 1


async def test_remover_vale_fora_do_premium(client, pg_pool, test_seller):
    """Quem saiu do Premium precisa poder apagar a conta que não abre mais."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")
    assert client.delete(f"/ml/contas/{extra}", headers=_auth(user_id)).status_code == 204


async def test_a_principal_nao_se_remove(client, pg_pool, test_seller):
    user_id, sid = test_seller
    resp = client.delete(f"/ml/contas/{sid}", headers=_auth(user_id))
    assert resp.status_code == 409
    assert resp.json()["detail"]["codigo"] == "conta-principal"


async def test_nao_remove_conta_de_outro_usuario(client, pg_pool, test_seller, outro_seller):
    user_id, _sid = test_seller
    outro_user, _alheia = outro_seller
    extra_alheia = await _extra(pg_pool, outro_user)
    resp = client.delete(f"/ml/contas/{extra_alheia}", headers=_auth(user_id))
    assert resp.status_code == 404
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sellers WHERE id = $1", extra_alheia) == 1


# ---------- agendador, worker, retenção e exclusão ----------


async def test_sync_todos_inclui_a_extra_so_no_premium(
    client, monkeypatch, pg_pool, test_seller, qualquer_hora_e_manha
):
    monkeypatch.setenv("SYNC_SECRET", SEGREDO)
    user_id, sid = test_seller
    velho = datetime.now(UTC) - timedelta(days=2)
    await _conectado(pg_pool, sid, ultimo_sync=velho, ml_seller_id=101)
    extra = await _extra(pg_pool, user_id, ml_seller_id=202)
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET last_synced_at = $2 WHERE id = $1", extra, velho)

    client.post("/ml/sync-todos", headers=_cabecalho())
    async with pg_pool.acquire() as conn:
        alvos = {r["seller_id"] for r in await conn.fetch("SELECT seller_id FROM sync_jobs")}
        assert alvos == {sid, extra}
        await conn.execute("DELETE FROM sync_jobs")
        await da_plano(conn, sid, "exclusive")

    client.post("/ml/sync-todos", headers=_cabecalho())
    async with pg_pool.acquire() as conn:
        alvos = {r["seller_id"] for r in await conn.fetch("SELECT seller_id FROM sync_jobs")}
    assert alvos == {sid}


async def test_plano_do_worker_para_a_extra_vem_da_principal(pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    assert (await plano_vigente(pg_pool, extra)).nome == "premium"

    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")
    assert (await plano_vigente(pg_pool, sid)).nome == "exclusive"
    assert await plano_vigente(pg_pool, extra) is None


async def test_retencao_da_extra_segue_a_assinatura_da_principal(pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, extra, 1, "2026-07-25T10:00:00+00:00", 100.0)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET origem = 'gateway', "
            "acesso_ate = now() - interval '13 months' WHERE seller_id = $1",
            sid,
        )

    await retencao.aplica_retencao(pg_pool)

    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", extra) == 0


async def test_exclusao_leva_todas_as_contas(pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, extra, 1, "2026-07-25T10:00:00+00:00", 100.0)
    async with pg_pool.acquire() as conn:
        relatorio = await exclui_conta(conn, EMAIL, aplicar=True)
        excluidas = {
            r["seller_id"]
            for r in await conn.fetch(
                "SELECT seller_id FROM contas_excluidas WHERE user_id = $1", user_id
            )
        }
        await conn.execute("DELETE FROM contas_excluidas WHERE user_id = $1", user_id)
        await conn.execute(
            "DELETE FROM aceites_de_termos WHERE seller_id NOT IN (SELECT id FROM sellers)"
        )
    assert relatorio.apagadas["orders"] == 1
    assert excluidas == {sid, extra}
