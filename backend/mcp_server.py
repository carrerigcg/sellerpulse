# backend/mcp_server.py
"""Servidor MCP da demonstracao — expoe as analises pra Claude e ChatGPT.

Fase 1 do design em `docs/specs/2026-10-13-mcp-server-design.md`: seis
ferramentas somente-leitura sobre o seller de demonstracao, sem autenticacao.

Este modulo e CASCA. Toda a analise vive em `backend/analytics/` e nao e
reimplementada aqui — as ferramentas chamam as mesmas funcoes que os endpoints
REST chamam, e qualquer divergencia entre MCP e tela seria bug.

As tres travas de `routers/demo.py` valem igual aqui, porque esta e a MESMA
porta sem autenticacao, so que com outro protocolo:

1. So leitura. Nenhuma ferramenta escreve.
2. O `seller_id` vem de variavel de ambiente no servidor e e conferido contra
   `is_demo`. NUNCA e parametro de ferramenta — aceitar do cliente viraria
   leitura arbitraria do faturamento de qualquer vendedor cadastrado.
3. Entrada limitada pelos MESMOS tetos do REST (`routers/_common.py`). Sem
   isso, eu abriria pelo MCP exatamente o que foi fechado no REST: janela
   arbitraria e `n` arbitrario numa porta publica, num free tier que hiberna.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from fastapi import HTTPException
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import Response

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos
from backend.analytics.segmentation_pg import abc_pareto, cohort_produto, rfm_scores
from backend.db import get_pool

# `_seller_de_demo` e privado e mora num router, o que e uma importacao torta
# pra um modulo que nao e router. E deliberado: ela carrega a checagem do
# `is_demo` que protege a porta publica, e duplicar essa checagem aqui
# significaria que um dia as duas divergem — e a que diverge pra pior serve
# faturamento real pra internet. Uma copia so, mesmo torta, e mais segura.
from backend.routers._common import validate_n, validate_window
from backend.routers.demo import _seller_de_demo

AVISO_DEMO = "Dados de demonstracao ficticios, nao uma loja real."

# Janela padrao quando a IA nao informa datas. 90 dias e a janela mais larga
# que o frontend pede (`periodoPadrao()`), entao e o que a pessoa ja ve na tela.
# Sem padrao, a IA inventa datas — e inventa diferente a cada chamada.
JANELA_PADRAO_DIAS = 90

_INSTRUCOES = f"""\
Analises de vendas do SellerPulse para um vendedor do Mercado Livre.

IMPORTANTE: {AVISO_DEMO} Os numeros sao de uma loja sintetica criada para
demonstracao. Nunca os apresente como resultado real de alguem.

Margem aqui e margem de CONTRIBUICAO: receita bruta menos a comissao do
Mercado Livre menos o frete. Nao e lucro — o custo do produto nao entra,
porque o SellerPulse nao o conhece. Nao chame de lucro.

As datas sao inclusivas nos dois lados: `date_to` e o ultimo dia contado.
Omitindo as datas, a janela e dos ultimos {JANELA_PADRAO_DIAS} dias.

