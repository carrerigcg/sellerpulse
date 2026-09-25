"""Popula um seller real com dados sinteticos via `backend.seed.seed_postgres`.

Usa `DATABASE_URL` do ambiente (mesmo nome que `backend/db.py` le em
producao) -- serve tanto pro Postgres local de dev quanto, depois, pra
popular um seller de demo no Supabase.

Uso (da raiz do repo):
    python backend/scripts/seed_seller.py <seller_id> [--weeks-back 12]

Falha com mensagem clara se `DATABASE_URL` nao estiver definida, se
`seller_id` nao for um UUID valido, ou se o seller nao existir na tabela
`sellers`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Rodando como script direto (nao `python -m`), o Python so poe o diretorio
# do proprio arquivo (`backend/scripts`) no sys.path -- sem isto, `import
# backend.seed` falharia. parents[2] a partir deste arquivo e a raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncpg  # noqa: E402

from backend.seed import DEFAULT_SEED, seed_postgres  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Popula um seller com dados sinteticos.")
    parser.add_argument("seller_id", help="UUID do seller (coluna sellers.id)")
    parser.add_argument(
        "--weeks-back", type=int, default=12, help="Semanas de historico (default: 12)"
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help="Semente do gerador determinístico"
    )
    parser.add_argument("--n-categories", type=int, default=10)
    parser.add_argument("--n-products", type=int, default=50)
    parser.add_argument("--claim-rate", type=float, default=0.04)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    import os

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("ERRO: variavel de ambiente DATABASE_URL nao definida")

    try:
        seller_id = uuid.UUID(args.seller_id)
    except ValueError:
        raise SystemExit(f"ERRO: seller_id invalido (esperado UUID): {args.seller_id!r}") from None

    pool = await asyncpg.create_pool(
        database_url, min_size=1, max_size=2, server_settings={"timezone": "UTC"}
    )
    try:
        async with pool.acquire() as conn:
            existe = await conn.fetchval("SELECT 1 FROM sellers WHERE id = $1", seller_id)
        if not existe:
            raise SystemExit(f"ERRO: seller {seller_id} nao encontrado na tabela sellers")

        resumo = await seed_postgres(
            pool,
            seller_id,
            seed=args.seed,
            n_categories=args.n_categories,
            n_products=args.n_products,
            weeks_back=args.weeks_back,
            claim_rate=args.claim_rate,
        )
        print(f"seller {seller_id} semeado (weeks_back={args.weeks_back}, seed={args.seed}):")
        for tabela, n in resumo.items():
            print(f"  {tabela}: {n}")
    finally:
        await pool.close()


def main() -> None:
    # SystemExit levantado dentro de `_run` (DATABASE_URL ausente, UUID
    # invalido, seller inexistente) se propaga sozinho por `asyncio.run` --
    # o interpretador ja imprime a mensagem em stderr e sai com codigo 1,
    # entao nao precisa (e nao deve) ser recapturado aqui.
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
