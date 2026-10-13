"""Testes do servidor MCP da demonstracao.

As ferramentas sao chamadas direto (sao corrotinas comuns), sem subir o
transporte HTTP: o que importa aqui e o contrato -- envelope, janela de datas e
isolamento --, nao o protocolo, que e do SDK e ja e testado la.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend import main, mcp_server
from backend.db import close_pool
from backend.main import app
from backend.mcp_server import AVISO_DEMO, JANELA_PADRAO_DIAS, resolve_janela
from backend.routers._common import MAX_JANELA_DIAS, MAX_N

from .conftest import TEST_DATABASE_URL

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3, 'paid', $4, 10, 5, $5, '{}'::jsonb, now())
"""

# As seis ferramentas e se aceitam `n`. Lista explicita: um nome novo que
# entrar sem passar por aqui nao ganha os testes de contrato de graca.
FERRAMENTAS = [
    ("visao_geral", False),
    ("fluxo_financeiro", False),
    ("top_produtos", True),
    ("curva_abc", False),
    ("segmentos_de_clientes", False),
    ("cohort_de_produtos", False),
]


def _ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "irrelevante-aqui")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")
    # Mesmo motivo de test_routers_demo: o refresh comeca apagando os pedidos
    # do seller de demo, que e o seller que estes testes acabaram de popular.
    monkeypatch.setenv("DEMO_REFRESH_IN_PROCESS", "0")


@pytest.fixture(autouse=True)
async def _pool_global_limpo():
    """Fecha o pool singleton depois de cada teste deste arquivo.

    `backend/db.py` guarda um pool por PROCESSO, e ele fica preso ao event loop
    que o criou. Os testes de router nao sofrem com isso porque o `TestClient`
    roda o lifespan, que abre no startup e fecha no shutdown. Aqui as
    ferramentas chamam `get_pool()` direto, entao sem este teardown o teste
    seguinte herda um pool de um loop ja fechado — e falha com "Event loop is
    closed" num ponto que nao tem nada a ver com a causa.
    """
    yield
    await close_pool()


@pytest.fixture
async def demo(monkeypatch, pg_pool, test_seller):
    """Seller marcado como demo, com o ambiente que o MCP espera."""
    _u, seller_id = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET is_demo = true WHERE id = $1", seller_id)
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_id))
    yield seller_id


async def _chama(nome: str, **kwargs):
    """Executa a ferramenta pelo registro do MCP, como o cliente faria.

    Duas desembrulhadas, pra o teste falar do contrato e nao do SDK:
    `call_tool` devolve um `CallToolResult` (o dict esta em
    `structured_content`), e uma excecao levantada dentro da ferramenta chega
    embrulhada em `UnexpectedToolError` com a original no `__cause__`.
    """
    try:
        resultado = await mcp_server.mcp.call_tool(nome, kwargs)
    except Exception as exc:
        raise (exc.__cause__ or exc) from None
    return resultado.structured_content


# --------------------------------------------------------------------------
# Contrato das ferramentas
# --------------------------------------------------------------------------


async def test_as_seis_ferramentas_estao_registradas():
    nomes = {t.name for t in await mcp_server.mcp.list_tools()}
    assert nomes == {n for n, _ in FERRAMENTAS}


async def test_nenhuma_ferramenta_aceita_seller_id():
    """O isolamento do tenant e por construcao, igual ao router /demo.

    Se uma ferramenta aceitasse seller_id, o conector publico viraria leitura
    arbitraria do faturamento de qualquer vendedor cadastrado. Este teste trava
    a invariante no nome do parametro, nao numa URL.
    """
    for t in await mcp_server.mcp.list_tools():
        props = (t.input_schema or {}).get("properties", {})
        assert not [p for p in props if "seller" in p.lower()], f"{t.name} expoe seller_id"


