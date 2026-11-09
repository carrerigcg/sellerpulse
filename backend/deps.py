# backend/deps.py
"""Dependencies do FastAPI — resolução de identidade autenticada.

O isolamento entre tenants do backend é feito AQUI: o seller_id nunca vem
do cliente, sempre é resolvido a partir do `sub` de um JWT já validado.
As queries analíticas filtram por esse valor.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

import asyncpg
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth import decode_supabase_jwt
from backend.db import get_pool
from backend.jobs import queue
from backend.planos import (
    ASSINATURA_VIGENTE,
    DIAS_DE_INGESTAO_MINIMO,
    PLANOS,
    VERSAO_DOS_TERMOS,
    Plano,
    Recurso,
    conta_abre,
)

_bearer = HTTPBearer()


async def resolve_seller_id(pool: asyncpg.Pool, user_id: str) -> uuid.UUID:
    """user_id (claim `sub` do JWT) -> seller_id da conta principal. 404 se não houver.

    É a principal que tem plano, aceite e cobrança. A conta aberta na tela,
    que pode ser uma extra, vem de `get_contas`.

    Não deveria acontecer em uso normal: um trigger no Supabase cria a row
    em `sellers` a cada insert em `auth.users`. É defesa contra estado
    inconsistente.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM sellers WHERE user_id = $1 AND principal", uuid.UUID(str(user_id))
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Usuário sem seller associado")
    return row["id"]


async def _claims_verificadas(pool: asyncpg.Pool, token: str) -> dict:
    """Valida o token e, de quem ativou o segundo fator, exige o código.

    O Supabase marca `aal: "aal2"` no token de quem passou pelo app
    autenticador. Sem esta trava, a verificação em duas etapas seria só de
    tela: com a senha, o token `aal1` chamaria a API direto (spec
    docs/specs/2026-11-04-telefone-e-verificacao-em-duas-etapas-design.md).
    """
    claims = decode_supabase_jwt(token)
    if claims.get("aal") != "aal2":
        async with pool.acquire() as conn:
            tem_fator = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM auth.mfa_factors "
                "WHERE user_id = $1 AND status = 'verified')",
                uuid.UUID(claims["sub"]),
            )
        if tem_fator:
            raise recusa(401, "segundo-fator", "Confirme o código do app autenticador")
    return claims


