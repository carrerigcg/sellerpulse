# backend/ml/tokens.py
"""Cifra dos tokens do Mercado Livre e persistencia por seller.

Por que cifrar e nao so confiar na RLS: um access_token do ML nao e
credencial de leitura. Com ele da pra editar anuncio, responder comprador e
ver dado de cliente. Se a tabela vazar — backup, service role comprometida,
ou eu mesmo olhando — vaza a LOJA do usuario, nao o dashboard dele. RLS
protege de outro usuario logado; nao protege de nenhum desses casos.
"""

from __future__ import annotations

import os
import uuid
from functools import lru_cache

import asyncpg
from cryptography.fernet import Fernet, InvalidToken

from src.auth import TokenSet

# Versao da chave gravada junto de cada token. Hoje e sempre 1 e NINGUEM le de
# volta: a coluna existe pra que uma rotacao futura seja possivel sem migration,
# nao porque rotacao ja funcione. Pra funcionar de verdade, decifra() teria que
# escolher a chave pela versao — via MultiFernet, que tenta uma lista de chaves
# na ordem. Rotacionar TOKEN_ENCRYPTION_KEY hoje quebra todos os tokens ja
# gravados de uma vez.
KEY_VERSION_ATUAL = 1


class TokenCifraError(Exception):
    """Ciphertext invalido, adulterado, ou cifrado com outra chave."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(os.environ["TOKEN_ENCRYPTION_KEY"].encode())


def cifra(valor: str) -> str:
    return _fernet().encrypt(valor.encode()).decode()


def decifra(valor: str) -> str:
    # _fernet() fica FORA do try: chave malformada e problema de configuracao do
    # processo, nao de integridade desta linha. Confundir os dois manda quem
    # depura procurar linha corrompida quando o que quebrou foi a env var.
    fernet = _fernet()
    try:
        return fernet.decrypt(valor.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        # Mensagem sem o ciphertext: ele nao e segredo, mas jogar payload de
        # token em log e habito ruim de se ter.
        raise TokenCifraError("token ilegivel: adulterado ou chave errada") from exc


class PostgresTokenStore:
    """Le e grava o TokenSet de UM seller na tabela oauth_tokens.

    Equivalente do `src.auth.TokenStore` (que usa arquivo JSON local) para o
    contexto multi-tenant: mesma interface conceitual (load/save), mas
    escopada por seller_id e com os valores cifrados.
    """

    def __init__(self, pool: asyncpg.Pool, seller_id: uuid.UUID) -> None:
        self._pool = pool
        self._seller_id = seller_id

    async def load(self) -> TokenSet | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT access_token_enc, refresh_token_enc, expires_at "
                "FROM oauth_tokens WHERE seller_id = $1",
                self._seller_id,
            )
        if row is None:
            return None
        return TokenSet(
            access_token=decifra(row["access_token_enc"]),
            refresh_token=decifra(row["refresh_token_enc"]),
            expires_at=row["expires_at"],
        )

    async def save(self, tokens: TokenSet) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO oauth_tokens (
                    seller_id, access_token_enc, refresh_token_enc,
                    expires_at, key_version, updated_at
                ) VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (seller_id) DO UPDATE SET
                    access_token_enc  = excluded.access_token_enc,
                    refresh_token_enc = excluded.refresh_token_enc,
                    expires_at        = excluded.expires_at,
                    key_version       = excluded.key_version,
                    updated_at        = now()
                """,
                self._seller_id,
                cifra(tokens.access_token),
                cifra(tokens.refresh_token),
                tokens.expires_at,
                KEY_VERSION_ATUAL,
            )

    async def delete(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM oauth_tokens WHERE seller_id = $1", self._seller_id)
