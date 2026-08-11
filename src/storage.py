"""Camada de persistência SQLite — schema, conexão, repositories."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    date_closed TEXT NOT NULL,
    status TEXT NOT NULL,
    total_amount REAL NOT NULL,
    marketplace_fee REAL NOT NULL,
    shipping_cost REAL NOT NULL,
    buyer_id INTEGER,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(date_closed);

CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    PRIMARY KEY (order_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_order_items_item ON order_items(item_id);

CREATE TABLE IF NOT EXISTS items_cache (
    item_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories_cache (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    status TEXT NOT NULL,
    date_created TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_date ON claims(date_created);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    pdf_path TEXT,
    status TEXT NOT NULL,
    error_message TEXT
);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Abre conexão SQLite, garante schema inicializado, retorna conn."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Cria tabelas (idempotente) e registra versão do schema."""
    conn.executescript(_SCHEMA_SQL)
    existing = conn.execute(
        "SELECT version FROM schema_version WHERE version = ?",
        (SCHEMA_VERSION,),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
        )
    conn.commit()


def upsert_order(conn: sqlite3.Connection, order: dict[str, Any]) -> None:
    """Insere ou atualiza um pedido + seus itens. Idempotente."""
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO orders (
            order_id, date_closed, status, total_amount,
            marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(order_id) DO UPDATE SET
            date_closed = excluded.date_closed,
            status = excluded.status,
            total_amount = excluded.total_amount,
            marketplace_fee = excluded.marketplace_fee,
            shipping_cost = excluded.shipping_cost,
            buyer_id = excluded.buyer_id,
            raw_json = excluded.raw_json,
            fetched_at = excluded.fetched_at
        """,
        (
            order["order_id"],
            order["date_closed"],
            order["status"],
            order["total_amount"],
            order["marketplace_fee"],
            order["shipping_cost"],
            order["buyer_id"],
            order["raw_json"],
            now,
        ),
    )
    conn.execute("DELETE FROM order_items WHERE order_id = ?", (order["order_id"],))
    for item in order.get("items", []):
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            (order["order_id"], item["item_id"], item["quantity"], item["unit_price"]),
        )
    conn.commit()


def get_orders_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> list[sqlite3.Row]:
    """Devolve pedidos com date_closed >= start e < end (ISO8601 strings)."""
    cursor = conn.execute(
        "SELECT * FROM orders WHERE date_closed >= ? AND date_closed < ? ORDER BY date_closed",
        (start_iso, end_iso),
    )
    return cursor.fetchall()


def upsert_item_cache(conn: sqlite3.Connection, item_id: str, title: str, category_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO items_cache (item_id, title, category_id, fetched_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            title = excluded.title,
            category_id = excluded.category_id,
            fetched_at = excluded.fetched_at
        """,
        (item_id, title, category_id, now),
    )
    conn.commit()


def get_item_cache(
    conn: sqlite3.Connection, item_id: str, ttl_days: int = 30
) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM items_cache WHERE item_id = ?", (item_id,)).fetchone()
    if row is None:
        return None
    fetched = datetime.fromisoformat(row["fetched_at"])
    if datetime.now(UTC) - fetched > timedelta(days=ttl_days):
        return None
    return row


def upsert_category_cache(conn: sqlite3.Connection, category_id: str, name: str) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO categories_cache (category_id, name, fetched_at)
        VALUES (?, ?, ?)
        ON CONFLICT(category_id) DO UPDATE SET
            name = excluded.name,
            fetched_at = excluded.fetched_at
        """,
        (category_id, name, now),
    )
    conn.commit()


def get_category_cache(conn: sqlite3.Connection, category_id: str) -> str | None:
    row = conn.execute(
        "SELECT name FROM categories_cache WHERE category_id = ?", (category_id,)
    ).fetchone()
    return row["name"] if row else None


def upsert_claim(conn: sqlite3.Connection, claim: dict[str, Any]) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO claims (claim_id, order_id, status, date_created, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(claim_id) DO UPDATE SET
            order_id = excluded.order_id,
            status = excluded.status,
            date_created = excluded.date_created,
            raw_json = excluded.raw_json,
            fetched_at = excluded.fetched_at
        """,
        (
            claim["claim_id"],
            claim["order_id"],
            claim["status"],
            claim["date_created"],
            claim["raw_json"],
            now,
        ),
    )
    conn.commit()


def get_claims_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM claims WHERE date_created >= ? AND date_created < ? ORDER BY date_created",
        (start_iso, end_iso),
    ).fetchall()


def log_run(
    conn: sqlite3.Connection,
    *,
    week_start: str,
    week_end: str,
    pdf_path: str | None,
    status: str,
    error_message: str | None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO runs (run_at, week_start, week_end, pdf_path, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (datetime.now(UTC).isoformat(), week_start, week_end, pdf_path, status, error_message),
    )
    conn.commit()
    return cursor.lastrowid


def get_last_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
