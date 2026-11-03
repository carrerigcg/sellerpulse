"""Prazos de guarda da Política. Decisões em
docs/specs/2026-11-03-retencao-automatica-design.md."""

from __future__ import annotations

import uuid

import pytest

from backend import retencao
from backend.tests.test_corrige_taxas import _insere_legado
from backend.tests.test_ingest_pg import _pedido


async def _fim_do_plano(pool, seller_id, intervalo: str | None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET origem = 'gateway', acesso_ate = "
            + ("NULL" if intervalo is None else f"now() - interval '{intervalo}'")
            + " WHERE seller_id = $1",
            seller_id,
        )


async def _com_token_e_pedido(pool, seller_id) -> None:
    await _insere_legado(pool, seller_id, _pedido(1))
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO oauth_tokens (seller_id, access_token_enc, refresh_token_enc, expires_at) "
            "VALUES ($1, 'a', 'r', now())",
            seller_id,
        )
        await conn.execute("UPDATE sellers SET last_synced_at = now() WHERE id = $1", seller_id)


async def _conta(pool, tabela, seller_id) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(f"SELECT count(*) FROM {tabela} WHERE seller_id = $1", seller_id)


async def test_toda_tabela_de_vendedor_tem_destino_decidido(pg_pool):
    async with pg_pool.acquire() as conn:
        tabelas = {
            r["table_name"]
            for r in await conn.fetch(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'seller_id'"
            )
        }
    tabelas.add("sellers")
    assert tabelas == set(retencao.DADOS_DA_LOJA) | set(retencao.FICAM)


@pytest.mark.parametrize(
    ("fim", "token", "pedidos"),
    [
        ("29 days", 1, 1),
        ("31 days", 0, 1),
        ("11 months 28 days", 0, 1),
        ("13 months", 0, 0),
        (None, 1, 1),
    ],
)
async def test_prazos_contam_do_fim_do_plano(pg_pool, test_seller, fim, token, pedidos):
    _, seller_id = test_seller
    await _com_token_e_pedido(pg_pool, seller_id)
    await _fim_do_plano(pg_pool, seller_id, fim)
    await retencao.aplica_retencao(pg_pool)
    assert await _conta(pg_pool, "oauth_tokens", seller_id) == token
    assert await _conta(pg_pool, "orders", seller_id) == pedidos
    # A conta e a prova ficam sempre.
    assert await _conta(pg_pool, "assinaturas", seller_id) == 1
    assert await _conta(pg_pool, "aceites_de_termos", seller_id) == 1


async def test_sem_a_credencial_a_tela_volta_a_oferecer_a_conexao(pg_pool, test_seller):
    _, seller_id = test_seller
    await _com_token_e_pedido(pg_pool, seller_id)
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET ml_seller_id = 987 WHERE id = $1", seller_id)
    await _fim_do_plano(pg_pool, seller_id, "31 days")
    await retencao.aplica_retencao(pg_pool)
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT ml_seller_id FROM sellers WHERE id = $1", seller_id) is None
        )


async def test_sem_os_dados_a_volta_traz_a_ingestao_inicial(pg_pool, test_seller):
    _, seller_id = test_seller
    await _com_token_e_pedido(pg_pool, seller_id)
    await _fim_do_plano(pg_pool, seller_id, "13 months")
    await retencao.aplica_retencao(pg_pool)
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT last_synced_at FROM sellers WHERE id = $1", seller_id)
            is None
        )


async def test_a_demonstracao_nunca_vence(pg_pool, test_seller):
    _, seller_id = test_seller
    await _com_token_e_pedido(pg_pool, seller_id)
    await _fim_do_plano(pg_pool, seller_id, "13 months")
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET is_demo = true WHERE id = $1", seller_id)
    await retencao.aplica_retencao(pg_pool)
    assert await _conta(pg_pool, "orders", seller_id) == 1


