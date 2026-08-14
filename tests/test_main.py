"""Teste de integração do orquestrador de ingestão."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import responses

from src.auth import TokenSet, TokenStore
from src.main import _default_pdf_output, _resolve_gerar_pdf_window, ingest_window, main
from src.storage import connect, get_orders_in_range

BASE_URL = "https://api.mercadolibre.com"


@responses.activate
def test_ingest_window_persists_orders_items_claims_and_logs_run(tmp_path, monkeypatch):
    # 1) Setup ambiente
    tokens_path = tmp_path / "tokens.json"
    db_path = tmp_path / "historico.db"
    store = TokenStore(tokens_path)
    store.save(
        TokenSet(
            access_token="acc-1",
            refresh_token="ref-1",
            expires_at=datetime.now(UTC) + timedelta(hours=5),
        )
    )
    monkeypatch.setenv("ML_CLIENT_ID", "cid")
    monkeypatch.setenv("ML_CLIENT_SECRET", "csec")
    monkeypatch.setenv("ML_USER_ID", "999")

    # 2) Mocks ML
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={
            "paging": {"total": 1, "offset": 0, "limit": 50},
            "results": [
                {
                    "id": 1001,
                    "date_closed": "2026-06-10T14:30:00.000-03:00",
                    "status": "paid",
                    "total_amount": 250.0,
                    "payments": [{"marketplace_fee": 30.0}],
                    "shipping": {"list_cost": 15.0},
                    "buyer": {"id": 8888},
                    "order_items": [{"item": {"id": "MLB1"}, "quantity": 1, "unit_price": 250.0}],
                }
            ],
        },
        status=200,
    )
    # Segunda chamada (status=cancelled) → vazio
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={"paging": {"total": 0, "offset": 0, "limit": 50}, "results": []},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/items/MLB1",
        json={"id": "MLB1", "title": "Lanterna CG 150", "category_id": "MLB-cat-A"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/categories/MLB-cat-A",
        json={"id": "MLB-cat-A", "name": "Iluminação"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/post-purchase/v1/claims/search",
        json={"data": [], "paging": {"total": 0}},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/users/999",
        json={
            "id": 999,
            "seller_reputation": {"level_id": "5_green", "metrics": {"claims": {"value": 0}}},
        },
        status=200,
    )

    # 3) Executar
    result = ingest_window(
        tokens_path=tokens_path,
        db_path=db_path,
        date_from="2026-06-08T00:00:00.000-03:00",
        date_to="2026-06-15T00:00:00.000-03:00",
    )

    # 4) Validar
    conn = connect(db_path)
    orders = get_orders_in_range(conn, "2026-06-08", "2026-06-15")
    assert len(orders) == 1
    assert orders[0]["order_id"] == 1001

    items = conn.execute("SELECT * FROM items_cache").fetchall()
    assert items[0]["title"] == "Lanterna CG 150"

    cat = conn.execute("SELECT * FROM categories_cache").fetchall()
    assert cat[0]["name"] == "Iluminação"

    last_run = conn.execute("SELECT * FROM runs").fetchone()
    assert last_run["status"] == "ok"
    assert result["orders_fetched"] == 1


def test_main_help_lists_all_subcommands(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for subcmd in ["ingerir", "regerar-dados", "gerar-pdf", "abrir-dashboard"]:
        assert subcmd in out


def test_resolve_gerar_pdf_window_uses_last_seven_days_of_data() -> None:
    """Janela default = 7 dias terminando 1 dia após MAX(date_closed) do demo.db.

    demo.db paid MAX = 2026-07-31 → date_to=2026-08-01, date_from=2026-07-25.
    Bate com a janela do snapshot golden, garantindo reproducibilidade zero-arg.
    """
    date_from, date_to = _resolve_gerar_pdf_window(Path("data/demo.db"))
    assert date_from == "2026-07-25"
    assert date_to == "2026-08-01"


def test_default_pdf_output_uses_iso_week_naming() -> None:
    """RELATORIOS/relatorio-YYYY-WNN.pdf — WNN = ISO week de date_from."""
    # 2026-07-25 é sábado da ISO week 30
    assert _default_pdf_output("2026-07-25") == Path("RELATORIOS/relatorio-2026-W30.pdf")


def test_default_pdf_output_pads_week_below_ten() -> None:
    """Semana < 10 recebe zero à esquerda (W03, não W3)."""
    # 2026-01-15 = ISO week 3
    assert _default_pdf_output("2026-01-15") == Path("RELATORIOS/relatorio-2026-W03.pdf")


def _copy_demo_db(tmp_path: Path) -> Path:
    """Helper: copia demo.db versionado pro tmp_path/data/ (isola side effects do teste)."""
    src = Path("data/demo.db").resolve()
    (tmp_path / "data").mkdir(exist_ok=True)
    dst = tmp_path / "data" / "demo.db"
    dst.write_bytes(src.read_bytes())
    return dst


def test_cmd_gerar_pdf_default_invokes_render_with_derived_window(monkeypatch, tmp_path) -> None:
    """Sem args: chama render_pdf com janela derivada + path RELATORIOS/relatorio-YYYY-WNN.pdf."""
    _copy_demo_db(tmp_path)
    monkeypatch.chdir(tmp_path)

    captured: dict = {}

    def fake_render(**kwargs):
        captured.update(kwargs)
        return kwargs["output_path"]

    monkeypatch.setattr("src.pdf_renderer.render_pdf", fake_render)

    rc = main(["gerar-pdf"])
    assert rc == 0
    assert captured["date_from"] == "2026-07-25"
    assert captured["date_to"] == "2026-08-01"
    assert captured["output_path"] == Path("RELATORIOS/relatorio-2026-W30.pdf")
    assert captured["db_path"] == Path("data/demo.db")


def test_cmd_gerar_pdf_respects_from_to_flags(monkeypatch, tmp_path) -> None:
    """--from/--to substituem a janela derivada."""
    _copy_demo_db(tmp_path)
    monkeypatch.chdir(tmp_path)

    captured: dict = {}
    monkeypatch.setattr(
        "src.pdf_renderer.render_pdf",
        lambda **kw: captured.update(kw) or kw["output_path"],
    )

    rc = main(["gerar-pdf", "--from", "2026-06-01", "--to", "2026-06-08"])
    assert rc == 0
    assert captured["date_from"] == "2026-06-01"
    assert captured["date_to"] == "2026-06-08"


def test_cmd_gerar_pdf_respects_output_flag(monkeypatch, tmp_path) -> None:
    """--output substitui o path default."""
    _copy_demo_db(tmp_path)
    monkeypatch.chdir(tmp_path)

    captured: dict = {}
    monkeypatch.setattr(
        "src.pdf_renderer.render_pdf",
        lambda **kw: captured.update(kw) or kw["output_path"],
    )

    rc = main(["gerar-pdf", "--output", "custom/dir/meu.pdf"])
    assert rc == 0
    assert captured["output_path"] == Path("custom/dir/meu.pdf")


def test_main_abrir_dashboard_returns_not_implemented(capsys) -> None:
    rc = main(["abrir-dashboard"])
    assert rc == 0
    assert "não implementado" in capsys.readouterr().out.lower()


def test_main_without_subcommand_prints_help(capsys) -> None:
    rc = main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "ingerir" in err or "usage" in err.lower()


def test_main_regerar_dados_creates_demo_db(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["regerar-dados"])
    assert rc == 0
    demo_path = tmp_path / "data" / "demo.db"
    assert demo_path.exists()
    # Pin exact size: regression sentinel — if generator changes without
    # regenerating the versioned data/demo.db, CI catches the drift.
    assert demo_path.stat().st_size == 278528
