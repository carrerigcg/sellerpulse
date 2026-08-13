"""Renderiza o relatório executivo em HTML e PDF.

`render_html` é pura (recebe conn + janela + timestamp, devolve string).
`render_pdf` (adicionado na Task 7) é o wrapper impuro que passa o HTML
pro WeasyPrint.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.metrics import fluxo_financeiro, reputacao_devolucao, top_produtos

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_TEMPLATE_NAME = "relatorio.html.j2"

_MESES_PT = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

# Proxy tem 3 níveis; mapeiam pras posições ímpares da barra de 5 segmentos.
# Posições 2 (Laranja) e 4 (Verde claro) ficam vazias até o feed real de
# reputação ML entrar (Fase 3+).
_THERM_POSITION_BY_NIVEL = {"Vermelho": 1, "Amarelo": 3, "Verde": 5}


def _fmt_brl(value: float) -> str:
    """Formata 3847.52 → 'R$ 3.847,52' (padrão BR). Preserva sinal para negativos."""
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    inteiro = int(abs_val)
    cents = round((abs_val - inteiro) * 100)
    inteiro_str = f"{inteiro:,}".replace(",", ".")
    return f"R$ {sign}{inteiro_str},{cents:02d}"


def _fmt_brl_short(value: float) -> str:
    """Formata 3847 → '3.847' (sem R$, sem centavos — usado no waterfall)."""
    return f"{int(round(value)):,}".replace(",", ".")


def _fmt_periodo(date_from: str, date_to: str) -> str:
    """'2026-07-25', '2026-08-01' → '25 a 31 de julho de 2026'."""
    inicio = datetime.fromisoformat(date_from)
    fim_exclusivo = datetime.fromisoformat(date_to)
    fim = fim_exclusivo - timedelta(days=1)
    if inicio.month == fim.month:
        return f"{inicio.day} a {fim.day} de {_MESES_PT[inicio.month - 1]} de {inicio.year}"
    return (
        f"{inicio.day} de {_MESES_PT[inicio.month - 1]} de {inicio.year} "
        f"a {fim.day} de {_MESES_PT[fim.month - 1]} de {fim.year}"
    )


def _fmt_generated_at(when: datetime) -> str:
    """datetime(2026, 8, 1, 6, 0) → '1 de agosto de 2026 · 06h00'."""
    return f"{when.day} de {_MESES_PT[when.month - 1]} de {when.year} · {when.strftime('%Hh%M')}"


def _build_context(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    generated_at: datetime,
) -> dict:
    fluxo_df = fluxo_financeiro(conn, date_from, date_to)
    receita = float(fluxo_df["receita_bruta"].sum())
    taxas = float(fluxo_df["taxas_ml"].sum())
    frete = float(fluxo_df["frete"].sum())
    liquido = float(fluxo_df["liquido"].sum())

    # Comparativo semana anterior — mesma duração, janela adjacente
    dias = (datetime.fromisoformat(date_to) - datetime.fromisoformat(date_from)).days
    prev_from = (datetime.fromisoformat(date_from) - timedelta(days=dias)).date().isoformat()
    prev_to = date_from
    prev_liquido = float(fluxo_financeiro(conn, prev_from, prev_to)["liquido"].sum())
    delta = liquido - prev_liquido

    top = top_produtos(conn, date_from, date_to, n=3)
    reput = reputacao_devolucao(conn, date_from, date_to)

    def pct(v: float) -> int:
        return int(round(100 * v / receita)) if receita else 0

    fluxo_ctx = {
        "receita_bruta": _fmt_brl(receita),
        "receita_bruta_short": _fmt_brl_short(receita),
        "taxas_ml": _fmt_brl(taxas),
        "taxas_ml_short": _fmt_brl_short(taxas),
        "frete": _fmt_brl(frete),
        "frete_short": _fmt_brl_short(frete),
        "liquido": _fmt_brl(liquido),
        "liquido_short": _fmt_brl_short(liquido),
        "taxas_pct": pct(taxas),
        "frete_pct": pct(frete),
        "liquido_pct": pct(liquido),
        "delta_vs_anterior": (f"+{_fmt_brl(delta)}" if delta >= 0 else f"−{_fmt_brl(abs(delta))}"),
        "delta_vs_anterior_positive": delta >= 0,
    }

    produtos_top = [
        {
            "posicao": i + 1,
            "title": row["title"],
            "category_name": row["category_name"],
            "unidades": int(row["unidades"]),
            "receita_fmt": _fmt_brl(float(row["receita"])),
        }
        for i, (_, row) in enumerate(top["produtos"].iterrows())
    ]
    categorias_top = [
        {
            "posicao": i + 1,
            "title": row["category_name"],
            "category_name": "",
            "unidades": int(row["unidades"]),
            "receita_fmt": _fmt_brl(float(row["receita"])),
        }
        for i, (_, row) in enumerate(top["categorias"].iterrows())
    ]

    reputacao_ctx = {
        "nivel_ml": reput["nivel_ml"],
        "taxa_devolucao_pct_fmt": f"{reput['taxa_devolucao_pct']:.2f}%".replace(".", ","),
        "claims_ativos": reput["claims_ativos"],
        "claims_total": reput["claims_total"],
        "alertas": reput["alertas"],
        "therm_position": _THERM_POSITION_BY_NIVEL[reput["nivel_ml"]],
    }

    inicio = datetime.fromisoformat(date_from)
    return {
        "periodo_label": _fmt_periodo(date_from, date_to),
        "edicao": {"vol": "I", "num": inicio.isocalendar().week, "ano": inicio.year},
        "generated_at_label": _fmt_generated_at(generated_at),
        "fluxo": fluxo_ctx,
        "produtos_top": produtos_top,
        "categorias_top": categorias_top,
        "reputacao": reputacao_ctx,
    }


def render_html(
    *,
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    generated_at: datetime | None = None,
) -> str:
    """Renderiza HTML do relatório executivo. Puro — só lê `conn`.

    Args:
        conn: SQLite aberto (read-only OK).
        date_from: início inclusivo (YYYY-MM-DD).
        date_to: fim exclusivo (YYYY-MM-DD).
        generated_at: timestamp que aparece no rodapé. Se None, usa now().

    Returns:
        HTML pronto pro WeasyPrint. UTF-8.
    """
    when = generated_at if generated_at is not None else datetime.now()
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template(_TEMPLATE_NAME)
    ctx = _build_context(conn, date_from, date_to, when)
    return template.render(**ctx)
