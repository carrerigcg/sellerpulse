"""Camada de persistência SQLite — schema, conexão, repositories."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()
