"""Smoke tests do dashboard Streamlit — só valida que cada página carrega
sem exception. Corretude analítica é coberta em test_metrics/test_segmentation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(scope="session", autouse=True)
def _demo_db_available() -> None:
    """Garante que data/demo.db existe antes de rodar qualquer smoke test."""
    assert Path("data/demo.db").exists(), "Rode `python -m src.main regerar-dados` antes."


def _page_path(filename: str) -> str:
    """Resolve an absolute path to a dashboard page file."""
    return str(Path(__file__).parent.parent / "src" / "pages" / filename)


def test_executive_page_loads() -> None:
    at = AppTest.from_file(_page_path("1_executive.py"))
    at.session_state["date_from"] = "2026-05-01"
    at.session_state["date_to"] = "2026-08-01"
    at.run(timeout=15)
    assert not at.exception, f"Page raised: {at.exception}"


def test_products_page_loads() -> None:
    at = AppTest.from_file(_page_path("2_products.py"))
    at.session_state["date_from"] = "2026-05-01"
    at.session_state["date_to"] = "2026-08-01"
    at.run(timeout=15)
    assert not at.exception, f"Page raised: {at.exception}"


def test_customers_page_loads() -> None:
    at = AppTest.from_file(_page_path("3_customers.py"))
    at.session_state["date_from"] = "2026-05-01"
    at.session_state["date_to"] = "2026-08-01"
    at.run(timeout=15)
    assert not at.exception, f"Page raised: {at.exception}"
