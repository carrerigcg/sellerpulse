"""Exclusão de conta a pedido. Decisões em docs/specs/2026-11-03-exclusao-de-conta-design.md."""

from __future__ import annotations

import pytest

from backend.pagamentos.eventos import processa
from backend.scripts.exclui_conta import ExclusaoRecusada, exclui_conta
from backend.tests.test_cobranca import _checkout_pago
from backend.tests.test_corrige_taxas import _insere_legado
from backend.tests.test_ingest_pg import _pedido

EMAIL = "teste@sellerpulse.dev"


@pytest.fixture
async def conta(pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _insere_legado(pg_pool, seller_id, _pedido(1))
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO checkouts (id, seller_id, plano, ciclo) VALUES ('chk', $1, 'essencial', 'mensal')",
            seller_id,
        )
        await conn.execute(
            "INSERT INTO registros_de_acesso (user_id, ip, hora) VALUES ($1, '203.0.113.9', now())",
            user_id,
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        for tabela in ("aceites_de_termos", "checkouts", "contas_excluidas"):
            await conn.execute(f"DELETE FROM {tabela} WHERE seller_id = $1", seller_id)
        await conn.execute("DELETE FROM registros_de_acesso WHERE user_id = $1", user_id)


async def _sobra(conn, seller_id) -> dict[str, int]:
    tabelas = await conn.fetch(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'seller_id'"
    )
    sobra = {}
    for linha in tabelas:
        nome = linha["table_name"]
        total = await conn.fetchval(f"SELECT count(*) FROM {nome} WHERE seller_id = $1", seller_id)
        if total:
            sobra[nome] = total
    return sobra


async def test_apaga_a_loja_e_guarda_a_prova(pg_pool, conta):
    user_id, seller_id = conta
    async with pg_pool.acquire() as conn:
        relatorio = await exclui_conta(conn, EMAIL, aplicar=True)
        assert await conn.fetchval("SELECT count(*) FROM auth.users WHERE id = $1", user_id) == 0
        # Só fica o que a lei manda guardar: a prova, a cobrança e o elo com o usuário.
        assert await _sobra(conn, seller_id) == {
            "aceites_de_termos": 1,
            "checkouts": 1,
            "contas_excluidas": 1,
        }
        assert (
            await conn.fetchval(
                "SELECT user_id FROM contas_excluidas WHERE seller_id = $1", seller_id
            )
            == user_id
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM registros_de_acesso WHERE user_id = $1", user_id
            )
            == 1
        )
    assert relatorio.aplicado
    assert relatorio.apagadas["orders"] == 1
    assert relatorio.preservadas == {
        "aceites_de_termos": 1,
        "checkouts": 1,
        "registros_de_acesso": 1,
    }


async def test_dry_run_nao_apaga_nada(pg_pool, conta):
    user_id, seller_id = conta
    async with pg_pool.acquire() as conn:
        relatorio = await exclui_conta(conn, EMAIL, aplicar=False)
        assert await conn.fetchval("SELECT count(*) FROM sellers WHERE id = $1", seller_id) == 1
        assert await conn.fetchval("SELECT count(*) FROM contas_excluidas") == 0
    assert not relatorio.aplicado
    assert relatorio.apagadas["orders"] == 1


async def test_recusa_quem_ainda_paga_assinatura(pg_pool, conta):
    _, seller_id = conta
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET asaas_assinatura = 'sub_1' WHERE seller_id = $1", seller_id
        )
        with pytest.raises(ExclusaoRecusada, match="cancele"):
            await exclui_conta(conn, EMAIL, aplicar=True)
        assert await conn.fetchval("SELECT count(*) FROM sellers WHERE id = $1", seller_id) == 1


async def test_assinatura_cancelada_nao_impede(pg_pool, conta):
    _, seller_id = conta
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET asaas_assinatura = 'sub_1', cancelada_em = now() "
            "WHERE seller_id = $1",
            seller_id,
        )
        assert (await exclui_conta(conn, EMAIL, aplicar=True)).aplicado


async def test_recusa_a_demonstracao(pg_pool, conta):
    _, seller_id = conta
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET is_demo = true WHERE id = $1", seller_id)
        with pytest.raises(ExclusaoRecusada, match="demonstração"):
            await exclui_conta(conn, EMAIL, aplicar=True)


async def test_checkout_pago_depois_da_exclusao_nao_quebra_o_aviso(pg_pool, conta):
    async with pg_pool.acquire() as conn:
        await exclui_conta(conn, EMAIL, aplicar=True)
    resultado = await processa(pg_pool, _checkout_pago(evento_id="evt_excl", checkout_id="chk"))
    assert resultado == "conta-excluida"
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM eventos_do_gateway WHERE id = 'evt_excl'")


async def test_email_desconhecido(pg_pool):
    async with pg_pool.acquire() as conn:
        with pytest.raises(ExclusaoRecusada, match="nenhuma conta"):
            await exclui_conta(conn, "ninguem@exemplo.com", aplicar=True)
