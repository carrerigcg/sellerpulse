"""Testes do fluxo OAuth do Mercado Livre no contexto multi-tenant."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import requests
import responses as responses_lib
from cryptography.fernet import Fernet

from backend.ml import oauth
from backend.ml import tokens as tokens_mod
from src.auth import TokenSet
from src.session_auth import OAuthError


@pytest.fixture(autouse=True)
def segredos(monkeypatch):
    monkeypatch.setenv("STATE_SECRET", "segredo-de-teste-do-state")
    monkeypatch.setenv("ML_CLIENT_ID", "1234567890")
    monkeypatch.setenv("ML_CLIENT_SECRET", "secret-do-app-ml")
    monkeypatch.setenv("ML_REDIRECT_URI", "https://api.exemplo.dev/ml/callback")


def test_state_round_trip():
    seller_id = str(uuid.uuid4())
    assert oauth.valida_state(oauth.emite_state(seller_id)) == seller_id


def test_state_expirado_e_recusado():
    """Usuario que deixou a aba do ML aberta meia hora nao consegue conectar.

    Sem expiracao, um `state` capturado de um log ou do historico do browser
    valeria para sempre.
    """
    seller_id = str(uuid.uuid4())
    passado = datetime.now(UTC) - timedelta(minutes=30)
    state = oauth.emite_state(seller_id, agora=passado)
    with pytest.raises(oauth.StateInvalido):
        oauth.valida_state(state)


def test_state_com_assinatura_de_outro_segredo_e_recusado():
    """O cenario do link forjado.

    Sem validar assinatura, um atacante montaria um callback apontando pro
    seller_id da vitima e plugaria a conta ML DELE no dashboard DELA.
    """
    forjado = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": oauth.AUDIENCIA_STATE,
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        "segredo-do-atacante",
        algorithm="HS256",
    )
    with pytest.raises(oauth.StateInvalido):
        oauth.valida_state(forjado)


def test_state_com_audience_errada_e_recusado():
    """Um JWT valido de OUTRO proposito nao serve como state.

    Sem checar `aud`, qualquer token assinado com o mesmo segredo — inclusive
    um emitido para outra finalidade no futuro — seria aceito aqui.
    """
    outro = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "outra-coisa",
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        os.environ["STATE_SECRET"],
        algorithm="HS256",
    )
    with pytest.raises(oauth.StateInvalido):
        oauth.valida_state(outro)


@pytest.mark.parametrize("valor", ["", "nao-e-um-jwt", "a.b.c"])
def test_state_vazio_ou_lixo_e_recusado(valor):
    with pytest.raises(oauth.StateInvalido):
        oauth.valida_state(valor)


def test_url_de_consentimento_carrega_o_state_e_o_client_id():
    seller_id = str(uuid.uuid4())
    url, state = oauth.url_de_consentimento(seller_id)
    assert url.startswith("https://auth.mercadolivre.com.br/authorization?")
    assert "client_id=1234567890" in url
    assert f"state={state}" in url
    # O secret NUNCA pode aparecer numa URL que vai pro browser.
    assert "secret-do-app-ml" not in url


@pytest.fixture(autouse=True)
def chave_de_cifra(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    tokens_mod._fernet.cache_clear()
    yield
    tokens_mod._fernet.cache_clear()


async def _grava_token(pool, seller_id, *, minutos: int) -> None:
    """Grava um TokenSet que expira em `minutos` (negativo = ja expirado).

    Atencao a margem: TokenSet.is_expired() considera expirado com 10 minutos
    de antecedencia, entao `minutos` precisa ser bem acima disso pra contar
    como valido.
    """
    await tokens_mod.PostgresTokenStore(pool, seller_id).save(
        TokenSet(
            access_token="APP_USR-velho",
            refresh_token="TG-velho",
            expires_at=datetime.now(UTC) + timedelta(minutes=minutos),
        )
    )


async def test_token_valido_nao_dispara_refresh(pg_pool, test_seller, monkeypatch):
    """Token que ainda vale e devolvido sem tocar na rede."""
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=120)

    def _nao_deveria_chamar(_refresh_token):
        raise AssertionError("renovou um token que ainda estava valido")

    monkeypatch.setattr(oauth, "_refresh_http", _nao_deveria_chamar)
    assert await oauth.garante_token_valido(pg_pool, seller_id) == "APP_USR-velho"


async def test_sem_conexao_levanta(pg_pool, test_seller):
    _u, seller_id = test_seller
    with pytest.raises(oauth.SemConexaoML):
        await oauth.garante_token_valido(pg_pool, seller_id)


async def test_token_expirado_e_renovado_e_persistido(pg_pool, test_seller):
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.POST,
            "https://api.mercadolibre.com/oauth/token",
            json={
                "access_token": "APP_USR-novo",
                "refresh_token": "TG-novo",
                "expires_in": 21600,
            },
        )
        novo = await oauth.garante_token_valido(pg_pool, seller_id)

    assert novo == "APP_USR-novo"
    # Persistiu: a proxima chamada nao precisa renovar de novo.
    guardado = await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load()
    assert guardado.access_token == "APP_USR-novo"
    assert guardado.refresh_token == "TG-novo"


async def test_refresh_concorrente_dispara_uma_unica_chamada(
    pg_pool_concorrente, test_seller, monkeypatch
):
    """Duas corrotinas renovando juntas => UMA chamada ao ML.

    Este e o teste que prova o `FOR UPDATE`. Sem o lock, as duas leem o mesmo
    refresh_token velho, as duas chamam o ML, e a segunda resposta invalida a
    primeira — o usuario e desconectado sozinho, num bug que so aparece sob
    concorrencia e e quase impossivel de reproduzir na mao.

    Usa `pg_pool_concorrente` (nao `pg_pool`): com `min_size=1`, a segunda
    corrotina gastaria tempo abrindo conexao nova e chegaria depois que a
    primeira ja tivesse commitado — o teste passaria mesmo sem o lock. Ver
    docstring do fixture.
    """
    _u, seller_id = test_seller
    await _grava_token(pg_pool_concorrente, seller_id, minutos=-5)

    chamadas: list[str] = []

    def _fake_refresh(refresh_token: str) -> TokenSet:
        chamadas.append(refresh_token)
        return TokenSet(
            access_token=f"APP_USR-{len(chamadas)}",
            refresh_token=f"TG-{len(chamadas)}",
            expires_at=datetime.now(UTC) + timedelta(hours=6),
        )

    monkeypatch.setattr(oauth, "_refresh_http", _fake_refresh)

    resultados = await asyncio.gather(
        oauth.garante_token_valido(pg_pool_concorrente, seller_id),
        oauth.garante_token_valido(pg_pool_concorrente, seller_id),
    )

    assert len(chamadas) == 1, f"renovou {len(chamadas)}x — o lock nao funcionou"
    # As duas chamadas terminam com um token valido (o mesmo).
    assert resultados[0] == resultados[1] == "APP_USR-1"


async def test_invalid_grant_apaga_a_conexao(pg_pool, test_seller):
    """Usuario revogou o acesso no ML: nao insiste, apaga e pede reconexao.

    Insistir em retry com um refresh_token morto so gasta rate limit e deixa o
    usuario vendo erro generico pra sempre.
    """
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.POST,
            "https://api.mercadolibre.com/oauth/token",
            status=400,
            json={"error": "invalid_grant", "message": "invalid_grant"},
        )
        with pytest.raises(oauth.ConexaoMLRevogada):
            await oauth.garante_token_valido(pg_pool, seller_id)

    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is None


async def test_falha_generica_nao_apaga_token_nem_trava_o_lock(pg_pool, test_seller, monkeypatch):
    """Erro que NAO e revogacao: token fica, lock e liberado, conexao volta.

    O bug do DELETE-dentro-da-transacao foi pego por teste, nao por leitura.
    Mesma disciplina aqui: se um OAuthError deixasse o lock preso ou a conexao
    fora do pool, a SEGUNDA chamada abaixo travaria ou estouraria.
    """
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    def _falha(_refresh_token):
        raise OAuthError("500 do lado do ML")

    monkeypatch.setattr(oauth, "_refresh_http", _falha)
    with pytest.raises(OAuthError):
        await oauth.garante_token_valido(pg_pool, seller_id)

    guardado = await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load()
    assert guardado is not None, "erro generico nao pode apagar o token"
    assert guardado.access_token == "APP_USR-velho"

    def _sucesso(_refresh_token):
        return TokenSet(
            access_token="APP_USR-depois",
            refresh_token="TG-depois",
            expires_at=datetime.now(UTC) + timedelta(hours=6),
        )

    monkeypatch.setattr(oauth, "_refresh_http", _sucesso)
    assert await oauth.garante_token_valido(pg_pool, seller_id) == "APP_USR-depois"


async def test_invalid_grant_detectado_mesmo_com_corpo_longo(pg_pool, test_seller):
    """O campo `error` depois do caractere 200 ainda conta como revogacao.

    Com deteccao por substring sobre o corpo truncado, este caso passava batido:
    a revogacao nao era vista, o token morto ficava no banco, e o backend
    tentaria renova-lo pra sempre.
    """
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.POST,
            "https://api.mercadolibre.com/oauth/token",
            status=400,
            json={"message": "x" * 400, "error": "invalid_grant"},
        )
        with pytest.raises(oauth.ConexaoMLRevogada):
            await oauth.garante_token_valido(pg_pool, seller_id)

    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is None


async def test_substring_invalid_grant_em_corpo_estruturado_nao_apaga_token(pg_pool, test_seller):
    """Mencionar `invalid_grant` no texto nao e o mesmo que SER invalid_grant.

    Falso positivo aqui apaga o token bom de um seller e o obriga a reconectar
    sem motivo. A deteccao tem que olhar o campo, nao o texto.
    """
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.POST,
            "https://api.mercadolibre.com/oauth/token",
            status=500,
            json={
                "error": "internal_error",
                "message": "veja a lista de erros, inclusive invalid_grant, na doc",
            },
        )
        with pytest.raises(OAuthError):
            await oauth.garante_token_valido(pg_pool, seller_id)

    guardado = await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load()
    assert guardado is not None, "erro alheio apagou o token do seller"


async def test_timeout_de_rede_sai_como_oauth_error(pg_pool, test_seller):
    """Timeout nao pode subir cru: quem chama trata OAuthError, nao requests.Timeout."""
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.POST,
            "https://api.mercadolibre.com/oauth/token",
            body=requests.exceptions.ConnectTimeout("estourou"),
        )
        with pytest.raises(OAuthError):
            await oauth.garante_token_valido(pg_pool, seller_id)

    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is not None


async def test_200_com_corpo_malformado_sai_como_oauth_error(pg_pool, test_seller):
    """200 sem access_token: KeyError cru viraria 500 sem tratamento."""
    _u, seller_id = test_seller
    await _grava_token(pg_pool, seller_id, minutos=-5)

    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.POST,
            "https://api.mercadolibre.com/oauth/token",
            json={"nada": "aqui"},
        )
        with pytest.raises(OAuthError):
            await oauth.garante_token_valido(pg_pool, seller_id)
