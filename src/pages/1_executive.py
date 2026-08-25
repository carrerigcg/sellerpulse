"""Página 1 do dashboard — Executive Summary.

Espelha o PDF: faixa de KPIs com a variação contra a janela anterior embutida
em cada tile + fluxo financeiro diário. Consome apenas metrics.* — nunca abre
SQLite direto. Todo o estilo vem de src.theme.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.express as px
import streamlit as st

from src import theme
from src.metrics import fluxo_financeiro, reputacao_devolucao

_DEMO_DB = Path("data/demo.db")

_COMPONENTES = ["receita_bruta", "taxas_ml", "frete", "custo_estimado", "liquido"]
_ROTULOS = {
    "receita_bruta": "Receita bruta",
    "taxas_ml": "Taxas ML",
    "frete": "Frete",
    "custo_estimado": "Custo estimado",
    "liquido": "Líquido",
}


def _get_window() -> tuple[str, str]:
    """Lê período da sidebar; fallback = últimos 90 dias."""
    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    return (
        st.session_state.get("date_from", default_from.isoformat()),
        st.session_state.get("date_to", default_to.isoformat()),
    )


@st.cache_data(ttl=300)
def _load_fluxo(date_from: str, date_to: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return fluxo_financeiro(conn, date_from, date_to)
    finally:
        conn.close()


@st.cache_data(ttl=300)
def _load_reputacao(date_from: str, date_to: str) -> dict:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return reputacao_devolucao(conn, date_from, date_to)
    finally:
        conn.close()


def _totais(fluxo: pd.DataFrame) -> tuple[float, float, float]:
    """(receita bruta, custo total, lucro líquido) do período."""
    if fluxo.empty:
        return 0.0, 0.0, 0.0
    receita = float(fluxo["receita_bruta"].sum())
    custo = float((fluxo["taxas_ml"] + fluxo["frete"] + fluxo["custo_estimado"]).sum())
    liquido = float(fluxo["liquido"].sum())
    return receita, custo, liquido


def _janela_anterior(date_from: str, date_to: str) -> tuple[str, str]:
    """Janela imediatamente anterior, de mesma duração."""
    dt_from = date.fromisoformat(date_from)
    dt_to = date.fromisoformat(date_to)
    delta_dias = (dt_to - dt_from).days
    prev_to = dt_from
    prev_from = prev_to - timedelta(days=delta_dias)
    return prev_from.isoformat(), prev_to.isoformat()


def _delta(atual: float, anterior: float) -> tuple[str | None, bool | None]:
    """Variação percentual formatada + se subiu. (None, None) sem base."""
    if anterior == 0:
        return None, None
    pct = 100 * (atual - anterior) / anterior
    return f"{pct:+.1f}%", pct >= 0


def _render_kpis(fluxo: pd.DataFrame, reput: dict, date_from: str, date_to: str) -> None:
    receita, custo, liquido = _totais(fluxo)
    prev_from, prev_to = _janela_anterior(date_from, date_to)
    receita_ant, custo_ant, liquido_ant = _totais(_load_fluxo(prev_from, prev_to))

    d_receita, subiu_receita = _delta(receita, receita_ant)
    d_custo, subiu_custo = _delta(custo, custo_ant)
    d_liquido, subiu_liquido = _delta(liquido, liquido_ant)

    theme.kpi_row(
        [
            theme.Kpi("Receita bruta", f"R$ {receita:,.2f}", "revenue", d_receita, subiu_receita),
            # Custo é o único KPI em que subir é resultado pior: o sinal inverte.
            theme.Kpi(
                "Custo total",
                f"R$ {custo:,.2f}",
                "cost",
                d_custo,
                None if subiu_custo is None else not subiu_custo,
            ),
            theme.Kpi("Lucro líquido", f"R$ {liquido:,.2f}", "profit", d_liquido, subiu_liquido),
            theme.Kpi("Nível ML", str(reput.get("nivel_ml", "—")), "level"),
        ]
    )


def _render_fluxo_chart(fluxo: pd.DataFrame) -> None:
    with theme.card("Fluxo financeiro por dia", "Composição diária de receita e custos"):
        if fluxo.empty:
            st.info("Sem pedidos pagos no período selecionado.")
            return
        tidy = fluxo.melt(
            id_vars="date",
            value_vars=_COMPONENTES,
            var_name="componente",
            value_name="valor",
        )
        tidy["componente"] = tidy["componente"].map(_ROTULOS)
        fig = px.bar(
            tidy,
            x="date",
            y="valor",
            color="componente",
            labels={"date": "", "valor": "R$", "componente": ""},
            color_discrete_sequence=theme.CHART_SEQUENCE,
            category_orders={"componente": [_ROTULOS[c] for c in _COMPONENTES]},
        )
        st.plotly_chart(theme.style_fig(fig), width="stretch")


def _main() -> None:
    theme.inject_css()
    date_from, date_to = _get_window()
    theme.page_header(
        "Executive Summary",
        "Receita, custos e resultado do período — com variação sobre a janela anterior.",
        f"{date_from} — {date_to}",
    )

    fluxo = _load_fluxo(date_from, date_to)
    reput = _load_reputacao(date_from, date_to)

    _render_kpis(fluxo, reput, date_from, date_to)
    _render_fluxo_chart(fluxo)


_main()
