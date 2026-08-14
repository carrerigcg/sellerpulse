"""Testes do renderizador de PDF — foco no HTML (snapshot)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.pdf_renderer import _fmt_brl, _fmt_periodo, render_html


@pytest.fixture(scope="module")
def demo_conn() -> sqlite3.Connection:
    db_path = Path("data/demo.db")
    assert db_path.exists(), "Rode `python -m src.main regerar-dados` antes."
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_render_html_matches_golden(demo_conn: sqlite3.Connection, file_regression) -> None:
    """Snapshot: HTML gerado com a janela demo bate byte-a-byte com o golden.

    Regenerar após mudanças intencionais no template:
        pytest tests/test_pdf_renderer.py --force-regen
    """
    html = render_html(
        conn=demo_conn,
        date_from="2026-07-25",
        date_to="2026-08-01",
        generated_at=datetime(2026, 8, 1, 6, 0, 0),
    )
    file_regression.check(html, extension=".html", encoding="utf-8")


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.0, "R$ 0,00"),
        (0.05, "R$ 0,05"),
        (3847.52, "R$ 3.847,52"),
        (1_234_567.89, "R$ 1.234.567,89"),
        (-0.50, "R$ -0,50"),  # regression: signal preservation < 1
        (-127.30, "R$ -127,30"),
        (-1_234.00, "R$ -1.234,00"),
    ],
)
def test_fmt_brl(value: float, expected: str) -> None:
    assert _fmt_brl(value) == expected


@pytest.mark.parametrize(
    "date_from,date_to,expected",
    [
        ("2026-07-25", "2026-08-01", "25 a 31 de julho de 2026"),  # same month
        ("2026-07-28", "2026-08-04", "28 de julho de 2026 a 3 de agosto de 2026"),  # cross month
        ("2025-12-29", "2026-01-05", "29 de dezembro de 2025 a 4 de janeiro de 2026"),  # cross year
    ],
)
def test_fmt_periodo(date_from: str, date_to: str, expected: str) -> None:
    assert _fmt_periodo(date_from, date_to) == expected


def test_render_pdf_produces_valid_pdf_file(tmp_path: Path) -> None:
    """Smoke test — só verifica que WeasyPrint cospe algo com assinatura %PDF."""
    try:
        pytest.importorskip("weasyprint", reason="WeasyPrint não instalado (GTK ausente)")
    except OSError as exc:
        pytest.skip(f"WeasyPrint não funcional nesta máquina (GTK ausente): {exc}")
    from src.pdf_renderer import render_pdf

    output = tmp_path / "relatorio.pdf"
    result = render_pdf(
        db_path=Path("data/demo.db"),
        output_path=output,
        date_from="2026-07-25",
        date_to="2026-08-01",
        generated_at=datetime(2026, 8, 1, 6, 0, 0),
    )
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 1024
    assert output.read_bytes()[:4] == b"%PDF"
