# backend/worker/__main__.py
"""Entrypoint standalone: `python -m backend.worker`.

Existe pra que promover o worker a processo dedicado (Background Worker pago
no Render, container separado, o que for) seja configuracao de plataforma e
nao refactor. Nao e usado hoje.
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from backend.db import close_pool, get_pool
from backend.worker.runner import loop


async def main() -> None:
    load_dotenv()
    pool = await get_pool()
    parar = asyncio.Event()
    try:
        await loop(pool, parar=parar)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
