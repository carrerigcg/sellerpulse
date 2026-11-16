# backend/mcp_conta.py
"""Servidor MCP da conta real: o vendedor do Premium pergunta à IA sobre a loja dele.

Spec: docs/specs/2026-11-09-premium-mcp-conta-real-design.md. É o par do
`mcp_server.py` (a demonstração, pública): as mesmas seis ferramentas, só
leitura, mas sobre o dado de quem autorizou, e atrás do login OAuth 2.1 do
Supabase.

O que separa este servidor de um vazamento de faturamento:

1. Quem é o vendedor sai SÓ do token validado (`sub`), nunca de parâmetro. O
   parâmetro `conta` escolhe entre as contas DESTE login, e é conferido.
2. Só token emitido para um cliente de IA (`client_id`) entra aqui, e o
   contrário vale na API REST (`deps._claims_verificadas`): o token da IA não
   grava custo nem cancela assinatura.
3. A sessão é conferida a cada chamada: desconectar na tela corta na hora, e
   não quando o token vencer.
4. Plano, aceite, conta que abre e histórico vêm de `deps._acesso`, a mesma
   regra do painel.
"""

from __future__ import annotations

import contextvars
import os
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

import pandas as pd
from fastapi import HTTPException
from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import Response

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos
from backend.analytics.segmentation_pg import abc_pareto, cohort_produto, rfm_scores
from backend.auth import decode_supabase_jwt
from backend.db import get_pool
from backend.deps import TODAS_AS_CONTAS, Acesso, _acesso, resolve_contas
from backend.mcp_server import JANELA_PADRAO_DIAS, periodo_anterior, resolve_janela, variacao
from backend.planos import Recurso
from backend.routers._common import limita_ao_historico, validate_n

# O endereço público deste servidor. É o identificador do recurso protegido
# (RFC 9728): o cliente de IA lê o metadado a partir dele e sabe onde logar.
URL_DO_RECURSO = os.environ.get("MCP_CONTA_URL", "https://api.usesellerpulse.com/mcp/conta")

# Teto de chamadas de ferramenta por login e por hora (decisão 12 da spec).
LIMITE_POR_HORA = 300

# Quanto antes de a sessão do token nascer a aprovação com o app autenticador
# ainda vale (decisão 7). Na conexão real, a sessão nasceu 1 s depois da
# aprovação; a folga cobre quem demora a voltar ao Claude, e mais que isso
# seria deixar a aprovação de um dia servir para a conexão do outro.
JANELA_DA_APROVACAO = timedelta(minutes=15)

# A aprovação é gravada pelo relógio do Postgres, e a sessão pelo do servidor
# de login do Supabase. A folga evita barrar a conexão legítima por diferença
# entre os dois; uma sessão que já existia antes da aprovação (minutos ou
# horas) continua fora.
FOLGA_DO_RELOGIO = timedelta(minutes=1)

_URL_ASSINATURA = "https://usesellerpulse.com/dashboard/assinatura"
_URL_ACEITE = "https://usesellerpulse.com/aceite"


def emissor() -> str:
    """O servidor de autorização: o Auth do projeto Supabase."""
    base = os.environ.get("SUPABASE_URL", "https://supabase.invalid").rstrip("/")
    return f"{base}/auth/v1"


_INSTRUCOES = f"""\
Analises de vendas do SellerPulse sobre a loja do proprio vendedor no Mercado
Livre. Os numeros sao reais e de quem autorizou esta conexao.

Toda resposta diz de qual conta e de qual periodo e o dado. Com mais de uma
conta no Mercado Livre, o parametro `conta` escolhe a loja pelo apelido, ou
`todas` para a soma; sem ele, e a conta principal.

Margem aqui e margem de CONTRIBUICAO: receita bruta menos a comissao do
Mercado Livre, o frete e o custo do produto que o vendedor INFORMOU. Produto
sem custo informado nao desconta nada: `receita_sem_custo` diz quanto da
receita ficou sem custo, e enquanto ela nao for zero a margem nao e lucro.
O mesmo vale para o frete ainda nao buscado (`receita_sem_frete`). Ausencia
nao e zero: nunca preencha um custo que nao veio.

As datas sao inclusivas nos dois lados: `date_to` e o ultimo dia contado.
Omitindo as datas, a janela e dos ultimos {JANELA_PADRAO_DIAS} dias. O periodo
nunca passa do historico do plano; quando a janela pedida foi cortada, a
resposta traz `historico_desde`.
"""


