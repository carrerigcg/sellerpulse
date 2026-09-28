# backend/ml/oauth.py
"""Fluxo OAuth do Mercado Livre no contexto multi-tenant.

Camada sobre `src/session_auth.py` (que monta a URL de consentimento e troca
o code, sem persistir nada). O que este modulo acrescenta e o que o SaaS
precisa: identidade viajando no `state`, e refresh coordenado entre processos.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt

from src.session_auth import build_authorize_url

# `aud` fixa amarra o token a ESTE proposito. Sem ela, qualquer JWT assinado
# com o mesmo segredo — hoje ou num uso futuro qualquer — passaria por state.
AUDIENCIA_STATE = "sellerpulse:ml-oauth-state"

# Dez minutos: tempo de sobra pra consentir no ML, curto o suficiente pra que
# um state capturado em log ou historico de browser nao valha nada depois.
VALIDADE_STATE = timedelta(minutes=10)


class StateInvalido(Exception):
    """`state` do callback ausente, expirado, mal assinado, ou de outro proposito."""


def emite_state(seller_id: str, *, agora: datetime | None = None) -> str:
    """Token curto que prova que este callback pertence ao fluxo que o iniciou.

    `agora` existe pra teste determinar a janela; em producao sempre o default.
    """
    agora = agora or datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(seller_id),
            "aud": AUDIENCIA_STATE,
            # `iat` nao e validado pelo PyJWT nem por valida_state — fica so pra
            # correlacionar com log quando alguem for investigar um callback.
            # Quem garante a janela e o `exp`.
            "iat": agora,
            "exp": agora + VALIDADE_STATE,
        },
        os.environ["STATE_SECRET"],
        algorithm="HS256",
    )


def valida_state(state: str) -> str:
    """Devolve o seller_id embutido, ou levanta StateInvalido."""
    try:
        claims = jwt.decode(
            state,
            os.environ["STATE_SECRET"],
            algorithms=["HS256"],
            audience=AUDIENCIA_STATE,
        )
    except jwt.PyJWTError as exc:
        raise StateInvalido("state invalido ou expirado") from exc
    sub = claims.get("sub")
    if not sub:
        raise StateInvalido("state sem sub")
    return sub


def url_de_consentimento(seller_id: str) -> tuple[str, str]:
    """Devolve (url, state). O client_secret nao entra aqui — so no exchange."""
    state = emite_state(seller_id)
    url = build_authorize_url(
        client_id=os.environ["ML_CLIENT_ID"],
        redirect_uri=os.environ["ML_REDIRECT_URI"],
        state=state,
    )
    return url, state