async def get_current_seller_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Dependency dos endpoints: valida o Bearer token e devolve o seller_id."""
    pool = await get_pool()
    claims = await _claims_verificadas(pool, credentials.credentials)
    return await resolve_seller_id(pool, claims["sub"])


# O valor de `X-Conta` que pede a visão que soma as contas do login (Premium).
TODAS_AS_CONTAS = "todas"


@dataclass(frozen=True)
class Contas:
    principal: uuid.UUID
    # A que a tela mostra: a do cabeçalho `X-Conta`, ou a principal. Na visão
    # somada, a principal, mas quem soma lê `somadas`.
    aberta: uuid.UUID
    # Na visão somada, todas as contas do login, a principal primeiro. Vazio
    # fora dela.
    somadas: tuple[uuid.UUID, ...] = ()

    @property
    def somada(self) -> bool:
        return bool(self.somadas)

    @property
    def extra_aberta(self) -> bool:
        return not self.somada and self.aberta != self.principal


def recusa_conta_invalida() -> HTTPException:
    return recusa(403, "conta-invalida", "Esta conta do Mercado Livre não está disponível")


def recusa_visao_somada() -> HTTPException:
    return recusa(409, "visao-somada", "Escolha uma conta do Mercado Livre para esta tela")


async def resolve_contas(pool: asyncpg.Pool, user_id: str, x_conta: str | None) -> Contas:
    """A principal do usuário e a conta pedida no cabeçalho, conferida.

    Conta que não é do usuário é recusada, e nunca trocada pela principal: o
    número de uma conta apareceria com o nome de outra.
    """
    if x_conta == TODAS_AS_CONTAS:
        async with pool.acquire() as conn:
            linhas = await conn.fetch(
                "SELECT id FROM sellers WHERE user_id = $1 ORDER BY principal DESC, created_at, id",
                uuid.UUID(str(user_id)),
            )
        if not linhas:
            raise HTTPException(status_code=404, detail="Usuário sem seller associado")
        ids = tuple(linha["id"] for linha in linhas)
        return Contas(principal=ids[0], aberta=ids[0], somadas=ids)
    pedida = None
    if x_conta:
        try:
            pedida = uuid.UUID(x_conta)
        except ValueError:
            raise recusa_conta_invalida() from None
    async with pool.acquire() as conn:
        linhas = await conn.fetch(
            "SELECT id, principal FROM sellers WHERE user_id = $1 AND (principal OR id = $2)",
            uuid.UUID(str(user_id)),
            pedida,
        )
    principal = next((linha["id"] for linha in linhas if linha["principal"]), None)
    if principal is None:
        raise HTTPException(status_code=404, detail="Usuário sem seller associado")
    if pedida is not None and pedida not in {linha["id"] for linha in linhas}:
        raise recusa_conta_invalida()
    return Contas(principal=principal, aberta=pedida or principal)


async def get_contas_somaveis(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    x_conta: str | None = Header(default=None),
) -> Contas:
    """A conta aberta, ou a visão somada. Só para quem sabe tratar as duas."""
    pool = await get_pool()
    claims = await _claims_verificadas(pool, credentials.credentials)
    return await resolve_contas(pool, claims["sub"], x_conta)


async def get_contas(contas: Contas = Depends(get_contas_somaveis)) -> Contas:
    """A conta aberta, sem exigir plano: para desconectar e ver o status.

    Recusa a visão somada (409 `visao-somada`). É o padrão de propósito: uma
    rota nova que não pensou na soma não grava nem mostra uma conta só com o
    rótulo de todas (spec 2026-11-06-premium-varias-contas, parte B, item 3).
    """
    if contas.somada:
        raise recusa_visao_somada()
    return contas


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Só o token: para o que precisa continuar valendo sem `sellers`."""
    claims = await _claims_verificadas(await get_pool(), credentials.credentials)
    return uuid.UUID(claims["sub"])


@dataclass(frozen=True)
class Acesso:
    plano: Plano
    # A que tem o plano e a cobrança. É a mesma quando não há conta extra aberta.
    principal_id: uuid.UUID
    # As contas que a tela lê: a aberta, ou todas na visão somada.
    contas: tuple[uuid.UUID, ...]
    somada: bool = False

    @property
    def seller_id(self) -> uuid.UUID:
        """A conta aberta, para o que é de uma conta só.

        Na visão somada não existe uma: rota que optou pela soma e leu uma
        conta só mostraria a principal com o rótulo de todas. Erro, e não a
        principal, para isso aparecer no teste e não na tela.
        """
        if self.somada:
            raise RuntimeError("visão somada: leia `acesso.contas`, não `acesso.seller_id`")
        return self.contas[0]


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
            f"""
            SELECT a.plano,
                   EXISTS (SELECT 1 FROM aceites_de_termos t
                            WHERE t.seller_id = $1 AND t.versao = $2) AS aceitou
              FROM (SELECT 1) AS um
              LEFT JOIN assinaturas a
                     ON a.seller_id = $1
                    AND {ASSINATURA_VIGENTE}
            """,
            seller_id,
            VERSAO_DOS_TERMOS,
        )
    plano = PLANOS[row["plano"]] if row["plano"] is not None else None
    return plano, row["aceitou"]


