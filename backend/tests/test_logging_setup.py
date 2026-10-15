# backend/tests/test_logging_setup.py
"""Testes da configuracao de logging do backend.

Esta suite existe por causa de um modo de falha que nenhum teste pegava: o
logging do processo funcionava por EFEITO COLATERAL do construtor do `FastMCP`,
que chama `logging.basicConfig(format="%(message)s")` quando
`backend/mcp_server.py` e importado. Logo:

- tirar o MCP do caminho de import apagaria os logs, em silencio;
- sem nivel no inicio da linha, o Render marcava todo `warning`/`exception`
  nosso como `info` -- em 25 dias de producao, nenhuma linha da aplicacao
  chegou marcada como erro.

Entao os dois testes que carregam peso aqui sao o que prova que a configuracao
e NOSSA (desloca a do SDK) e o que le a linha renderizada de verdade para
conferir que o nivel vem primeiro. O resto e guarda contra regressao boba.
"""

from __future__ import annotations

import logging

import pytest

from backend.logging_setup import FORMATO, NIVEL_PADRAO, configura_logging


@pytest.fixture(autouse=True)
def _restaura_logging():
    """Devolve o estado global do logging ao fim de cada teste.

    Sem isto, um teste daqui deixaria o handler dele pendurado na raiz e
    mudaria o comportamento de captura de qualquer teste que rodasse depois --
    e a suite inteira compartilha esse estado.
    """
    raiz = logging.getLogger()
    handlers = list(raiz.handlers)
    nivel = raiz.level
    yield
    raiz.handlers = handlers
    raiz.setLevel(nivel)


def _formatos_na_raiz() -> list[str | None]:
    return [
        h.formatter._fmt if h.formatter is not None else None for h in logging.getLogger().handlers
    ]


def test_desloca_a_configuracao_acidental_do_sdk_do_mcp():
    """O handler que o SDK pendura na raiz some; o nosso fica, sozinho.

    Simula a ordem real: `import backend.mcp_server` roda primeiro e deixa um
    handler com `format="%(message)s"`; so depois `backend/main.py` chama a
    nossa configuracao.
    """
    raiz = logging.getLogger()
    raiz.handlers = []
    do_sdk = logging.StreamHandler()
    do_sdk.setFormatter(logging.Formatter("%(message)s"))
    raiz.addHandler(do_sdk)

    configura_logging()

    assert _formatos_na_raiz() == [FORMATO]


def test_nivel_vem_primeiro_na_linha_renderizada(capsys):
    """O que o Render le. Assercao na SAIDA, nao na configuracao.

    Conferir o formato configurado nao bastaria: o que determina se um
    traceback de producao e encontravel e o primeiro token da linha que sai.
    """
    configura_logging()

    logging.getLogger("backend.teste_de_formato").warning("fila inacessivel")

    linha = capsys.readouterr().err.strip()
    assert linha.startswith("WARNING"), linha
    assert linha == "WARNING backend.teste_de_formato: fila inacessivel"


def test_chamar_duas_vezes_nao_duplica_a_linha(capsys):
    """Idempotencia medida pelo sintoma: a mensagem aparece UMA vez.

    Dois handlers na raiz nao quebram nada visivel na configuracao -- o
    estrago e cada linha de log em dobro no painel.
    """
    configura_logging()
    configura_logging()

    logging.getLogger("backend.teste_de_duplicata").warning("uma vez so")

    assert capsys.readouterr().err.count("uma vez so") == 1


def test_log_level_do_ambiente_e_respeitado(monkeypatch, capsys):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    configura_logging()
    logging.getLogger("backend.teste_de_nivel").debug("detalhe")

    assert logging.getLogger().level == logging.DEBUG
    assert "detalhe" in capsys.readouterr().err


def test_info_passa_no_nivel_padrao(monkeypatch, capsys):
    """O `LOG_LEVEL` tem que estar AUSENTE pra este teste significar algo."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    configura_logging()
    logging.getLogger("backend.teste_de_padrao").info("nascimento do worker")

    assert capsys.readouterr().err.count("nascimento do worker") == 1


def test_log_level_invalido_nao_derruba_o_boot(monkeypatch, capsys):
    """Typo em variavel de ambiente degrada pro padrao, com aviso.

    O boot do backend acontece no deploy do Render. Levantar aqui trocaria
    "log em nivel errado" por "servico fora do ar", e a assimetria nao
    justifica.
    """
    monkeypatch.setenv("LOG_LEVEL", "verboso")

    configura_logging()

    assert logging.getLogger().level == logging.getLevelName(NIVEL_PADRAO)
    erro = capsys.readouterr().err
    assert "verboso" in erro
    assert "WARNING" in erro


def test_nao_mexe_nos_loggers_da_uvicorn():
    """`force=True` limpa a RAIZ, e a uvicorn nao pendura handler nela.

    As linhas de acesso (`INFO:     GET /... 200 OK`) saem por um handler do
    logger `uvicorn.access`, com `propagate=False`. Se um dia a nossa
    configuracao passar a limpar isso tambem, o log de acesso morre.
    """
    acesso = logging.getLogger("uvicorn.access")
    original, propagava = list(acesso.handlers), acesso.propagate
    try:
        dela = logging.StreamHandler()
        acesso.handlers = [dela]
        acesso.propagate = False

        configura_logging()

        assert acesso.handlers == [dela]
        assert acesso.propagate is False
    finally:
        acesso.handlers = original
        acesso.propagate = propagava
