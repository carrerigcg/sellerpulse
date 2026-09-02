"""Fixtures compartilhadas entre todos os testes."""

import sqlite3
from pathlib import Path

import pytest

from src.storage import init_schema


@pytest.fixture
def memory_db():
    """SQLite em memória com schema inicializado.

    Testes que precisam do estado "sem schema" devem instanciar sua própria
    conexão. Os testes de `init_schema` funcionam mesmo assim, pois a função
    é idempotente por design.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def tmp_tokens_file(tmp_path: Path) -> Path:
    """Caminho temporário para tokens.json em testes."""
    return tmp_path / "tokens.json"
