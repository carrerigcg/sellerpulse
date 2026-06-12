"""Fixtures compartilhadas entre todos os testes."""
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def memory_db():
    """Banco SQLite em memória, fresco a cada teste."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def tmp_tokens_file(tmp_path: Path) -> Path:
    """Caminho temporário para tokens.json em testes."""
    return tmp_path / "tokens.json"