O servidor roda num plano gratuito que hiberna apos ~15 minutos parado. A
primeira chamada depois de uma pausa pode levar ~25 segundos. Isso e normal:
aguarde em vez de concluir que esta fora do ar.
"""

mcp = MCPServer(
    name="sellerpulse-demo",
    title="SellerPulse (demonstracao)",
    instructions=_INSTRUCOES,
)


# --------------------------------------------------------------------------
# Janela de datas
# --------------------------------------------------------------------------


def resolve_janela(date_from: str | None, date_to: str | None) -> tuple[str, str, str, str]:
    """Normaliza a janela pedida pela IA pra janela que a analise espera.

    Devolve `(de, ate_inclusivo, de_query, ate_query)`: os dois primeiros pra
    mostrar na resposta, os dois ultimos pra passar pras funcoes de analise.

    Duas conversoes acontecem aqui, e as duas sao fonte de bug silencioso:

    1. **`date_to` e INCLUSIVO pra quem pergunta, EXCLUSIVO pra analise.**
       Quando alguem diz "ate 13 de outubro", quer o dia 13 contado. As funcoes
       de `backend/analytics/` tratam `date_to` como fim exclusivo (esta nas
       docstrings delas). Sem somar um dia aqui, TODA resposta perderia o
       ultimo dia da janela — e o numero sairia plausivel, so que errado.
       Decisao travada do produto em 2026-10-01: o seletor e exclusivo e fica
       assim; quem converte e a borda.

    2. **Sem datas, usa os ultimos `JANELA_PADRAO_DIAS` dias.**

    Levanta `ValueError` com mensagem legivel pra entrada invalida — a IA le
    essa mensagem e corrige a chamada. `validate_window` levanta
    `HTTPException` porque nasceu pros routers REST; traduzimos aqui em vez de
    duplicar os tetos, pra ter uma regra so.
    """
    ate_incl = date.today() if date_to is None else _parse_dia(date_to, "date_to")
    de = (
        ate_incl - timedelta(days=JANELA_PADRAO_DIAS)
        if date_from is None
        else _parse_dia(date_from, "date_from")
    )

    if de > ate_incl:
        raise ValueError(
            f"date_from ({de.isoformat()}) e posterior a date_to ({ate_incl.isoformat()})."
        )

    # A analise quer o fim exclusivo: o dia seguinte ao ultimo dia contado.
    ate_excl = ate_incl + timedelta(days=1)
    try:
        de_q, ate_q = validate_window(de.isoformat(), ate_excl.isoformat())
    except HTTPException as exc:  # tetos do REST, mensagem pra IA
        raise ValueError(str(exc.detail)) from exc
    return de.isoformat(), ate_incl.isoformat(), de_q, ate_q


def _parse_dia(valor: str, campo: str) -> date:
    """`YYYY-MM-DD` -> date, com mensagem util pro campo errado."""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{campo} invalida: {valor!r}. Use o formato YYYY-MM-DD, por exemplo 2026-10-13."
        ) from exc


def envelope(de: str, ate: str, dados: Any) -> dict[str, Any]:
    """Resposta padrao das ferramentas.

    O `aviso` nao e decoracao. Sem ele a IA apresenta "R$ 331.551" como
    faturamento real de alguem — e um numero com cara de verdade e mais
    perigoso que um erro obvio. E a mesma funcao da faixa amarela no painel.
    """
    return {"aviso": AVISO_DEMO, "periodo": {"de": de, "ate": ate}, "dados": dados}


async def _contexto() -> tuple[Any, uuid.UUID]:
    """Pool e seller da demo, com a checagem de `is_demo` feita por `demo.py`."""
    pool = await get_pool()
    try:
        seller_id = await _seller_de_demo(pool)
    except HTTPException as exc:
        raise ValueError(f"Demonstracao indisponivel: {exc.detail}") from exc
    return pool, seller_id


def _registros(df: pd.DataFrame) -> list[dict]:
    return df.to_dict(orient="records") if not df.empty else []


# --------------------------------------------------------------------------
# As seis ferramentas
# --------------------------------------------------------------------------


@mcp.tool(
    name="visao_geral",
    description=(
        "Resumo do periodo: receita bruta, custos do Mercado Livre (comissao + frete), "
        "margem de contribuicao, e a variacao contra o periodo anterior de mesma duracao. "
        "Comece por esta ferramenta quando a pergunta for ampla, do tipo 'como foi o mes' "
        "ou 'como vai o negocio' — ela responde em uma chamada so. Margem de contribuicao "
        "NAO e lucro: o custo do produto nao entra."
    ),
)
async def visao_geral(date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    pool, seller_id = await _contexto()

    atual = await fluxo_financeiro(pool, seller_id, de_q, ate_q)

    # Periodo anterior de MESMA duracao, imediatamente antes — e a mesma regra
    # que `janelaAnterior` usa no frontend, entao tela e MCP contam igual.
    dias = (date.fromisoformat(ate) - date.fromisoformat(de)).days + 1
    de_ant = (date.fromisoformat(de) - timedelta(days=dias)).isoformat()
    anterior = await fluxo_financeiro(pool, seller_id, de_ant, de_q)

    def soma(df: pd.DataFrame, col: str) -> float:
        return round(float(df[col].sum()), 2) if not df.empty else 0.0

    def variacao(agora: float, antes: float) -> float | None:
        # None, nao 0: sem base de comparacao, "0%" seria uma afirmacao falsa.
        if antes == 0:
            return None
        return round((agora - antes) / antes * 100, 1)

    campos = ("receita_bruta", "taxas_ml", "frete", "margem_contribuicao")
    agora = {c: soma(atual, c) for c in campos}
    antes = {c: soma(anterior, c) for c in campos}

    return envelope(
        de,
        ate,
        {
            "receita_bruta": agora["receita_bruta"],
            "custos_mercado_livre": round(agora["taxas_ml"] + agora["frete"], 2),
            "comissao_mercado_livre": agora["taxas_ml"],
            "frete": agora["frete"],
            "margem_contribuicao": agora["margem_contribuicao"],
            "dias_com_venda": int(len(atual)),
            "variacao_vs_periodo_anterior_pct": {c: variacao(agora[c], antes[c]) for c in campos},
            "periodo_anterior": {"de": de_ant, "ate": de, "totais": antes},
        },
    )


@mcp.tool(
    name="fluxo_financeiro",
    description=(
        "Faturamento dia a dia: para cada dia com pedido pago, receita bruta, comissao do "
        "Mercado Livre, frete e margem de contribuicao. Use quando a pergunta for sobre "
        "evolucao no tempo, picos ou quedas. Para um resumo do periodo, prefira visao_geral."
    ),
)
async def tool_fluxo_financeiro(
    date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    pool, seller_id = await _contexto()
    df = await fluxo_financeiro(pool, seller_id, de_q, ate_q)
    return envelope(de, ate, _registros(df))


@mcp.tool(
    name="top_produtos",
    description=(
        "Os produtos e categorias que mais faturaram no periodo, com unidades vendidas e "
        "receita. Use para 'o que mais vendeu'. Para saber quais produtos SUSTENTAM a "
        "receita (e quais sao cauda longa), use curva_abc."
    ),
)
async def tool_top_produtos(
    date_from: str | None = None, date_to: str | None = None, n: int = 10
) -> dict[str, Any]:
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    try:
        n = validate_n(n)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    pool, seller_id = await _contexto()
    resultado = await top_produtos(pool, seller_id, de_q, ate_q, n)
    return envelope(
        de,
        ate,
        {
            "produtos": _registros(resultado["produtos"]),
            "categorias": _registros(resultado["categorias"]),
        },
    )


@mcp.tool(
    name="curva_abc",
    description=(
        "Curva ABC de Pareto por produto: classifica cada produto em A, B ou C pela "
        "participacao acumulada na receita. Classe A e o grupo que sustenta o faturamento. "
        "Use para 'quais produtos sustentam a receita', 'onde esta concentrada minha venda' "
        "ou decisoes de estoque."
    ),
)
async def tool_curva_abc(
    date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    pool, seller_id = await _contexto()
    df = await abc_pareto(pool, seller_id, de_q, ate_q)
    return envelope(de, ate, _registros(df))


@mcp.tool(
    name="segmentos_de_clientes",
    description=(
        "Segmentacao RFM dos compradores: Champions, Loyal, At Risk, New, Hibernating e "
        "Others, com recencia, frequencia e valor de cada comprador. Esta e a ferramenta "
        "que responde 'quem compra de novo' e 'quem sumiu sem avisar' — a frequencia diz "
        "quem voltou. Nao confunda com cohort_de_produtos, que e sobre produtos."
    ),
)
async def tool_segmentos_de_clientes(
    date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    pool, seller_id = await _contexto()
    df = await rfm_scores(pool, seller_id, de_q, ate_q)
    return envelope(de, ate, _registros(df))


@mcp.tool(
    name="cohort_de_produtos",
    description=(
        "Cohort de PRODUTOS, nao de clientes: agrupa os produtos pelo mes da primeira venda "
        "e mostra quanta receita cada grupo gerou em cada mes seguinte. Responde 'produto "
        "novo vende e some, ou continua faturando?'. Para comportamento de CLIENTES "
        "(quem voltou a comprar), use segmentos_de_clientes."
    ),
)
async def tool_cohort_de_produtos(
    date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    de, ate, de_q, ate_q = resolve_janela(date_from, date_to)
    pool, seller_id = await _contexto()
    df = await cohort_produto(pool, seller_id, de_q, ate_q)
    # Vazio precisa de tratamento proprio: `cohort_produto` devolve um DataFrame
    # sem index nomeado quando nao ha vendas, e `reset_index()` ali geraria uma
    # coluna "index" espuria. Mesmo caso tratado em `routers/demo.py`.
    if df.empty:
        return envelope(de, ate, [])
    return envelope(de, ate, df.reset_index().to_dict(orient="records"))


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------


class _Delegador:
    """Ponto de montagem estavel que aponta pro ASGI MCP do ciclo de vida atual.

    Existe por uma restricao do SDK: `StreamableHTTPSessionManager.run()` so
    pode ser chamado UMA vez por instancia, e o gerenciador nasce junto com o
    ASGI em `streamable_http_app()`. Montar o ASGI direto no import amarraria o
    processo inteiro a um unico ciclo de vida — o segundo startup do mesmo app
    estoura com "can only be called once per instance".

    Em producao isso parece inofensivo (o lifespan roda uma vez), mas nao e:
    derrubou a suite de testes inteira, que sobe o app varias vezes, e
    significa que o app nao sobrevive a um restart do proprio lifespan.

    A solucao: o mount aponta pra este objeto, que e estavel, e o lifespan
    troca o `destino` por um ASGI novinho a cada ciclo.
    """

    def __init__(self) -> None:
        self.destino: Any = None

    async def __call__(self, scope, receive, send) -> None:
        if self.destino is None:
            # Antes do startup ou depois do shutdown. 503 e a resposta honesta:
            # o endereco existe, o servico ainda nao.
            resposta = Response("Servidor MCP ainda nao iniciado", status_code=503)
            await resposta(scope, receive, send)
            return
        await self.destino(scope, receive, send)


delegador = _Delegador()


@asynccontextmanager
async def ciclo_de_vida(hosts: list[str], origens: list[str]) -> AsyncIterator[None]:
    """Sobe um ASGI MCP novo e o liga no mount pela duracao do ciclo.

    Chamado pelo lifespan de `main.py`. Constroi primeiro (o que cria o
    gerenciador de sessao), roda o gerenciador, e so entao liga o destino —
    ligar antes serviria requisicoes contra um gerenciador parado.
    """
    app_mcp = monta_app(hosts, origens)
    async with mcp.session_manager.run():
        delegador.destino = app_mcp
        try:
            yield
        finally:
            delegador.destino = None


def monta_app(hosts: list[str], origens: list[str]):
    """ASGI do MCP, pronto pra `app.mount("/mcp", ...)`.

    Dois detalhes que, errados, quebram so em producao:

    1. `streamable_http_path="/"`. O padrao do SDK e "/mcp"; montando em "/mcp"
       o endereco final viraria `/mcp/mcp`.
    2. A protecao contra DNS-rebinding vem LIGADA e, sem `allowed_hosts`, so
       responde a localhost — funcionaria na maquina do dev e falharia no
       Render. Host e Origin sao listas SEPARADAS porque o SDK as trata
       diferente: Host ausente ou fora da lista e recusado (421), enquanto
       Origin ausente passa e so e checado quando vem (403). Quem decide o
       conteudo das listas e `main.py`, que conhece o ambiente.
    """
    return mcp.streamable_http_app(
        streamable_http_path="/",
        # Sem estado entre chamadas: o Render hiberna e reinicia a instancia, e
        # sessao guardada em memoria morreria junto. Cada chamada se basta.
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origens,
        ),
    )
