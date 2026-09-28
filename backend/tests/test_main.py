import asyncio

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.main import app, lifespan

from .conftest import TEST_DATABASE_URL


def test_health_check(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_lifespan_sobe_o_worker_por_default(monkeypatch, pg_pool):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("WORKER_IN_PROCESS", raising=False)
    async with lifespan(app):
        tarefas = [t for t in asyncio.all_tasks() if t.get_name() == "sellerpulse-worker"]
        assert len(tarefas) == 1


async def test_lifespan_respeita_o_desligamento_do_worker(monkeypatch, pg_pool):
    """Desligavel importa: os testes de router precisam que ninguem drene a fila."""
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")
    async with lifespan(app):
        assert not [t for t in asyncio.all_tasks() if t.get_name() == "sellerpulse-worker"]


async def test_worker_para_no_shutdown(monkeypatch, pg_pool):
    """Task vazada num shutdown deixaria o processo pendurado no deploy.

    Troca o `worker_loop` de verdade por um fake que, ao notar `parar`, ainda
    leva 0.5s pra sair — tempo de sobra maior que qualquer outro await
    incidental no shutdown (ex.: close_pool()). Sem isso, um worker ocioso sai
    quase instantaneamente assim que agendado, e o teste nao consegue
    distinguir "esperou a task terminar de verdade" de "a task terminou sozinha
    por acaso, empurrada por outro await qualquer no caminho de shutdown".
    """
    import backend.main as main_mod

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("WORKER_IN_PROCESS", raising=False)

    async def _worker_loop_lento(pool, *, parar):
        await parar.wait()
        await asyncio.sleep(0.5)

    monkeypatch.setattr(main_mod, "worker_loop", _worker_loop_lento)

    async with lifespan(app):
        tarefa = next(t for t in asyncio.all_tasks() if t.get_name() == "sellerpulse-worker")
    assert tarefa.done()


async def test_lifespan_recusa_subir_sem_chave_de_cifra(monkeypatch, pg_pool):
    """Deploy com chave faltando tem que morrer no boot, nao no primeiro usuario."""
    from backend.ml import tokens as tokens_mod

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    tokens_mod._fernet.cache_clear()
    with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
        async with lifespan(app):
            pass
    tokens_mod._fernet.cache_clear()