@pytest.mark.parametrize(("nome", "_aceita_n"), FERRAMENTAS)
async def test_toda_ferramenta_devolve_o_envelope(demo, pg_pool, nome, _aceita_n):
    """Aviso e periodo em TODA resposta.

    O aviso nao e decoracao: sem ele a IA apresenta o numero ficticio como
    faturamento real de alguem, e um numero com cara de verdade e mais
    perigoso que um erro obvio.
    """
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, demo, datetime(2026, 7, 15, tzinfo=UTC), 250.0, 1)
    out = await _chama(nome, date_from="2026-07-01", date_to="2026-07-31")
    assert out["aviso"] == AVISO_DEMO
    assert out["periodo"] == {"de": "2026-07-01", "ate": "2026-07-31"}
    assert "dados" in out


# --------------------------------------------------------------------------
# A janela de datas
# --------------------------------------------------------------------------


async def test_o_ultimo_dia_da_janela_entra_no_resultado(demo, pg_pool):
    """O teste que prova a conversao de `date_to` inclusivo -> exclusivo.

    As funcoes de `backend/analytics/` tratam `date_to` como fim EXCLUSIVO.
    Quem pergunta "ate 31 de julho" quer o dia 31 contado. Sem somar um dia na
    borda, o pedido do ultimo dia some e a resposta sai plausivel e errada.

    Mutacao que o derruba: tirar o `+ timedelta(days=1)` de `resolve_janela`.
    """
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, demo, datetime(2026, 7, 31, 23, tzinfo=UTC), 777.0, 1)
    out = await _chama("fluxo_financeiro", date_from="2026-07-01", date_to="2026-07-31")
    receitas = [linha["receita_bruta"] for linha in out["dados"]]
    assert 777.0 in receitas, "o pedido do ultimo dia da janela nao apareceu"


def test_sem_datas_usa_a_janela_padrao():
    """Sem padrao a IA inventa datas, e inventa diferente a cada chamada."""
    de, ate, _de_q, _ate_q = resolve_janela(None, None)
    assert ate == date.today().isoformat()
    assert date.fromisoformat(ate) - date.fromisoformat(de) == timedelta(days=JANELA_PADRAO_DIAS)


def test_a_consulta_recebe_o_dia_seguinte_ao_fim_pedido():
    """O par mostrado e o par consultado divergem de proposito, por um dia."""
    de, ate, de_q, ate_q = resolve_janela("2026-07-01", "2026-07-31")
    assert (de, ate) == ("2026-07-01", "2026-07-31")
    assert de_q == "2026-07-01"
    assert ate_q == "2026-08-01"


def test_janela_invertida_e_erro_legivel():
    with pytest.raises(ValueError, match="posterior"):
        resolve_janela("2026-08-01", "2026-07-01")


def test_data_malformada_diz_o_formato_esperado():
    """A IA le a mensagem e corrige a chamada — por isso ela cita o formato."""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        resolve_janela("31/07/2026", None)


def test_a_janela_respeita_o_teto_do_rest():
    """O MCP e a MESMA porta publica do /demo, com outro protocolo.

    Sem este teto eu abriria pelo MCP exatamente o que `routers/_common.py`
    fechou no REST: janela arbitraria numa porta sem autenticacao, num plano
    gratuito que hiberna.
    """
    fim = date.today()
    inicio = fim - timedelta(days=MAX_JANELA_DIAS + 10)
    with pytest.raises(ValueError, match="no maximo|máximo"):
        resolve_janela(inicio.isoformat(), fim.isoformat())


async def test_top_produtos_respeita_o_teto_de_n(demo):
    with pytest.raises(ValueError, match=str(MAX_N)):
        await _chama("top_produtos", n=MAX_N + 1)


# --------------------------------------------------------------------------
# Isolamento e montagem
# --------------------------------------------------------------------------


