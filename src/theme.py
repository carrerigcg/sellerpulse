"""Identidade visual do dashboard — tokens, CSS e componentes.

Fonte única de verdade do estilo. Nenhuma página escreve CSS: elas chamam
`inject_css()` no topo e usam os helpers deste módulo.

A paleta é derivada de `templates/relatorio.html.j2`, transposta para fundo
escuro — dashboard e PDF são o mesmo produto visualmente.

Convenção do módulo: funções `*_html` constroem string e não tocam o
Streamlit (são o que os testes exercitam); as demais renderizam.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SELETORES FRÁGEIS DO STREAMLIT
#
# Os `data-testid` abaixo são internos do Streamlit e podem mudar entre
# versões majors — por isso `requirements.txt` fixa `streamlit>=1.62,<2`.
# Se o layout quebrar depois de um upgrade, é AQUI que se conserta: nenhum
# outro arquivo do projeto depende desses seletores.
#
#   [data-testid="stAppViewContainer"]           container raiz da página
#   [data-testid="stHeader"]                     barra superior
#   [data-testid="stToolbar"]                    botão Deploy + menu
#   [data-testid="stSidebar"]                    sidebar
#   [data-testid="stVerticalBlockBorderWrapper"] st.container(border=True)
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    "bg": "#051431",  # --navy-950 do PDF
    "surface": "#0a1f3d",  # --navy-900
    "surface_raised": "#0f2a4d",  # interpolado
    "border": "rgba(148,163,184,.14)",
    "text": "#e8eef7",
    "text_muted": "#8fa3bf",
    "accent": "#3b82f6",  # --blue-500
    "gold": "#c9a961",  # --gold-500
    "positive": "#34d399",  # --positive clareado para fundo escuro
    "negative": "#f87171",  # --negative clareado para fundo escuro
}

# Rampa categórica dos gráficos. A ordem importa: é ela que decide a cor de
# cada série. Plotly Express NÃO respeita `colorway` — passe esta lista em
# `color_discrete_sequence=` na criação da figura.
CHART_SEQUENCE: list[str] = [
    "#3b82f6",
    "#c9a961",
    "#60a5fa",
    "#94a3b8",
    "#34d399",
    "#f87171",
]

# Escala contínua (heatmap de cohort): navy -> azul -> dourado.
CHART_CONTINUOUS: list[list[float | str]] = [
    [0.0, COLORS["surface"]],
    [0.6, COLORS["accent"]],
    [1.0, COLORS["gold"]],
]

GRID_COLOR = "rgba(148,163,184,.10)"

FONT_STACK = '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif'