async def test_nao_toca_em_outro_vendedor(pg_pool, test_seller, outro_seller):
    _, vencido = test_seller
    _, ativo = outro_seller
    for seller_id in (vencido, ativo):
        await _com_token_e_pedido(pg_pool, seller_id)
    await _fim_do_plano(pg_pool, vencido, "13 months")
    await retencao.aplica_retencao(pg_pool)
    assert await _conta(pg_pool, "orders", vencido) == 0
    assert await _conta(pg_pool, "orders", ativo) == 1


async def test_registro_de_acesso_e_prova_prescritos(pg_pool):
    user_id, velho, recente = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO registros_de_acesso (user_id, ip, hora) VALUES "
            "($1, 'velho', now() - interval '6 months 2 hours'), "
            "($1, 'quase', now() - interval '5 months 28 days')",
            user_id,
        )
        for seller_id, quando in ((velho, "5 years 1 day"), (recente, "4 years 11 months")):
            await conn.execute(
                "INSERT INTO contas_excluidas (seller_id, user_id, excluida_em) "
                f"VALUES ($1, $2, now() - interval '{quando}')",
                seller_id,
                user_id,
            )
            await conn.execute(
                "INSERT INTO aceites_de_termos (seller_id, versao) VALUES ($1, 'v')", seller_id
            )
            await conn.execute(
                "INSERT INTO checkouts (id, seller_id, plano, ciclo) "
                "VALUES ($1, $2, 'essencial', 'mensal')",
                f"chk_{seller_id}",
                seller_id,
            )
        try:
            saiu = await retencao.aplica_retencao(pg_pool)
            ips = [
                r["ip"]
                for r in await conn.fetch(
                    "SELECT ip FROM registros_de_acesso WHERE user_id = $1", user_id
                )
            ]
            restam = {
                r["seller_id"]
                for r in await conn.fetch(
                    "SELECT seller_id FROM aceites_de_termos WHERE seller_id = ANY($1::uuid[])",
                    [velho, recente],
                )
            }
            checkouts = {
                r["seller_id"]
                for r in await conn.fetch(
                    "SELECT seller_id FROM checkouts WHERE seller_id = ANY($1::uuid[])",
                    [velho, recente],
                )
            }
        finally:
            await conn.execute("DELETE FROM registros_de_acesso WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM contas_excluidas WHERE user_id = $1", user_id)
            for tabela in ("aceites_de_termos", "checkouts"):
                await conn.execute(
                    f"DELETE FROM {tabela} WHERE seller_id = ANY($1::uuid[])", [velho, recente]
                )
    # O Marco Civil pede ao menos 6 meses: o quase vencido fica.
    assert ips == ["quase"]
    assert restam == {recente}
    assert checkouts == {recente}
    assert saiu["contas_excluidas"] == 1


def test_e_opt_in(monkeypatch):
    monkeypatch.delenv("RETENCAO_IN_PROCESS", raising=False)
    assert not retencao.retencao_habilitada()
    monkeypatch.setenv("RETENCAO_IN_PROCESS", "1")
    assert retencao.retencao_habilitada()


async def test_eventos_do_asaas_saem_depois_de_5_anos(pg_pool):
    # A Política guarda "os registros da cobrança" por 5 anos; o evento não tem
    # vendedor, então o prazo conta do recebimento.
    async with pg_pool.acquire() as conn:
        for evento, quando in (("evt_velho", "5 years 1 day"), ("evt_quase", "4 years 11 months")):
            await conn.execute(
                "INSERT INTO eventos_do_gateway (id, tipo, payload, recebido_em) "
                f"VALUES ($1, 'PAYMENT_RECEIVED', '{{}}'::jsonb, now() - interval '{quando}')",
                evento,
            )
        try:
            saiu = await retencao.aplica_retencao(pg_pool)
            restam = [
                r["id"]
                for r in await conn.fetch(
                    "SELECT id FROM eventos_do_gateway WHERE id = ANY($1::text[])",
                    ["evt_velho", "evt_quase"],
                )
            ]
        finally:
            await conn.execute(
                "DELETE FROM eventos_do_gateway WHERE id = ANY($1::text[])",
                ["evt_velho", "evt_quase"],
            )
    assert restam == ["evt_quase"]
    assert saiu["eventos_do_gateway"] == 1
