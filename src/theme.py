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

# Ícones: só o miolo do <svg>, num grid de 24x24, traço em currentColor.
# Emoji está descartado de propósito — destoa da regra de contenção
# corporativa (ver docs/specs/2026-08-25-ui-theme-dashboard-design.md).
ICONS: dict[str, str] = {
    "revenue": '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/>',
    "cost": '<polyline points="3 7 9 13 13 9 21 17"/><polyline points="15 17 21 17 21 11"/>',
    "profit": (
        '<path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        '<path d="M16 12h3"/>'
    ),
    "level": '<circle cx="12" cy="9" r="5"/><polyline points="9 13 8 21 12 19 16 21 15 13"/>',
    "users": (
        '<path d="M16 19v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9.5" cy="7" r="3.5"/>'
        '<path d="M21 19v-2a4 4 0 0 0-3-3.9"/>'
    ),
    "star": '<polygon points="12 3 14.8 8.6 21 9.5 16.5 13.9 17.6 20 12 17.1 6.4 20 7.5 13.9 3 9.5 9.2 8.6"/>',
    "alert": '<path d="M12 4 2.5 20h19z"/><line x1="12" y1="10" x2="12" y2="14"/><line x1="12" y1="16.8" x2="12" y2="17"/>',
    "ticket": (
        '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0l-7.2-7.2A2 2 0 0 1 3 12V5a2 2 0 0 1 2-2h7'
        'a2 2 0 0 1 1.4.6l7.2 7.2a2 2 0 0 1 0 2.6z"/><circle cx="7.5" cy="7.5" r="1.2"/>'
    ),
    "box": (
        '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="M3 8l9 5 9-5"/>'
        '<line x1="12" y1="13" x2="12" y2="21"/>'
    ),
}


def icon_html(name: str, size: int = 20, color: str | None = None) -> str:
    """SVG inline de `ICONS[name]`. Levanta KeyError se o nome não existir."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color or COLORS["accent"]}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f"{ICONS[name]}</svg>"
    )
