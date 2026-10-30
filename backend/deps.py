# backend/deps.py
"""Dependencies do FastAPI — resolução de identidade autenticada.

O isolamento entre tenants do backend é feito AQUI: o seller_id nunca vem
do cliente, sempre é resolvido a partir do `sub` de um JWT já validado.
As queries analíticas filtram por esse valor.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import asyncpg
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth import decode_supabase_jwt
from backend.db import get_pool
from backend.planos import PLANOS, VERSAO_DOS_TERMOS, Plano, Recurso

_bearer = HTTPBearer()


async def resolve_seller_id(pool: asyncpg.Pool, user_id: str) -> uuid.UUID:
    """user_id (claim `sub` do JWT) -> seller_id. 404 se não houver seller.

    Não deveria acontecer em uso normal: um trigger no Supabase cria a row
    em `sellers` a cada insert em `auth.users`. É defesa contra estado
    inconsistente.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM sellers WHERE user_id = $1", user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Usuário sem seller associado")
    return row["id"]


async def get_current_seller_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Dependency dos endpoints: valida o Bearer token e devolve o seller_id."""
    claims = decode_supabase_jwt(credentials.credentials)
    pool = await get_pool()
    return await resolve_seller_id(pool, claims["sub"])


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Só o token: para o que precisa continuar valendo sem `sellers`."""
    return uuid.UUID(decode_supabase_jwt(credentials.credentials)["sub"])


@dataclass(frozen=True)
class Acesso:
    seller_id: uuid.UUID
    plano: Plano


def recusa(status: int, codigo: str, mensagem: str) -> HTTPException:
    # `codigo` é o que o front lê para decidir a tela (planos, aceite,
    # cadeado); `mensagem` é para quem lê o erro cru.
    return HTTPException(status_code=status, detail={"codigo": codigo, "mensagem": mensagem})


async def le_plano_e_aceite(pool: asyncpg.Pool, seller_id: uuid.UUID) -> tuple[Plano | None, bool]:
    """O plano do vendedor (None se não tem) e se aceitou a versão vigente.

    Plano com prazo vencido (`acesso_ate` no passado) conta como sem plano: é
    assim que a inadimplência e o cancelamento desligam o acesso, sem
    agendador nenhum (spec docs/specs/2026-10-29-cobranca-asaas-design.md).
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.plano,
                   EXISTS (SELECT 1 FROM aceites_de_termos t
                            WHERE t.seller_id = $1 AND t.versao = $2) AS aceitou
              FROM (SELECT 1) AS um
              LEFT JOIN assinaturas a
                     ON a.seller_id = $1
                    AND (a.acesso_ate IS NULL OR a.acesso_ate > now())
            """,
            seller_id,
            VERSAO_DOS_TERMOS,
        )
    plano = PLANOS[row["plano"]] if row["plano"] is not None else None
    return plano, row["aceitou"]


async def get_acesso(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> Acesso:
    """Vendedor com plano E com os termos vigentes aceitos. Senão, recusa.

    Sem plano, 402 (o caminho é contratar). Com plano e sem aceite, 403
    `termos-pendentes` (o caminho é aceitar). A ordem importa: quem não tem
    plano não tem contrato para aceitar.
    """
    pool = await get_pool()
    plano, aceitou = await le_plano_e_aceite(pool, seller_id)
    if plano is None:
        raise recusa(402, "sem-plano", "Contrate um plano para acessar o painel")
    if not aceitou:
        raise recusa(403, "termos-pendentes", "Aceite os Termos de Uso para continuar")
    return Acesso(seller_id=seller_id, plano=plano)


def exige(recurso: Recurso) -> Callable[..., Awaitable[Acesso]]:
    """Dependency que, além do acesso, exige que o plano libere `recurso`."""

    async def _dependency(acesso: Acesso = Depends(get_acesso)) -> Acesso:
        if not acesso.plano.libera(recurso):
            raise recusa_fora_do_plano()
        return acesso

    return _dependency


def recusa_fora_do_plano() -> HTTPException:
    return recusa(403, "fora-do-plano", "Disponível em um plano acima do seu")
