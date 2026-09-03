"""OAuth helpers para contexto web (Streamlit + futuro Next.js/FastAPI).

Camada fina sobre src/auth.OAuthClient. Módulo puro Python — zero
import de streamlit. Testável isoladamente com biblioteca `responses`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import requests

from src.auth import TokenSet

ML_AUTHORIZE_URL = "https://auth.mercadolivre.com.br/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class OAuthError(Exception):
    """Falha no fluxo OAuth (rede, credenciais, ou 4xx do ML).

    NOTA: distinta de src.auth.OAuthError, que sinaliza falha em fluxo
    com persistência em disco (setup_auth.py). Esta exceção é para
    callers em contexto web (Streamlit callback) que gerenciam tokens
    via session_state em memória. Não são intercambiáveis — capture a
    correta conforme a origem da chamada.
    """


_ML_TOKEN_PATTERNS = [
    re.compile(r"APP_USR-[\w\-]+"),  # access token pattern
    re.compile(r"TG-[\w\-]+"),  # refresh token pattern
]


def sanitize_oauth_error(message: str) -> str:
    """Redige tokens ML de uma string antes de logar ou mostrar ao usuário.

    Substitui qualquer match dos patterns conhecidos por [REDACTED].
    Preserva o resto da mensagem intacto.
    """
    out = message
    for pattern in _ML_TOKEN_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    """Monta a URL de consentimento OAuth do Mercado Livre.

    O `state` é o token anti-CSRF gerado pelo caller (`secrets.token_urlsafe(32)`)
    e será devolvido intacto no callback — cabe ao caller validar.
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{ML_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> TokenSet:
    """Troca o `code` do callback OAuth por um TokenSet.

    Não persiste em disco — cabe ao caller salvar em session_state (via
    InMemoryTokenStore). Levanta OAuthError em qualquer resposta != 200.
    """
    response = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise OAuthError(
            sanitize_oauth_error(
                f"Falha no exchange ({response.status_code}): {response.text[:200]}"
            )
        )
    data = response.json()
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
    )
