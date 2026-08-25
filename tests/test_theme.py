"""Testes do contrato de src/theme.py.

São testes puros: miram nos construtores de string (build_css, kpi_row_html)
e em style_fig, nunca em funções que chamam o Streamlit. Isso mantém a suíte
rodando sem runtime do Streamlit.
"""

from __future__ import annotations

from src import theme

_TOKENS_ESPERADOS = {
    "bg",
    "surface",
    "surface_raised",
    "border",
    "text",
    "text_muted",
    "accent",
    "gold",
    "positive",
    "negative",
}


def test_colors_tem_todos_os_tokens() -> None:
    assert set(theme.COLORS) == _TOKENS_ESPERADOS


def test_chart_sequence_na_ordem_especificada() -> None:
    assert theme.CHART_SEQUENCE == [
        "#3b82f6",
        "#c9a961",
        "#60a5fa",
        "#94a3b8",
        "#34d399",
        "#f87171",
    ]


def test_chart_continuous_vai_de_navy_a_gold() -> None:
    assert theme.CHART_CONTINUOUS[0] == [0.0, theme.COLORS["surface"]]
    assert theme.CHART_CONTINUOUS[-1] == [1.0, theme.COLORS["gold"]]
