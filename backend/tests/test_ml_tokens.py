"""Testes da cifra e da persistencia dos tokens do Mercado Livre."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from backend.ml import tokens as mod
from src.auth import TokenSet


@pytest.fixture(autouse=True)
def chave_de_teste(monkeypatch):
    """Chave Fernet fixa por teste.

    `_fernet()` e cacheado com lru_cache pra nao reconstruir o objeto a cada
    chamada — o cache_clear aqui e obrigatorio, senao o primeiro teste que
    rodar fixa a chave para todos os seguintes.
    """
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    mod._fernet.cache_clear()
    yield
    mod._fernet.cache_clear()


def test_round_trip_preserva_o_valor():
    assert mod.decifra(mod.cifra("APP_USR-123-abc")) == "APP_USR-123-abc"


def test_ciphertext_nao_contem_o_valor_em_claro():
    cifrado = mod.cifra("APP_USR-123-abc")
    assert "APP_USR" not in cifrado


def test_ciphertext_adulterado_levanta():
    """Adulteracao tem que estourar, nao devolver lixo silenciosamente.

    Fernet autentica com HMAC, entao um byte trocado invalida. Se este teste
    falhar, a cifra nao esta verificando integridade e um token corrompido
    entraria como string invalida na chamada ao ML, produzindo um 401 confuso
    em vez de um erro claro.
    """
    cifrado = mod.cifra("APP_USR-123-abc")
    adulterado = cifrado[:-4] + ("aaaa" if not cifrado.endswith("aaaa") else "bbbb")
    with pytest.raises(mod.TokenCifraError):
        mod.decifra(adulterado)


def test_chave_diferente_nao_decifra(monkeypatch):
    cifrado = mod.cifra("APP_USR-123-abc")
    mod._fernet.cache_clear()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(mod.TokenCifraError):
        mod.decifra(cifrado)


def _token_set(minutos=60) -> TokenSet:
    return TokenSet(
        access_token="APP_USR-acesso",
        refresh_token="TG-refresh",
        expires_at=datetime.now(UTC) + timedelta(minutes=minutos),
    )


async def test_store_salva_e_carrega(pg_pool, test_seller):
    _user_id, seller_id = test_seller
    store = mod.PostgresTokenStore(pg_pool, seller_id)

    original = _token_set()
    await store.save(original)
    carregado = await store.load()

    assert carregado is not None
    assert carregado.access_token == original.access_token
    assert carregado.refresh_token == original.refresh_token
    # asyncpg devolve timestamptz sempre aware. Assertar explicitamente pra que,
    # se algum dia voltar naive, o teste falhe dizendo isso em vez de estourar
    # um TypeError obscuro na subtracao abaixo.
    assert carregado.expires_at.tzinfo is not None
    # timestamptz volta com precisao de microssegundo; comparar com tolerancia
    assert abs((carregado.expires_at - original.expires_at).total_seconds()) < 1


async def test_store_grava_cifrado_no_banco(pg_pool, test_seller):
    """O que esta NA COLUNA nao pode ser o token em claro.

    Sem este teste, uma implementacao que esquecesse de chamar cifra() passaria
    em todos os outros — porque load() faria o round-trip do jeito errado dos
    dois lados e ninguem notaria.
    """
    _user_id, seller_id = test_seller
    store = mod.PostgresTokenStore(pg_pool, seller_id)
    await store.save(_token_set())

    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT access_token_enc, refresh_token_enc, key_version "
            "FROM oauth_tokens WHERE seller_id = $1",
            seller_id,
        )
    assert "APP_USR" not in row["access_token_enc"]
    assert "TG-" not in row["refresh_token_enc"]
    assert row["key_version"] == mod.KEY_VERSION_ATUAL


async def test_store_load_sem_conexao_devolve_none(pg_pool, test_seller):
    _user_id, seller_id = test_seller
    assert await mod.PostgresTokenStore(pg_pool, seller_id).load() is None


async def test_store_save_e_idempotente(pg_pool, test_seller):
    """Segundo save no mesmo seller atualiza, nao estoura por PK duplicada."""
    _user_id, seller_id = test_seller
    store = mod.PostgresTokenStore(pg_pool, seller_id)
    await store.save(_token_set())
    await store.save(
        TokenSet(
            access_token="APP_USR-novo",
            refresh_token="TG-novo",
            expires_at=datetime.now(UTC) + timedelta(minutes=90),
        )
    )
    carregado = await store.load()
    assert carregado.access_token == "APP_USR-novo"


async def test_store_delete_remove(pg_pool, test_seller):
    _user_id, seller_id = test_seller
    store = mod.PostgresTokenStore(pg_pool, seller_id)
    await store.save(_token_set())
    await store.delete()
    assert await store.load() is None


def test_valida_chave_de_cifra_aceita_chave_boa():
    mod.valida_chave_de_cifra()  # a fixture autouse ja pos uma chave valida


def test_valida_chave_de_cifra_recusa_chave_ausente(monkeypatch):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    mod._fernet.cache_clear()
    with pytest.raises(RuntimeError, match="nao definida"):
        mod.valida_chave_de_cifra()


def test_valida_chave_de_cifra_recusa_chave_malformada(monkeypatch):
    """Chave truncada e o caso realista: alguem colou metade do valor no Render."""
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "chave-que-nao-e-fernet")
    mod._fernet.cache_clear()
    with pytest.raises(RuntimeError, match="invalida"):
        mod.valida_chave_de_cifra()


async def test_store_e_isolado_entre_sellers(pg_pool, test_seller, outro_seller):
    """Token do seller A nunca aparece pro seller B.

    Um `WHERE seller_id = $1` esquecido em load() faria o store devolver o
    token de outro tenant — permitindo ingerir a loja de terceiro.
    """
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    await mod.PostgresTokenStore(pg_pool, seller_a).save(_token_set())
    assert await mod.PostgresTokenStore(pg_pool, seller_b).load() is None