# --------------------------------------------------------------------------
# Token
# --------------------------------------------------------------------------


class VerificadorSupabase:
    """Aceita só o token de acesso que o Supabase emitiu para um cliente de IA."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = decode_supabase_jwt(token)
        except HTTPException:
            return None
        cliente = claims.get("client_id")
        sessao = claims.get("session_id")
        sub = claims.get("sub")
        # Sem `client_id` é a sessão do site: ela não serve aqui (decisão 4).
        if not cliente or not sessao or not sub:
            return None
        pool = await get_pool()
        async with pool.acquire() as conn:
            linha = await conn.fetchrow(
                """
                SELECT
                    EXISTS (SELECT 1 FROM auth.sessions
                             WHERE id = $1 AND user_id = $2
                               AND (not_after IS NULL OR not_after > now())) AS viva,
                    EXISTS (SELECT 1 FROM auth.mfa_factors
                             WHERE user_id = $2 AND status = 'verified') AS tem_fator,
                    EXISTS (SELECT 1 FROM aprovacoes_de_ia a
                              JOIN auth.sessions s ON s.id = $1
                             WHERE a.user_id = $2 AND a.client_id = $3
                               AND a.aprovado_em <= s.created_at + $5::interval
                               AND a.aprovado_em > s.created_at - $4::interval)
                        AS aprovado_com_codigo
                """,
                uuid.UUID(str(sessao)),
                uuid.UUID(str(sub)),
                str(cliente),
                JANELA_DA_APROVACAO,
                FOLGA_DO_RELOGIO,
            )
        # Sessão apagada é conexão desconectada (decisão 5).
        if not linha["viva"]:
            return None
        # Quem ativou o app autenticador precisa ter passado por ele (decisão
        # 7). O token do Supabase nasce `aal1` mesmo assim, então a prova é a
        # aprovação que o backend gravou com sessão `aal2`, logo antes de a
        # sessão deste token nascer.
        if linha["tem_fator"] and claims.get("aal") != "aal2" and not linha["aprovado_com_codigo"]:
            return None
        return AccessToken(
            token=token,
            client_id=str(cliente),
            scopes=[],
            expires_at=claims.get("exp"),
            subject=str(sub),
            claims=claims,
        )


mcp = MCPServer(
    name="sellerpulse",
    title="SellerPulse",
    instructions=_INSTRUCOES,
    token_verifier=VerificadorSupabase(),
    auth=AuthSettings(
        issuer_url=emissor(),
        resource_server_url=URL_DO_RECURSO,
        # O verificador confere o `client_id` por conta própria: o Supabase
        # emite `aud: authenticated`, e não o endereço deste recurso.
        validate_token_resource=False,
    ),
)


# --------------------------------------------------------------------------
# Limite de uso e registro de acesso
# --------------------------------------------------------------------------

# O IP de quem chamou, posto pelo `_ComIp` em volta do ASGI.
_ip_da_chamada: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ip_da_chamada", default=None
)

_chamadas: dict[str, deque[float]] = defaultdict(deque)


def conta_chamada(user_id: str, *, agora: float | None = None) -> bool:
    """Registra a chamada e diz se ela cabe no limite da última hora.

    Em memória, numa instância: zera a cada deploy. É proteção do serviço, e
    não cobrança (decisão 12).
    """
    agora = time.monotonic() if agora is None else agora
    fila = _chamadas[user_id]
    while fila and fila[0] <= agora - 3600:
        fila.popleft()
    if len(fila) >= LIMITE_POR_HORA:
        return False
    fila.append(agora)
    return True


async def _registra_acesso(pool, user_id: uuid.UUID) -> None:
    """Marco Civil, art. 15: a mesma linha por hora e IP que o painel grava."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO registros_de_acesso (user_id, ip, hora)
            VALUES ($1, $2, date_trunc('hour', now()))
            ON CONFLICT DO NOTHING
            """,
            user_id,
            _ip_da_chamada.get() or "desconhecido",
        )


# --------------------------------------------------------------------------
# Quem pergunta e qual conta
# --------------------------------------------------------------------------

_MENSAGENS = {
    "sem-plano": (
        "A conexao com a IA e uma funcao do plano Premium, e esta conta nao tem plano "
        f"ativo. Para assinar: {_URL_ASSINATURA}"
    ),
    "termos-pendentes": (
        f"O vendedor precisa aceitar os Termos de Uso vigentes antes: {_URL_ACEITE}"
    ),
    "conta-invalida": (
        "Esta conta do Mercado Livre nao esta disponivel neste login ou neste plano."
    ),
    "fora-do-plano": (
        f"A conexao com a IA e uma funcao do plano Premium. Para mudar de plano: {_URL_ASSINATURA}"
    ),
}


def _mensagem(exc: HTTPException) -> str:
    detalhe = exc.detail if isinstance(exc.detail, dict) else {}
    return _MENSAGENS.get(detalhe.get("codigo", ""), "Nao foi possivel ler a conta agora.")


async def _contas_pedidas(pool, user_id: uuid.UUID, conta: str | None):
    """`conta` (apelido ou `todas`) -> as contas deste login, conferidas."""
    if conta is None or not conta.strip():
        return await resolve_contas(pool, str(user_id), None)
    if conta.strip().lower() == TODAS_AS_CONTAS:
        return await resolve_contas(pool, str(user_id), TODAS_AS_CONTAS)
    async with pool.acquire() as conn:
        linhas = await conn.fetch(
            "SELECT id, ml_nickname FROM sellers WHERE user_id = $1 AND ml_seller_id IS NOT NULL",
            user_id,
        )
    achadas = [
        linha["id"]
        for linha in linhas
        if (linha["ml_nickname"] or "").strip().lower() == conta.strip().lower()
    ]
    if len(achadas) != 1:
        apelidos = sorted(linha["ml_nickname"] for linha in linhas if linha["ml_nickname"])
        raise ValueError(
            f"Conta {conta!r} nao encontrada. As contas deste login sao: "
            f"{', '.join(apelidos) or 'nenhuma conectada'}; ou `todas` para a soma."
        )
    return await resolve_contas(pool, str(user_id), str(achadas[0]))


async def _nomes(pool, contas: tuple[uuid.UUID, ...]) -> list[str]:
    async with pool.acquire() as conn:
        linhas = await conn.fetch(
            "SELECT id, ml_nickname FROM sellers WHERE id = any($1::uuid[])", list(contas)
        )
    por_id = {linha["id"]: linha["ml_nickname"] or "(sem apelido)" for linha in linhas}
    return [por_id[c] for c in contas if c in por_id]


async def _contexto(conta: str | None) -> tuple[Any, Acesso, list[str]]:
    """Pool, acesso conferido e o nome das contas lidas. Erro legível para a IA."""
    token = get_access_token()
    if token is None or token.subject is None:
        # Não acontece atrás do middleware; é a trava se alguém montar errado.
        raise ValueError("Conexao sem login.")
    user_id = uuid.UUID(token.subject)
    if not conta_chamada(token.subject):
        raise ValueError(
            f"Limite de {LIMITE_POR_HORA} chamadas por hora atingido. Tente de novo mais tarde."
        )
    pool = await get_pool()
    await _registra_acesso(pool, user_id)
    try:
        contas = await _contas_pedidas(pool, user_id, conta)
        acesso = await _acesso(contas)
    except HTTPException as exc:
        raise ValueError(_mensagem(exc)) from exc
    if not acesso.plano.libera(Recurso.MCP_CONTA):
        raise ValueError(_MENSAGENS["fora-do-plano"])
    return pool, acesso, await _nomes(pool, acesso.contas)


def _janela(acesso: Acesso, date_from: str | None, date_to: str | None):
    """A janela pedida, cortada no histórico do plano. `historico_desde` se cortou."""
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    try:
        de_q, ate_q, cortado = limita_ao_historico(acesso.plano, de_q, ate_q)
    except HTTPException as exc:
        raise ValueError(
            "O periodo pedido esta todo antes do historico do plano "
            f"({acesso.plano.dias_de_historico} dias)."
        ) from exc
    if cortado is not None:
        de = cortado
    return de, ate, de_q, ate_q, cortado


def envelope(
    nomes: list[str], somada: bool, de: str, ate: str, cortado: str | None, dados: Any
) -> dict[str, Any]:
    """Toda resposta diz de qual conta e de qual período é o dado (decisão 10)."""
    resposta: dict[str, Any] = {
        "contas": nomes,
        "soma_das_contas": somada,
        "periodo": {"de": de, "ate": ate},
        "dados": dados,
    }
    if cortado is not None:
        resposta["historico_desde"] = cortado
    return resposta


def _registros(df: pd.DataFrame) -> list[dict]:
    return df.to_dict(orient="records") if not df.empty else []


# --------------------------------------------------------------------------
# As seis ferramentas
# --------------------------------------------------------------------------

_SOBRE_CONTA = (
    " O parametro `conta` escolhe a loja pelo apelido no Mercado Livre, ou `todas` para a "
    "soma; sem ele, e a conta principal."
)


@mcp.tool(
    name="visao_geral",
    description=(
        "Resumo do periodo: receita bruta, comissao do Mercado Livre, frete, custo do produto "
        "informado, margem de contribuicao e a variacao contra o periodo anterior de mesma "
        "duracao. Comece por esta ferramenta quando a pergunta for ampla, do tipo 'como foi o "
        "mes'. Margem de contribuicao so e lucro quando `receita_sem_custo` e zero." + _SOBRE_CONTA
    ),
)
async def visao_geral(
    date_from: str | None = None, date_to: str | None = None, conta: str | None = None
) -> dict[str, Any]:
    pool, acesso, nomes = await _contexto(conta)
    de, ate, de_q, ate_q, cortado = _janela(acesso, date_from, date_to)
    atual = await fluxo_financeiro(pool, acesso.contas, de_q, ate_q)

    campos = (
        "receita_bruta",
        "taxas_ml",
        "frete",
        "receita_sem_frete",
        "custo_produtos",
        "receita_sem_custo",
        "margem_contribuicao",
    )

    def totais(df: pd.DataFrame) -> dict[str, float]:
        return {c: (round(float(df[c].sum()), 2) if not df.empty else 0.0) for c in campos}

    agora = totais(atual)
    de_ant = periodo_anterior(de, ate)
    # O período anterior fora do histórico do plano fica sem comparação, e
    # não zerado: zero diria que não houve venda ali.
    anterior = None
    if cortado is None and limita_ao_historico_cabe(acesso, de_ant, de_q):
        anterior = totais(await fluxo_financeiro(pool, acesso.contas, de_ant, de_q))

    return envelope(
        nomes,
        acesso.somada,
        de,
        ate,
        cortado,
        {
            **agora,
            "dias_com_venda": int(len(atual)),
            "variacao_vs_periodo_anterior_pct": (
                {c: variacao(agora[c], anterior[c]) for c in campos} if anterior else None
            ),
            "periodo_anterior": (
                {"de": de_ant, "ate": de, "totais": anterior}
                if anterior
                else "fora do historico do plano"
            ),
        },
    )


def limita_ao_historico_cabe(acesso: Acesso, de: str, ate: str) -> bool:
    """A janela cabe inteira no histórico do plano, sem corte?"""
    try:
        _de, _ate, cortado = limita_ao_historico(acesso.plano, de, ate)
    except HTTPException:
        return False
    return cortado is None


@mcp.tool(
    name="fluxo_financeiro",
    description=(
        "Faturamento dia a dia: para cada dia com pedido pago, receita bruta, comissao, frete, "
        "custo do produto informado e margem de contribuicao. Use para evolucao no tempo, picos "
        "ou quedas. Para um resumo do periodo, prefira visao_geral." + _SOBRE_CONTA
    ),
)
async def tool_fluxo_financeiro(
    date_from: str | None = None, date_to: str | None = None, conta: str | None = None
) -> dict[str, Any]:
    pool, acesso, nomes = await _contexto(conta)
    de, ate, de_q, ate_q, cortado = _janela(acesso, date_from, date_to)
    df = await fluxo_financeiro(pool, acesso.contas, de_q, ate_q)
    return envelope(nomes, acesso.somada, de, ate, cortado, _registros(df))


@mcp.tool(
    name="top_produtos",
    description=(
        "Os produtos e categorias que mais faturaram no periodo, com unidades vendidas e "
        "receita. Use para 'o que mais vendeu'. Para saber quais produtos SUSTENTAM a receita, "
        "use curva_abc." + _SOBRE_CONTA
    ),
)
async def tool_top_produtos(
    date_from: str | None = None,
    date_to: str | None = None,
    n: int = 10,
    conta: str | None = None,
) -> dict[str, Any]:
    try:
        n = validate_n(n)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    pool, acesso, nomes = await _contexto(conta)
    de, ate, de_q, ate_q, cortado = _janela(acesso, date_from, date_to)
    resultado = await top_produtos(pool, acesso.contas, de_q, ate_q, n)
    return envelope(
        nomes,
        acesso.somada,
        de,
        ate,
        cortado,
        {
            "produtos": _registros(resultado["produtos"]),
            "categorias": _registros(resultado["categorias"]),
        },
    )


@mcp.tool(
    name="curva_abc",
    description=(
        "Curva ABC de Pareto por produto: classifica cada produto em A, B ou C pela "
        "participacao acumulada na receita. Classe A e o grupo que sustenta o faturamento."
        + _SOBRE_CONTA
    ),
)
async def tool_curva_abc(
    date_from: str | None = None, date_to: str | None = None, conta: str | None = None
) -> dict[str, Any]:
    pool, acesso, nomes = await _contexto(conta)
    de, ate, de_q, ate_q, cortado = _janela(acesso, date_from, date_to)
    df = await abc_pareto(pool, acesso.contas, de_q, ate_q)
    return envelope(nomes, acesso.somada, de, ate, cortado, _registros(df))


@mcp.tool(
    name="segmentos_de_clientes",
    description=(
        "Segmentacao RFM dos compradores: Champions, Loyal, At Risk, New, Hibernating e "
        "Others, com recencia, frequencia e valor de cada comprador. Responde 'quem compra de "
        "novo' e 'quem sumiu'. Nao confunda com cohort_de_produtos, que e sobre produtos."
        + _SOBRE_CONTA
    ),
)
async def tool_segmentos_de_clientes(
    date_from: str | None = None, date_to: str | None = None, conta: str | None = None
) -> dict[str, Any]:
    pool, acesso, nomes = await _contexto(conta)
    de, ate, de_q, ate_q, cortado = _janela(acesso, date_from, date_to)
    df = await rfm_scores(pool, acesso.contas, de_q, ate_q)
    return envelope(nomes, acesso.somada, de, ate, cortado, _registros(df))


@mcp.tool(
    name="cohort_de_produtos",
    description=(
        "Cohort de PRODUTOS, nao de clientes: agrupa os produtos pelo mes da primeira venda e "
        "mostra quanta receita cada grupo gerou em cada mes seguinte. Para comportamento de "
        "CLIENTES, use segmentos_de_clientes." + _SOBRE_CONTA
    ),
)
async def tool_cohort_de_produtos(
    date_from: str | None = None, date_to: str | None = None, conta: str | None = None
) -> dict[str, Any]:
    pool, acesso, nomes = await _contexto(conta)
    de, ate, de_q, ate_q, cortado = _janela(acesso, date_from, date_to)
    df = await cohort_produto(pool, acesso.contas, de_q, ate_q)
    if df.empty:
        return envelope(nomes, acesso.somada, de, ate, cortado, [])
    return envelope(
        nomes, acesso.somada, de, ate, cortado, df.reset_index().to_dict(orient="records")
    )


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------


class _ComIp:
    """Guarda o IP da chamada para o registro de acesso (mesma regra do painel)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        ip = None
        if scope.get("type") == "http":
            for nome, valor in scope.get("headers", []):
                if nome == b"x-forwarded-for":
                    ip = valor.decode("latin-1")[-200:]
                    break
            if ip is None and scope.get("client"):
                ip = scope["client"][0]
        marca = _ip_da_chamada.set(ip)
        try:
            await self.app(scope, receive, send)
        finally:
            _ip_da_chamada.reset(marca)