async def test_ferramenta_so_le_o_seller_de_demo(demo, pg_pool, outro_seller):
    """Pedido de outro tenant nao pode vazar pela ferramenta."""
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, demo, datetime(2026, 7, 15, tzinfo=UTC), 100.0, 1)
        await conn.execute(_INSERT_ORDER, 2, seller_b, datetime(2026, 7, 16, tzinfo=UTC), 999.0, 2)
    out = await _chama("fluxo_financeiro", date_from="2026-07-01", date_to="2026-07-31")
    receitas = [linha["receita_bruta"] for linha in out["dados"]]
    assert receitas == [100.0]


async def test_sem_demo_configurada_a_ferramenta_explica(monkeypatch, pg_pool):
    """Falha de configuracao vira mensagem legivel, nao erro cru do FastAPI."""
    _ambiente(monkeypatch)
    monkeypatch.delenv("DEMO_SELLER_ID", raising=False)
    with pytest.raises(ValueError, match="indisponivel|indisponível"):
        await _chama("fluxo_financeiro", date_from="2026-07-01", date_to="2026-07-31")


async def test_seller_nao_marcado_como_demo_e_recusado(monkeypatch, pg_pool, outro_seller):
    """A checagem do is_demo e o que impede um env var errado servir dado real."""
    _ub, seller_b = outro_seller
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_b))
    with pytest.raises(ValueError, match="indisponivel|indisponível"):
        await _chama("fluxo_financeiro", date_from="2026-07-01", date_to="2026-07-31")


def test_o_mount_nao_derruba_as_rotas_que_ja_existiam(monkeypatch):
    """Um mount casa com tudo abaixo do prefixo; rota declarada depois sumiria."""
    _ambiente(monkeypatch)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_mcp_montado_em_mcp():
    """O caminho interno e "/" de proposito: o padrao do SDK daria /mcp/mcp."""
    assert "/mcp" in [getattr(r, "path", None) for r in app.routes]


def _rpc(c, metodo: str, params: dict, ident: int = 1):
    """Uma chamada JSON-RPC pelo HTTP, como o cliente de IA faz.

    A resposta do transporte streamable vem em SSE, entao o JSON esta na linha
    `data:`.
    """
    r = c.post(
        "/mcp",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={"jsonrpc": "2.0", "id": ident, "method": metodo, "params": params},
    )
    if r.status_code != 200:
        return r.status_code, r.text
    for linha in r.text.splitlines():
        if linha.startswith("data:"):
            return 200, json.loads(linha[5:].strip())
    return 200, r.text


def test_o_mount_serve_o_protocolo_de_verdade(monkeypatch):
    """O unico teste que prova que o MOUNT funciona, nao so as ferramentas.

    Os outros chamam as corrotinas direto. Este faz o handshake e lista as
    ferramentas pelo HTTP — e e o que pegaria o caminho montado errado, o
    gerenciador de sessao nao aberto, ou o `streamable_http_path` no default.
    """
    _ambiente(monkeypatch)
    # O TestClient manda `Host: testserver`, que nao esta nos defaults. Sem
    # isto o SDK devolve 421 — exatamente o que aconteceria em producao se o
    # host do Render nao estivesse na lista.
    monkeypatch.setattr(main, "_MCP_HOSTS", ["testserver"])
    with TestClient(app) as c:
        st, ini = _rpc(
            c,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        )
        assert st == 200, ini
        assert ini["result"]["serverInfo"]["name"] == "sellerpulse-demo"

        st, lst = _rpc(c, "tools/list", {}, 2)
        assert st == 200, lst
        assert {t["name"] for t in lst["result"]["tools"]} == {n for n, _ in FERRAMENTAS}


def test_host_fora_da_lista_e_recusado(monkeypatch):
    """A protecao contra DNS-rebinding tem que estar LIGADA de verdade.

    Desligada por engano, o servidor atenderia qualquer Host — e o teste acima
    continuaria verde, porque ele so prova o caminho feliz.
    """
    _ambiente(monkeypatch)
    monkeypatch.setattr(main, "_MCP_HOSTS", ["testserver"])
    with TestClient(app) as c:
        r = c.post(
            "/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Host": "atacante.example",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert r.status_code == 421
