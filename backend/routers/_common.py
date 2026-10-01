# backend/routers/_common.py
"""Validação de entrada compartilhada pelos routers REST.

Os módulos de `backend/analytics/` assumem entrada bem-formada (é
responsabilidade de quem chama). Como os routers são endpoints públicos de
um SaaS, qualquer entrada malformada do cliente precisa virar 400 — nunca
500. Centralizado aqui pra não repetir a mesma validação nos 5 endpoints.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException

from backend.analytics._common import _parse_boundary

# Teto da duração da janela. Derivado do que o produto de fato serve: a
# ingestão faz backfill de 6 meses (JANELAS_BACKFILL * DIAS_POR_JANELA =
# 6 * 30 = 180 dias, em backend/worker/runner.py). O teto é o DOBRO disso e não
# os 180 exatos porque os deltas seguintes só acrescentam dado pra frente — o
# histórico de uma conta antiga passa dos 180 dias, e pedir "tudo" tem que
# continuar funcionando. Acima daí não é tela de ninguém: a janela mais larga
# do frontend pede 90 dias (`periodoPadrao()` em app/**/page.tsx) e a
# comparação com o período anterior (`janelaAnterior` em lib/api.ts) repete a
# MESMA duração, nunca soma.
#
# Por que existir um teto: cada par (date_from, date_to) é uma chave de cache
# nova, então variar as datas a cada request fura ao mesmo tempo o
# `Cache-Control: public, max-age=300` da resposta e o `revalidate: 3600` do
# lado da Vercel. Sem teto, `?date_from=1900-01-01&date_to=2100-01-01` é aceito
# — e /demo é a única porta sem autenticação do sistema, rodando num free tier
# do Render que hiberna em ~15 min e tem 750 horas-instância por mês: um loop
# trivial mantém a instância acordada de graça e queima a cota. Limitar a
# entrada é o que encolhe isso de verdade; um limitador de taxa in-process
# zeraria a cada cold start da instância, ou seja, seria teatro.
MAX_JANELA_DIAS = 2 * 180

# Teto do top-N. As duas rotas que aceitam `n` (/metrics/top-produtos e
# /demo/top-produtos) alimentam ranking de tela — o frontend usa o default de
# 10 e nenhuma tela mostra 100 produtos. Pelo mesmo motivo do teto acima: `n`
# arbitrário é `LIMIT` arbitrário no Postgres, isto é, trabalho ilimitado por
# request numa porta sem autenticação.
MAX_N = 100


def validate_window(date_from: str, date_to: str) -> tuple[str, str]:
    """Garante janela ISO 8601, ordenada e com no máximo `MAX_JANELA_DIAS`.

    `_parse_boundary` levanta `ValueError` pra string malformada — sem essa
    validação na borda da API, isso estouraria como 500 (erro não tratado)
    em vez de um 400 de entrada inválida do cliente.
    """
    limites = []
    for label, value in (("date_from", date_from), ("date_to", date_to)):
        try:
            limites.append(_parse_boundary(value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{label} inválida: {value!r}") from exc

    de, ate = limites
    # Janela invertida (ou de duração zero) devolvia 200 com lista vazia, que o
    # dashboard mostra como "nenhuma venda" — indistinguível de um período ruim
    # de verdade. É erro de entrada do cliente e tem que ser dito como tal.
    if de >= ate:
        raise HTTPException(
            status_code=400, detail=f"date_from ({date_from}) deve ser anterior a date_to"
        )
    # Compara o timedelta inteiro, não `.days`: `.days` truncaria as horas e
    # deixaria passar uma janela de "360 dias e 23 horas" como se fossem 360.
    duracao = ate - de
    if duracao > timedelta(days=MAX_JANELA_DIAS):
        raise HTTPException(
            status_code=400,
            detail=f"janela de no máximo {MAX_JANELA_DIAS} dias; a pedida tem {duracao.days} dias",
        )
    return date_from, date_to


def validate_n(n: int) -> int:
    """Garante `1 <= n <= MAX_N`.

    `LIMIT` negativo é erro de sintaxe no Postgres (diferente do SQLite
    original, onde `LIMIT -1` significa "sem limite") — sem essa validação,
    `n <= 0` estouraria como 500 vindo do Postgres.
    """
    if n < 1:
        raise HTTPException(status_code=400, detail="n deve ser um inteiro >= 1")
    if n > MAX_N:
        raise HTTPException(status_code=400, detail=f"n deve ser no máximo {MAX_N}; pedido: {n}")
    return n
