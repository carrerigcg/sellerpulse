"""Identidade visual do dashboard — tokens, CSS e componentes.

Fonte única de verdade do estilo. Nenhuma página escreve CSS: elas chamam
`inject_css()` no topo e usam os helpers deste módulo.

A paleta é derivada de `templates/relatorio.html.j2`, transposta para fundo
escuro — dashboard e PDF são o mesmo produto visualmente.

Convenção do módulo: funções `*_html` constroem string e não tocam o
Streamlit (são o que os testes exercitam); as demais renderizam.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

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


def build_css() -> str:
    """Folha de estilo completa do dashboard, como string.

    Separada de `inject_css` para poder ser testada sem runtime do Streamlit.
    """
    c = COLORS
    return f"""@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
  --sp-bg: {c["bg"]};
  --sp-surface: {c["surface"]};
  --sp-raised: {c["surface_raised"]};
  --sp-border: {c["border"]};
  --sp-text: {c["text"]};
  --sp-muted: {c["text_muted"]};
  --sp-accent: {c["accent"]};
  --sp-gold: {c["gold"]};
  --sp-positive: {c["positive"]};
  --sp-negative: {c["negative"]};
  --sp-radius: 12px;
}}

/* ---- superfícies base ---- */
[data-testid="stAppViewContainer"] {{ background: var(--sp-bg); }}
[data-testid="stHeader"] {{ background: transparent; }}
/* Esconde o botão Deploy e o menu — ruído em screenshot de portfólio. */
[data-testid="stToolbar"] {{ display: none; }}
[data-testid="stSidebar"] {{
  background: var(--sp-surface);
  border-right: 1px solid var(--sp-border);
}}

html, body, [data-testid="stAppViewContainer"] {{
  font-family: {FONT_STACK};
  color: var(--sp-text);
}}

/* ---- cartões: st.container(border=True) ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  padding: 18px 20px;
}}
.sp-card__head {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }}
.sp-card__title {{ font-size: .95rem; font-weight: 600; color: var(--sp-text); }}
.sp-card__subtitle {{ font-size: .78rem; color: var(--sp-muted); }}

/* ---- cabeçalho de página ---- */
.sp-header {{ margin: 0 0 20px; }}
.sp-header__title {{
  font-size: 1.8rem; font-weight: 700; margin: 0;
  color: var(--sp-text); letter-spacing: -.02em;
}}
.sp-header__subtitle {{ margin: 4px 0 0; font-size: .95rem; color: var(--sp-muted); }}
.sp-pill {{
  display: inline-block; margin-top: 10px; padding: 3px 10px;
  font-size: .72rem; color: var(--sp-muted);
  border: 1px solid var(--sp-border); border-radius: 999px;
}}

/* ---- tiles de KPI ---- */
.sp-kpi-grid {{
  display: grid; gap: 14px; margin: 2px 0 22px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}}
.sp-kpi {{
  background: var(--sp-raised); border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius); padding: 16px 18px;
}}
.sp-kpi__icon {{ line-height: 0; margin-bottom: 10px; }}
.sp-kpi__value {{
  font-size: 1.7rem; font-weight: 600; color: var(--sp-text);
  letter-spacing: -.01em; font-feature-settings: "tnum";
}}
.sp-kpi__label {{
  margin-top: 4px; font-size: .7rem; color: var(--sp-muted);
  text-transform: uppercase; letter-spacing: .08em;
}}
.sp-kpi__delta {{
  display: inline-block; margin-top: 10px; padding: 2px 8px;
  font-size: .72rem; font-weight: 600; border-radius: 999px;
}}
.sp-kpi__delta.is-positive {{ color: var(--sp-positive); background: rgba(52,211,153,.12); }}
.sp-kpi__delta.is-negative {{ color: var(--sp-negative); background: rgba(248,113,113,.12); }}
.sp-kpi__delta.is-neutral  {{ color: var(--sp-muted);    background: rgba(148,163,184,.12); }}

