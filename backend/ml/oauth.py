# backend/ml/oauth.py
"""Fluxo OAuth do Mercado Livre no contexto multi-tenant.

Camada sobre `src/session_auth.py` (que monta a URL de consentimento e troca
o code, sem persistir nada). O que este modulo acrescenta e o que o SaaS
precisa: identidade viajando no `state`, e refresh coordenado entre processos.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import jwt
import requests

from backend.ml.tokens import KEY_VERSION_ATUAL, cifra, decifra
from src.auth import TokenSet
from src.session_auth import ML_TOKEN_URL, OAuthError, build_authorize_url, sanitize_oauth_error

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


class SemConexaoML(Exception):
    """O seller nunca conectou uma conta do Mercado Livre."""


class ConexaoMLRevogada(Exception):
    """O refresh_token morreu (usuario revogou no ML). Precisa reconectar."""


def _refresh_http(refresh_token: str) -> TokenSet:
    """Troca refresh_token por um par novo. SINCRONO — sempre via to_thread.

    Separado de `garante_token_valido` pra que o teste possa substituir esta
    funcao e contar chamadas sem mexer no lock.
    """
    resposta = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": os.environ["ML_CLIENT_ID"],
            "client_secret": os.environ["ML_CLIENT_SECRET"],
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if resposta.status_code != 200:
        corpo = sanitize_oauth_error(resposta.text[:200])
        if "invalid_grant" in corpo:
            raise ConexaoMLRevogada(corpo)
        raise OAuthError(f"Falha no refresh ({resposta.status_code}): {corpo}")
    dados = resposta.json()
    return TokenSet(
        access_token=dados["access_token"],
        refresh_token=dados["refresh_token"],
        expires_at=datetime.now(UTC) + timedelta(seconds=int(dados["expires_in"])),
    )


async def garante_token_valido(pool: asyncpg.Pool, seller_id: uuid.UUID) -> str:
    """Devolve um access_token valido, renovando sob lock se necessario.

    O `FOR UPDATE` serializa o refresh entre corrotinas e entre processos: o
    ML rotaciona o refresh_token a cada uso, entao dois refreshes paralelos
    invalidariam um ao outro. Quem chega segundo espera o lock, rele a linha,
    e encontra o token ja renovado.

    O lock e mantido durante a chamada HTTP de proposito. Isso segura uma
    conexao do pool por alguns segundos, o que e aceitavel porque refresh
    acontece a cada ~6 horas por seller — o custo de NAO serializar e
    desconectar o usuario.
    """
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT access_token_enc, refresh_token_enc, expires_at "
                    "FROM oauth_tokens WHERE seller_id = $1 FOR UPDATE",
                    seller_id,
                )
                if row is None:
                    raise SemConexaoML(f"seller {seller_id} sem conexao com o Mercado Livre")

                atual = TokenSet(
                    access_token=decifra(row["access_token_enc"]),
                    refresh_token=decifra(row["refresh_token_enc"]),
                    expires_at=row["expires_at"],
                )
                if not atual.is_expired():
                    return atual.access_token

                novos = await asyncio.to_thread(_refresh_http, atual.refresh_token)

                await conn.execute(
                    """
                    UPDATE oauth_tokens SET
                        access_token_enc = $2, refresh_token_enc = $3,
                        expires_at = $4, key_version = $5, updated_at = now()
                    WHERE seller_id = $1
                    """,
                    seller_id,
                    cifra(novos.access_token),
                    cifra(novos.refresh_token),
                    novos.expires_at,
                    KEY_VERSION_ATUAL,
                )
                return novos.access_token
        except ConexaoMLRevogada:
            # FORA do `async with conn.transaction()`: a excecao propagando de
            # dentro dele dispara ROLLBACK antes de chegar aqui, entao um
            # DELETE executado la dentro nunca commitaria. Aqui fora, `conn`
            # nao esta em transacao explicita — o DELETE roda e commita
            # sozinho, imediatamente.
            await conn.execute("DELETE FROM oauth_tokens WHERE seller_id = $1", seller_id)
            raise
