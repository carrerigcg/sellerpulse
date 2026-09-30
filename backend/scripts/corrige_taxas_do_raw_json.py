"""Recalcula `marketplace_fee` e `shipping_cost` dos pedidos a partir do proprio `raw_json`.

Contexto: ate o fix em `backend/ml/ingest_pg.py`, a ingestao lia campos que nao
existem no payload real do Mercado Livre e gravava taxa e frete como 0 em todo
pedido. O `raw_json` completo de cada pedido ficou guardado, entao os valores
certos saem dele — sem chamar a API do ML de novo (reingerir levaria ~12 min e
gastaria rate limit por dados que ja temos).

A regra de extracao e IMPORTADA de `backend.ml.ingest_pg.extrai_taxa_e_frete`,
a mesma que a ingestao usa. Nao copie a logica pra ca: as duas divergiriam.

Salvaguardas:
- Sellers de demo (`sellers.is_demo`) sao ignorados. Os pedidos deles vem de
  `backend/seed.py`, que grava taxa/frete direto nas colunas e deixa um
  `raw_json` sintetico SEM `sale_fee` — recalcular a partir dele zeraria taxas
  que estao certas.
- Pedido cujo `raw_json` nao tem `sale_fee` em nenhum item e pulado, nao zerado:
  sem o dado nao ha o que recalcular, e sobrescrever com 0 seria repetir o bug.
- So atualiza linha cujo valor muda, dentro de UMA transacao (tudo ou nada).
  Rodar duas vezes e seguro: a segunda nao encontra nada pra mudar.

Uso (da raiz do repo; exige exatamente um dos dois modos):
    python backend/scripts/corrige_taxas_do_raw_json.py --dry-run   # so relata
    python backend/scripts/corrige_taxas_do_raw_json.py --apply     # grava

Le `DATABASE_URL` do ambiente, como `seed_seller.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Rodando como script direto (nao `python -m`), o Python so poe o diretorio
# do proprio arquivo (`backend/scripts`) no sys.path -- sem isto, `import
# backend.ml...` falharia. parents[2] a partir deste arquivo e a raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncpg  # noqa: E402

from backend.ml.ingest_pg import extrai_taxa_e_frete, tem_sale_fee  # noqa: E402

_ZERO = Decimal("0")

_SELECT = """
    SELECT o.seller_id, o.order_id, o.status, o.marketplace_fee, o.shipping_cost, o.raw_json,
           s.is_demo
    FROM orders o
    JOIN sellers s ON s.id = o.seller_id
    ORDER BY o.seller_id, o.order_id
"""

_UPDATE = """
    UPDATE orders SET marketplace_fee = $3, shipping_cost = $4
    WHERE seller_id = $1 AND order_id = $2
"""


@dataclass
class Resumo:
    """Contagens e totais de uma passada. `pagos` e o que o dashboard soma."""

    examinados: int = 0
    demo_ignorados: int = 0
    sem_sale_fee: int = 0
    a_mudar: int = 0
    inalterados: int = 0
    taxa_antes: Decimal = _ZERO
    taxa_depois: Decimal = _ZERO
    taxa_antes_pagos: Decimal = _ZERO
    taxa_depois_pagos: Decimal = _ZERO
    frete_antes: Decimal = _ZERO
    frete_depois: Decimal = _ZERO


def _dec(valor: float) -> Decimal:
    # str() antes de Decimal: Decimal(4.32) herda o ruido binario do float.
    return Decimal(str(valor))


def _como_dict(raw) -> dict:
    # asyncpg devolve jsonb como str, a menos que haja codec registrado.
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


async def corrige_taxas(pool: asyncpg.Pool, *, aplicar: bool) -> Resumo:
    """Recalcula taxa/frete de todos os pedidos de sellers reais.

    Com `aplicar=False` nao escreve nada. Devolve o resumo nos dois casos, com
    totais "antes" e "depois" (o "depois" e o que ficara gravado apos aplicar).
    """
    resumo = Resumo()
    mudancas: list[tuple] = []

    async with pool.acquire() as conn:
        linhas = await conn.fetch(_SELECT)

    for linha in linhas:
        if linha["is_demo"]:
            resumo.demo_ignorados += 1
            continue
        resumo.examinados += 1
        antes_taxa, antes_frete = linha["marketplace_fee"], linha["shipping_cost"]
        raw = _como_dict(linha["raw_json"])

        if tem_sale_fee(raw):
            taxa, frete = extrai_taxa_e_frete(raw)
            depois_taxa, depois_frete = _dec(taxa), _dec(frete)
        else:
            resumo.sem_sale_fee += 1
            depois_taxa, depois_frete = antes_taxa, antes_frete

        resumo.taxa_antes += antes_taxa
        resumo.taxa_depois += depois_taxa
        resumo.frete_antes += antes_frete
        resumo.frete_depois += depois_frete
        if linha["status"] == "paid":
            resumo.taxa_antes_pagos += antes_taxa
            resumo.taxa_depois_pagos += depois_taxa

        # Comparacao numerica (Decimal), nao textual: 10 == 10.00.
        if depois_taxa == antes_taxa and depois_frete == antes_frete:
            resumo.inalterados += 1
        else:
            resumo.a_mudar += 1
            mudancas.append((linha["seller_id"], linha["order_id"], depois_taxa, depois_frete))

    if aplicar and mudancas:
        async with pool.acquire() as conn, conn.transaction():
            await conn.executemany(_UPDATE, mudancas)
    return resumo


def _brl(valor: Decimal) -> str:
    inteiro, _, cent = f"{valor:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{cent}"


def _imprime(resumo: Resumo, *, aplicar: bool) -> None:
    modo = "APLICADO" if aplicar else "DRY-RUN (nada foi gravado)"
    print(f"== corrige_taxas_do_raw_json: {modo} ==")
    print(f"pedidos de sellers reais examinados : {resumo.examinados}")
    print(f"  ja corretos (nada a mudar)        : {resumo.inalterados}")
    rotulo = "alterados" if aplicar else "a alterar"
    print(f"  {rotulo:<34}: {resumo.a_mudar}")
    print(f"  pulados, raw_json sem sale_fee    : {resumo.sem_sale_fee}")
    print(f"pedidos de sellers de demo ignorados: {resumo.demo_ignorados}")
    print("taxa do ML, todos os pedidos")
    print(f"  antes : {_brl(resumo.taxa_antes)}")
    print(f"  depois: {_brl(resumo.taxa_depois)}")
    print("taxa do ML, so pedidos pagos (o que o dashboard soma)")
    print(f"  antes : {_brl(resumo.taxa_antes_pagos)}")
    print(f"  depois: {_brl(resumo.taxa_depois_pagos)}")
    print("frete")
    print(f"  antes : {_brl(resumo.frete_antes)}")
    print(f"  depois: {_brl(resumo.frete_depois)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recalcula taxa e frete dos pedidos a partir do raw_json."
    )
    # Exigir um modo explicito: esquecer uma flag nao pode significar "gravar em
    # producao" nem "nao fazer nada e parecer que funcionou".
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--dry-run", action="store_true", help="Relata o que mudaria, sem gravar.")
    modo.add_argument("--apply", action="store_true", help="Grava as correcoes.")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("ERRO: variavel de ambiente DATABASE_URL nao definida")

    pool = await asyncpg.create_pool(
        database_url, min_size=1, max_size=2, server_settings={"timezone": "UTC"}
    )
    try:
        resumo = await corrige_taxas(pool, aplicar=args.apply)
    finally:
        await pool.close()
    _imprime(resumo, aplicar=args.apply)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
