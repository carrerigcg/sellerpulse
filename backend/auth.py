# backend/auth.py
"""Validação de JWT emitido pelo Supabase Auth.

O Supabase emite tokens de duas formas, e um projeto pode usar qualquer uma:

- **Assimétrica (ES256/RS256)** — o padrão dos projetos novos. O header traz
  um `kid` e a chave pública fica no JWKS do projeto
  (`/auth/v1/.well-known/jwks.json`). É o modo deste projeto.
- **Simétrica (HS256)** — o modo legado, com o "JWT Secret" compartilhado.
  Continua valendo para as chaves `anon`/`service_role` antigas.

Este módulo aceita os dois: usa o `kid` do header pra decidir.

Nota de história, porque custou caro: a implementação original só aceitava
HS256. A verificação que "confirmou" essa premissa validou a **anon key**
contra o JWT Secret — e passou, porque a anon key é mesmo HS256. Mas os
tokens de *sessão de usuário* deste projeto são ES256, então toda chamada
autenticada respondia 401, e isso só apareceu na integração do dashboard.
Validar a coisa errada é pior do que não validar: dá confiança sem cobertura.
"""

from __future__ import annotations

import os
from functools import lru_cache

import jwt
from fastapi import HTTPException

_AUDIENCIA = "authenticated"


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """Cliente JWKS do projeto. Cacheado porque busca as chaves por HTTP.

    O `PyJWKClient` mantém cache interno das chaves, então a rotação de
    signing key no Supabase é absorvida sem redeploy (ele refaz o fetch
    quando encontra um `kid` desconhecido).
    """
    base = os.environ["SUPABASE_URL"].rstrip("/")
    return jwt.PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json")


def decode_supabase_jwt(token: str) -> dict:
    """Valida assinatura + expiração e devolve as claims.

    Levanta HTTPException(401) em qualquer falha — assinatura inválida,
    token expirado, audience errado ou payload malformado. A mensagem é
    genérica de propósito: não entrega ao cliente qual verificação falhou.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado") from exc

    try:
        if header.get("kid"):
            chave = _jwks_client().get_signing_key_from_jwt(token).key
            algoritmos = [header.get("alg", "ES256")]
        else:
            chave = os.environ["SUPABASE_JWT_SECRET"]
            algoritmos = ["HS256"]
        return jwt.decode(token, chave, algorithms=algoritmos, audience=_AUDIENCIA)
    except (jwt.PyJWTError, jwt.exceptions.PyJWKClientError) as exc:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado") from exc