class _Delegador:
    """O mesmo ponto de montagem estável do `mcp_server._Delegador`."""

    def __init__(self) -> None:
        self.destino: Any = None

    async def __call__(self, scope, receive, send) -> None:
        if self.destino is None:
            await Response("Servidor MCP ainda nao iniciado", status_code=503)(scope, receive, send)
            return
        await self.destino(scope, receive, send)


delegador = _Delegador()


class _SemBarra:
    """`/mcp/conta`, sem a barra final, que é como o cliente de IA chama.

    Sem esta rota exata, o Starlette não casa o mount de `/mcp/conta` (que
    pede a barra) e cai no de `/mcp`: a chamada iria para a demonstração
    como `/conta` e voltaria 404. Aqui ela segue para o mesmo delegador, já
    com o caminho que o app do MCP espera.
    """

    async def __call__(self, scope, receive, send) -> None:
        raiz = scope.get("root_path", "") + "/mcp/conta"
        await delegador(
            {**scope, "path": raiz + "/", "raw_path": (raiz + "/").encode(), "root_path": raiz},
            receive,
            send,
        )


sem_barra = _SemBarra()


@asynccontextmanager
async def ciclo_de_vida(hosts: list[str], origens: list[str]) -> AsyncIterator[None]:
    app_mcp = _ComIp(
        mcp.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=hosts,
                allowed_origins=origens,
            ),
        )
    )
    async with mcp.session_manager.run():
        delegador.destino = app_mcp
        try:
            yield
        finally:
            delegador.destino = None
