# backend/routers/_common.py
"""Validação de entrada compartilhada pelos routers REST.

Os módulos de `backend/analytics/` assumem entrada bem-formada (é
responsabilidade de quem chama). Como os routers são endpoints públicos de
um SaaS, qualquer entrada malformada do cliente precisa virar 400 — nunca
500. Centralizado aqui pra não repetir a mesma validação nos 5 endpoints.
"""

from __future__ import annotations

from fastapi import HTTPException

from backend.analytics._common import _parse_boundary


def validate_window(date_from: str, date_to: str) -> tuple[str, str]:
    """Garante que `date_from`/`date_to` parseiam como ISO 8601.

    `_parse_boundary` levanta `ValueError` pra string malformada — sem essa
    validação na borda da API, isso estouraria como 500 (erro não tratado)
    em vez de um 400 de entrada inválida do cliente.
    """
    for label, value in (("date_from", date_from), ("date_to", date_to)):
        try:
            _parse_boundary(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{label} inválida: {value!r}") from exc
    return date_from, date_to


def validate_n(n: int) -> int:
    """Garante `n >= 1`.

    `LIMIT` negativo é erro de sintaxe no Postgres (diferente do SQLite
    original, onde `LIMIT -1` significa "sem limite") — sem essa validação,
    `n <= 0` estouraria como 500 vindo do Postgres.
    """
    if n < 1:
        raise HTTPException(status_code=400, detail="n deve ser um inteiro >= 1")
    return n
