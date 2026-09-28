"""Testes da cifra e da persistencia dos tokens do Mercado Livre."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from backend.ml import tokens as mod


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


def test_chave_diferente_nao_decifra():
    cifrado = mod.cifra("APP_USR-123-abc")
    mod._fernet.cache_clear()
    import os

    os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    with pytest.raises(mod.TokenCifraError):
        mod.decifra(cifrado)