/* ---- marca na sidebar ---- */
.sp-brand {{ padding: 4px 0 14px; }}
.sp-brand__name {{
  font-size: 1.25rem; font-weight: 700;
  color: var(--sp-text); letter-spacing: -.02em;
}}
.sp-brand__name em {{ font-style: normal; color: var(--sp-accent); }}
.sp-brand__version {{
  margin-top: 2px; font-size: .68rem; color: var(--sp-muted);
  text-transform: uppercase; letter-spacing: .08em;
}}

/* ---- capa da home ---- */
.sp-cover {{ padding: 26px 0 30px; }}
.sp-cover__name {{
  font-size: 2.6rem; font-weight: 700;
  color: var(--sp-text); letter-spacing: -.03em;
}}
.sp-cover__name em {{ font-style: normal; color: var(--sp-accent); }}
.sp-cover__tagline {{ margin: 6px 0 0; font-size: 1rem; color: var(--sp-muted); }}

/* ---- cartões de navegação da home ---- */
.sp-nav__icon {{ line-height: 0; margin-bottom: 10px; }}
.sp-nav__title {{ font-size: 1.05rem; font-weight: 600; color: var(--sp-text); }}
.sp-nav__desc {{ margin-top: 4px; min-height: 40px; font-size: .85rem; color: var(--sp-muted); }}
"""


def inject_css() -> None:
    """Injeta a folha de estilo. Chamar UMA vez, no topo de cada página.

    Chamar duas vezes no mesmo run só emite um segundo bloco <style> idêntico
    — inofensivo (as regras são as mesmas), mas desnecessário.
    """
    st.markdown(f"<style>{build_css()}</style>", unsafe_allow_html=True)


@dataclass(frozen=True)
class Kpi:
    """Um tile da faixa de KPIs.

    Attributes:
        label: rótulo curto, renderizado em caixa alta.
        value: valor já formatado para exibição (o theme não formata número).
        icon: chave de `ICONS`.
        delta: variação já formatada (ex.: "+12.4%"). None esconde a pílula.
        delta_positive: True pinta de verde, False de vermelho, None de cinza.
            Quem chama decide o sinal — para custo, um aumento é negativo.
    """

    label: str
    value: str
    icon: str
    delta: str | None = None
    delta_positive: bool | None = None


def _kpi_tile_html(kpi: Kpi) -> str:
    delta = ""
    if kpi.delta is not None:
        if kpi.delta_positive is None:
            modifier = "is-neutral"
        else:
            modifier = "is-positive" if kpi.delta_positive else "is-negative"
        delta = f'<span class="sp-kpi__delta {modifier}">{html.escape(kpi.delta)}</span>'
    return (
        '<div class="sp-kpi">'
        f'<div class="sp-kpi__icon">{icon_html(kpi.icon)}</div>'
        f'<div class="sp-kpi__value">{html.escape(kpi.value)}</div>'
        f'<div class="sp-kpi__label">{html.escape(kpi.label)}</div>'
        f"{delta}"
        "</div>"
    )


def kpi_row_html(kpis: list[Kpi]) -> str:
    """Grid de tiles como string. Testável sem Streamlit."""
    tiles = "".join(_kpi_tile_html(k) for k in kpis)
    return f'<div class="sp-kpi-grid">{tiles}</div>'


def kpi_row(kpis: list[Kpi]) -> None:
    """Renderiza a faixa de KPIs.

    Vai numa ÚNICA chamada de st.markdown de propósito: quebrar em várias
    (uma por coluna) faz o Streamlit inserir espaçamento entre os blocos e
    o grid deixa de alinhar.
    """
    st.markdown(kpi_row_html(kpis), unsafe_allow_html=True)


def page_header_html(title: str, subtitle: str | None = None, period: str | None = None) -> str:
    parts = [f'<div class="sp-header"><h1 class="sp-header__title">{html.escape(title)}</h1>']
    if subtitle:
        parts.append(f'<p class="sp-header__subtitle">{html.escape(subtitle)}</p>')
    if period:
        parts.append(f'<span class="sp-pill">{html.escape(period)}</span>')
    parts.append("</div>")
    return "".join(parts)


def page_header(title: str, subtitle: str | None = None, period: str | None = None) -> None:
    """Substitui o par st.title + st.caption das páginas."""
    st.markdown(page_header_html(title, subtitle, period), unsafe_allow_html=True)
