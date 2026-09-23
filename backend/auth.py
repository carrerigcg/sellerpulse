# backend/auth.py
"""Validação de JWT emitido pelo Supabase Auth.

Usa o JWT Secret compartilhado (HS256) do projeto, aplicado CRU — não
base64-decodificado. Validação local, sem round-trip de rede.
Ver Project Settings > API > JWT Settings no dashboard do Supabase.
"""
from __future__ import annotations

import os

import jwt
from fastapi import HTTPException


def decode_supabase_jwt(token: str) -> dict:
    """Valida assinatura + expiração e devolve as claims.

    Levanta HTTPException(401) em qualquer falha — assinatura inválida,
    token expirado, audience errado ou payload malformado. A mensagem é
    genérica de propósito: não entrega ao cliente qual verificação falhou.
    """
    secret = os.environ["SUPABASE_JWT_SECRET"]
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado") from exc
