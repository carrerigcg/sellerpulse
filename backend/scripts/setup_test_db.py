"""Cria e prepara o banco de teste do backend.

Aplica `0000_test_auth_stub.sql` (stub do `auth.users`, que no Supabase e
nativo) e `0001_init.sql` (schema multi-tenant). As migrations 0002 (RLS) e
0003 (trigger) NAO sao aplicadas: dependem de `auth.uid()`, funcao exclusiva
do ambiente Supabase. O isolamento entre tenants que os testes exercitam e o
filtro explicito por `seller_id` nas queries, nao a RLS.

Usa asyncpg em vez de `psql` de proposito: asyncpg ja e dependencia do
backend, entao o script funciona sem depender de client Postgres instalado —
util tanto na CI quanto numa maquina Windows sem psql no PATH.

Uso (da raiz do repo):
    python backend/scripts/setup_test_db.py
    TEST_DATABASE_URL=postgresql://... python backend/scripts/setup_test_db.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg

DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/sellerpulse_test"
MIGRATIONS = ("0000_test_auth_stub.sql", "0001_init.sql")


def _admin_url(url: str) -> tuple[str, str]:
    """Devolve (url_do_banco_admin, nome_do_banco_alvo).

    `CREATE DATABASE` nao pode rodar conectado ao banco que esta sendo criado,
    entao a conexao administrativa aponta pro `postgres`.
    """
    parsed = urlparse(url)
    alvo = parsed.path.lstrip("/")
    if not alvo:
        raise SystemExit(f"URL sem nome de banco: {url}")
    return urlunparse(parsed._replace(path="/postgres")), alvo


async def main() -> None:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_URL)
    admin_url, alvo = _admin_url(url)

    admin = await asyncpg.connect(admin_url)
    try:
        existe = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", alvo)
        if existe:
            print(f"banco '{alvo}' ja existe")
        else:
            # UTF8 explicito: o instalador do Postgres no Windows nao oferece
            # locale UTF-8 na lista e o cluster pode nascer em WIN1252, enquanto
            # o Supabase (producao) e UTF8. TEMPLATE template0 e obrigatorio pra
            # poder escolher encoding diferente do padrao do cluster.
            await admin.execute(
                f'CREATE DATABASE "{alvo}" '
                "WITH ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0"
            )
            print(f"banco '{alvo}' criado em UTF8")
    finally:
        await admin.close()

    raiz = Path(__file__).resolve().parent.parent / "migrations"
    recriar = "--recreate" in sys.argv
    conn = await asyncpg.connect(url)
    try:
        encoding = await conn.fetchval("SHOW server_encoding")
        if encoding != "UTF8":
            raise SystemExit(f"banco '{alvo}' esta em {encoding}, esperado UTF8")

        ja_tem_schema = await conn.fetchval(
            "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'sellers'"
        )
        if ja_tem_schema and not recriar:
            # As migrations usam CREATE TABLE puro (sem IF NOT EXISTS), entao
            # reaplicar quebraria. Sair aqui deixa o script idempotente: rodar
            # de novo e um no-op seguro em vez de um erro confuso.
            print(f"banco '{alvo}' ja esta preparado — nada a fazer")
            print("(use --recreate pra recriar o schema do zero)")
            return
        if ja_tem_schema and recriar:
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            await conn.execute("DROP SCHEMA IF EXISTS auth CASCADE;")
            print("schema anterior removido (--recreate)")

        for nome in MIGRATIONS:
            caminho = raiz / nome
            if not caminho.exists():
                raise SystemExit(f"migration nao encontrada: {caminho}")
            await conn.execute(caminho.read_text(encoding="utf-8"))
            print(f"aplicada: {nome}")
        tabelas = await conn.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        print(f"pronto — {tabelas} tabelas em public")
    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