async def historico_visivel(
    pool: asyncpg.Pool, seller_id: uuid.UUID, plano: Plano
) -> tuple[int | None, bool]:
    """Os dias que a tela mostra, e se ainda falta buscar o que o plano promete.

    É o menor entre o plano e o que o backfill já trouxe: com 6 meses
    buscados, mostrar 12 exibiria os 6 antigos como venda zero. Ausência não é
    zero. Antes do primeiro backfill vale o plano, porque a tela de conexão já
    mostra o progresso (spec 2026-11-06-premium-historico-de-12-meses, decisão 6).
    """
    dias = plano.dias_de_historico
    # Só o plano que mostra além do piso de ingestão pode estar à frente do
    # que foi buscado: os outros nem consultam a fila.
    if dias is None or dias <= DIAS_DE_INGESTAO_MINIMO:
        return dias, False
    buscados = await queue.dias_ja_buscados(pool, seller_id)
    if buscados is None or buscados >= dias:
        return dias, False
    return buscados, True


async def historico_das_contas(
    pool: asyncpg.Pool, contas: tuple[uuid.UUID, ...], plano: Plano
) -> tuple[int | None, bool]:
    """`historico_visivel` de várias contas: o menor, e se alguma ainda busca.

    Na visão somada, uma conta já em 12 meses e outra ainda em 6: mostrar 12
    exibiria os 6 antigos da segunda como venda zero.
    """
    resultados = [await historico_visivel(pool, conta, plano) for conta in contas]
    dias = [d for d, _buscando in resultados if d is not None]
    return (min(dias) if dias else None), any(buscando for _d, buscando in resultados)


async def _acesso(contas: Contas) -> Acesso:
    pool = await get_pool()
    plano, aceitou = await le_plano_e_aceite(pool, contas.principal)
    if plano is None:
        raise recusa(402, "sem-plano", "Contrate um plano para acessar o painel")
    if not aceitou:
        raise recusa(403, "termos-pendentes", "Aceite os Termos de Uso para continuar")
    if contas.somada:
        # Somar é do plano de várias contas: fora dele, o front volta à principal.
        if plano.max_contas < 2:
            raise recusa_conta_invalida()
        lidas = contas.somadas
    else:
        if not conta_abre(plano, principal=not contas.extra_aberta):
            raise recusa_conta_invalida()
        lidas = (contas.aberta,)
    # O histórico é o das contas lidas: cada conta tem o próprio backfill.
    dias, _buscando = await historico_das_contas(pool, lidas, plano)
    if dias != plano.dias_de_historico:
        # O corte (`limita_ao_historico`) lê os dias do plano. Trocar aqui, num
        # lugar só, cobre todas as telas sem que cada router saiba da busca.
        plano = replace(plano, dias_de_historico=dias)
    return Acesso(plano=plano, principal_id=contas.principal, contas=lidas, somada=contas.somada)


async def get_acesso_somavel(contas: Contas = Depends(get_contas_somaveis)) -> Acesso:
    """`get_acesso` que aceita a visão somada. Só para as leituras que somam."""
    return await _acesso(contas)


async def get_acesso(contas: Contas = Depends(get_contas)) -> Acesso:
    """Vendedor com plano E com os termos vigentes aceitos. Senão, recusa.

    Sem plano, 402 (o caminho é contratar). Com plano e sem aceite, 403
    `termos-pendentes` (o caminho é aceitar). A ordem importa: quem não tem
    plano não tem contrato para aceitar. A visão somada é recusada (409
    `visao-somada`); quem soma usa `get_acesso_somavel`.
    """
    return await _acesso(contas)


def exige(recurso: Recurso, *, somavel: bool = False) -> Callable[..., Awaitable[Acesso]]:
    """Dependency que, além do acesso, exige que o plano libere `recurso`."""
    base = get_acesso_somavel if somavel else get_acesso

    async def _dependency(acesso: Acesso = Depends(base)) -> Acesso:
        if not acesso.plano.libera(recurso):
            raise recusa_fora_do_plano()
        return acesso

    return _dependency


def recusa_fora_do_plano() -> HTTPException:
    return recusa(403, "fora-do-plano", "Disponível em um plano acima do seu")
