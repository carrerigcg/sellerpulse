"""Exclui a conta de um vendedor a pedido dele, guardando o que a lei manda guardar.

Os Termos (seção 12) e a Política (seção 7) prometem apagar a conta e os dados em
até 30 dias, e manter por 5 anos a prova do aceite e os registros da cobrança.
Apagar `auth.users` cascateia para `sellers` e daí para todo dado da loja; a 0021
tirou a chave estrangeira de `aceites_de_termos` e `checkouts` para eles ficarem.

Salvaguardas:
- Recusa conta de demonstração.
- Recusa quem ainda tem assinatura recorrente no Asaas: apagar a conta não para
  a cobrança. Cancele antes (`docs/operacao.md`, seção 9).
- `--dry-run` só relata o que sairia e o que fica. Tudo numa transação.

Uso (da raiz do repo; exige exatamente um dos dois modos):
    python backend/scripts/exclui_conta.py --email pessoa@exemplo.com --dry-run
    python backend/scripts/exclui_conta.py --email pessoa@exemplo.com --apply

Le `DATABASE_URL` do ambiente, como `seed_seller.py`. Em produção, só com o ok do
Guilherme.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Rodando como script direto, o Python só põe `backend/scripts` no sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncpg  # noqa: E402

# O que sobrevive à exclusão, e por quê, em docs/specs/2026-11-03-exclusao-de-conta-design.md.
PRESERVADAS = ("aceites_de_termos", "checkouts")


class ExclusaoRecusada(Exception):
    pass


@dataclass
class Relatorio:
    user_id: object
    seller_id: object
    apagadas: dict[str, int] = field(default_factory=dict)
    preservadas: dict[str, int] = field(default_factory=dict)
    aplicado: bool = False


async def _tabelas_com_seller(conn) -> list[str]:
    # Lida do banco, e não de uma lista: tabela nova de tenant entra no relatório
    # sem ninguém lembrar de atualizar este script.
    linhas = await conn.fetch(
        """
        SELECT table_name FROM information_schema.columns
         WHERE table_schema = 'public' AND column_name = 'seller_id'
           AND table_name <> 'contas_excluidas'
         ORDER BY table_name
        """
    )
    return [linha["table_name"] for linha in linhas]


async def exclui_conta(conn, email: str, *, aplicar: bool) -> Relatorio:
    async with conn.transaction():
        conta = await conn.fetchrow(
            """
            SELECT u.id AS user_id, s.id AS seller_id, s.is_demo
              FROM auth.users u JOIN sellers s ON s.user_id = u.id
             WHERE lower(u.email) = lower($1)
            """,
            email,
        )
        if conta is None:
            raise ExclusaoRecusada(f"nenhuma conta com o e-mail {email}")
        if conta["is_demo"]:
            raise ExclusaoRecusada("é a conta de demonstração")
        recorrente = await conn.fetchval(
            """
            SELECT asaas_assinatura FROM assinaturas
             WHERE seller_id = $1 AND asaas_assinatura IS NOT NULL AND cancelada_em IS NULL
            """,
            conta["seller_id"],
        )
        if recorrente:
            raise ExclusaoRecusada(
                f"assinatura {recorrente} ainda ativa no Asaas: cancele antes de excluir"
            )

        relatorio = Relatorio(conta["user_id"], conta["seller_id"])
        for tabela in await _tabelas_com_seller(conn):
            total = await conn.fetchval(
                f"SELECT count(*) FROM {tabela} WHERE seller_id = $1", conta["seller_id"]
            )
            destino = relatorio.preservadas if tabela in PRESERVADAS else relatorio.apagadas
            destino[tabela] = total
        relatorio.preservadas["registros_de_acesso"] = await conn.fetchval(
            "SELECT count(*) FROM registros_de_acesso WHERE user_id = $1", conta["user_id"]
        )

        if aplicar:
            await conn.execute(
                "INSERT INTO contas_excluidas (seller_id, user_id) VALUES ($1, $2)",
                conta["seller_id"],
                conta["user_id"],
            )
            await conn.execute("DELETE FROM auth.users WHERE id = $1", conta["user_id"])
            relatorio.aplicado = True
        return relatorio


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--dry-run", action="store_true")
    modo.add_argument("--apply", action="store_true")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        relatorio = await exclui_conta(conn, args.email, aplicar=args.apply)
    except ExclusaoRecusada as erro:
        sys.exit(f"recusado: {erro}")
    finally:
        await conn.close()
    print(f"user_id {relatorio.user_id}  seller_id {relatorio.seller_id}")
    print("apagado:" if relatorio.aplicado else "sairia:")
    for tabela, total in relatorio.apagadas.items():
        print(f"  {tabela}: {total}")
    print("fica (5 anos; acesso, 6 meses):")
    for tabela, total in relatorio.preservadas.items():
        print(f"  {tabela}: {total}")
    if not relatorio.aplicado:
        print("nada foi apagado (--dry-run)")


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
