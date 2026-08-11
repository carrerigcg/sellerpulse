"""Testes do gerador de dados sintéticos determinístico."""

from __future__ import annotations

import hashlib
import sqlite3

from src.demo_data import ANCHOR_TIMESTAMP, write_row


def test_write_row_uses_anchor_timestamp_for_fetched_at(memory_db: sqlite3.Connection) -> None:
    memory_db.executescript(
        "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, fetched_at TEXT NOT NULL)"
    )
    write_row(memory_db, "t", {"id": 1, "name": "A"})
    row = memory_db.execute("SELECT fetched_at FROM t WHERE id = 1").fetchone()
    assert row["fetched_at"] == ANCHOR_TIMESTAMP


def test_write_row_is_deterministic_across_calls(tmp_path) -> None:
    def build_and_hash() -> str:
        db_path = tmp_path / "d.db"
        if db_path.exists():
            db_path.unlink()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, fetched_at TEXT NOT NULL)"
        )
        for i in range(10):
            write_row(conn, "t", {"id": i, "name": f"row-{i}"})
        conn.commit()
        conn.close()
        return hashlib.sha256(db_path.read_bytes()).hexdigest()

    # Prova determinismo same-process. Cross-run precisa de VACUUM
    # (adicionado no generate_demo_db da Task 6).
    assert build_and_hash() == build_and_hash()
