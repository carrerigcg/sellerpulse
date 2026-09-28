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
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

# Versao da chave gravada junto de cada token. Hoje sempre 1; existe pra que
# uma rotacao futura possa decifrar o acervo antigo com a chave antiga
# enquanto grava o novo com a nova, sem migration de emergencia.
KEY_VERSION_ATUAL = 1


class TokenCifraError(Exception):
    """Ciphertext invalido, adulterado, ou cifrado com outra chave."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(os.environ["TOKEN_ENCRYPTION_KEY"].encode())


def cifra(valor: str) -> str:
    return _fernet().encrypt(valor.encode()).decode()


def decifra(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        # Mensagem sem o ciphertext: ele nao e segredo, mas jogar payload de
        # token em log e habito ruim de se ter.
        raise TokenCifraError("token ilegivel: adulterado ou chave errada") from exc
