"""Utilitários compartilhados entre os módulos de porte pra Postgres/asyncpg.

Tem `FUSO_DO_VENDEDOR` (o fuso em que um "dia" é contado) e `_parse_boundary`,
usada por `metrics_pg.py` e `segmentation_pg.py` pra converter os limites de
janela temporal (`date_from`/`date_to`) antes de passar pra `pool.fetch(...)`.
Vivem aqui em vez de em qualquer um dos dois módulos pra evitar duplicação ou
import cruzado entre eles.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

# De QUEM é o dia. O armazenamento é `timestamptz` em UTC (correto, e não muda),
# mas agrupar por dia/mês em UTC respondia a pergunta errada: o vendedor fecha o
# mês em Brasília. Medido na loja real conectada (879 pedidos pagos, 180 dias):
# 123 pedidos (14%) caem num dia de calendário diferente em UTC, porque o pico
# de vendas da noite brasileira (21h-23h BRT) vira 00h-02h UTC do dia seguinte.
# Isso mudava o valor de 123 dos 179 dias do gráfico diário (69%), com
# diferença de até R$ 1.210,00 num dia, e jogava R$ 465,00 de junho pra julho.
#
# Uma constante só, usada pelas DUAS camadas analíticas: a mesma string
# duplicada em dois módulos é exatamente como duas camadas divergem.
#
# Por que o NOME do fuso e não o offset "-03:00": o Brasil extinguiu o horário
# de verão em 2019, mas `America/Sao_Paulo` ainda carrega as transições
# históricas — uma data de 2018 desloca 2h, não 3h. Isso é o comportamento
# CORRETO pra dado histórico, e um "-03" hardcoded (que parece mais simples)
# silenciosamente erraria o bucket de qualquer pedido anterior a 2019.
FUSO_DO_VENDEDOR = "America/Sao_Paulo"

_TZ_VENDEDOR = ZoneInfo(FUSO_DO_VENDEDOR)


def _parse_boundary(date_str: str) -> datetime:
    """Converte data/hora ISO 8601 em datetime timezone-aware.

    asyncpg exige `datetime.datetime` — não `str` — como argumento pra um
    parâmetro com cast `::timestamptz` (o protocolo binário não faz o parse
    que o `psycopg`/SQLite fariam com uma string crua).

    Datas sem horário (ex: "2026-07-25") viram meia-noite no fuso do vendedor,
    não em UTC: é o mesmo fuso em que as queries montam os buckets de dia e
    mês, e borda da janela discordando do bucket por 3 horas é pior que
    qualquer uma das duas escolhas feita de forma consistente.

    String que já traz offset explícito ("...T00:00:00+00:00") mantém o offset
    que o chamador declarou — aqui não se adivinha intenção de quem foi
    explícito.

    Terceiro consumidor, fora de `backend/analytics/`: `backend/seed.py` usa
    esta função pra converter os `date_closed` do gerador sintético antes de
    gravar. Aquelas strings são naive e representam hora de parede brasileira
    (`src/demo_data.py` sorteia hora entre 9 e 22), então interpretá-las em
    Brasília é mais fiel do que em UTC. Nenhum pedido semeado troca de dia por
    causa disso nos dois sentidos — 9h-22h não cruza a meia-noite em nenhum
    dos dois fusos —, só o instante absoluto gravado desloca 3 horas.
    A ingestão real NÃO passa por aqui: `backend/ml/ingest_pg.py` tem o seu
    próprio `_para_datetime`, e o ML já manda offset explícito ("...-03:00").
    """
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ_VENDEDOR)
    return dt
