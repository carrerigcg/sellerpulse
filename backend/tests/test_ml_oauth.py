"""Testes do fluxo OAuth do Mercado Livre no contexto multi-tenant."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from backend.ml import oauth


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
