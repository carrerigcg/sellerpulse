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


def test_icons_cobre_todos_os_usos_das_paginas() -> None:
    necessarios = {"revenue", "cost", "profit", "level", "users", "star", "alert", "ticket", "box"}
    assert necessarios <= set(theme.ICONS)


def test_icon_html_produz_svg_com_a_cor_de_acento() -> None:
    markup = theme.icon_html("revenue")
    assert markup.startswith("<svg")
    assert theme.COLORS["accent"] in markup
    assert 'viewBox="0 0 24 24"' in markup


def test_build_css_referencia_os_tokens_principais() -> None:
    css = theme.build_css()
    for token in ("bg", "surface", "surface_raised", "text", "accent"):
        assert theme.COLORS[token] in css, f"token {token} ausente do CSS"


def test_build_css_da_cores_distintas_as_pilulas_de_delta() -> None:
    css = theme.build_css()
    assert ".sp-kpi__delta.is-positive" in css
    assert ".sp-kpi__delta.is-negative" in css
    assert theme.COLORS["positive"] in css
    assert theme.COLORS["negative"] in css


def test_build_css_comeca_pelo_import_da_fonte() -> None:
    # @import só vale se for a primeira regra da folha de estilo.
    assert theme.build_css().lstrip().startswith("@import")


def test_kpi_row_html_emite_valor_e_rotulo_de_cada_tile() -> None:
    markup = theme.kpi_row_html(
        [
            theme.Kpi("Receita bruta", "R$ 1.234,00", "revenue"),
            theme.Kpi("Nível ML", "Verde", "level"),
        ]
    )
    assert "Receita bruta" in markup
    assert "R$ 1.234,00" in markup
    assert "Nível ML" in markup
    assert "Verde" in markup
    assert markup.count("sp-kpi__value") == 2


def test_kpi_row_html_marca_delta_positivo_e_negativo_com_classes_distintas() -> None:
    positivo = theme.kpi_row_html([theme.Kpi("A", "1", "revenue", "+5.0%", True)])
    negativo = theme.kpi_row_html([theme.Kpi("A", "1", "revenue", "-5.0%", False)])
    assert "is-positive" in positivo
    assert "is-negative" not in positivo
    assert "is-negative" in negativo
    assert "is-positive" not in negativo


def test_kpi_row_html_usa_pilula_neutra_quando_nao_ha_base_de_comparacao() -> None:
    markup = theme.kpi_row_html([theme.Kpi("A", "1", "revenue", "n/a", None)])
    assert "is-neutral" in markup


def test_kpi_row_html_omite_a_pilula_quando_nao_ha_delta() -> None:
    markup = theme.kpi_row_html([theme.Kpi("A", "1", "revenue")])
    assert "sp-kpi__delta" not in markup


def test_kpi_row_html_escapa_html_no_valor() -> None:
    markup = theme.kpi_row_html([theme.Kpi("<b>rótulo</b>", "<script>", "revenue")])
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_page_header_html_inclui_titulo_subtitulo_e_periodo() -> None:
    markup = theme.page_header_html("Executive", "Resumo do período", "2026-05-01 — 2026-08-01")
    assert "Executive" in markup
    assert "Resumo do período" in markup
    assert "2026-05-01 — 2026-08-01" in markup
    assert "sp-pill" in markup


def test_page_header_html_omite_partes_opcionais() -> None:
    markup = theme.page_header_html("Só o título")
    assert "sp-header__subtitle" not in markup
    assert "sp-pill" not in markup
