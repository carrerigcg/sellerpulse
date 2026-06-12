"""Orquestrador da ingestão semanal — busca, enriquece e persiste dados ML.

Modos:
    python -m src.main                              # últimos 7 dias até agora
    python -m src.main --week=2026-W23              # semana ISO específica
    python -m src.main --from=YYYY-MM-DD --to=YYYY-MM-DD  # janela explícita
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.auth import OAuthClient, OAuthError, TokenStore, get_valid_access_token
from src.ml_client import MLAPIError, MLClient
from src.storage import (
    connect, get_category_cache, get_item_cache,
    log_run, upsert_category_cache, upsert_claim,
    upsert_item_cache, upsert_order,
)

DEFAULT_TOKENS_PATH = Path("data/tokens.json")
DEFAULT_DB_PATH = Path("data/historico.db")


def ingest_window(
    *,
    tokens_path: Path,
    db_path: Path,
    date_from: str,
    date_to: str,
) -> dict[str, int]:
    """Busca e persiste todos os dados ML para a janela [date_from, date_to)."""
    load_dotenv()
    client_id = os.environ["ML_CLIENT_ID"]
    client_secret = os.environ["ML_CLIENT_SECRET"]
    user_id = int(os.environ["ML_USER_ID"])

    store = TokenStore(tokens_path)
    oauth = OAuthClient(client_id=client_id, client_secret=client_secret, store=store)
    access_token = get_valid_access_token(oauth)
    ml = MLClient(access_token=access_token)
    conn = connect(db_path)

    try:
        orders_paid = ml.get_orders(
            seller_id=user_id, status="paid",
            date_from=date_from, date_to=date_to,
        )
        orders_cancelled = ml.get_orders(
            seller_id=user_id, status="cancelled",
            date_from=date_from, date_to=date_to,
        )
        all_orders = orders_paid + orders_cancelled

        for raw in all_orders:
            _persist_order(conn, ml, raw)

        claims = ml.get_claims(seller_id=user_id, date_from=date_from)
        for c in claims:
            upsert_claim(conn, {
                "claim_id": c.get("id") or c.get("claim_id"),
                "order_id": c.get("resource_id") or c.get("order_id"),
                "status": c.get("status", "unknown"),
                "date_created": c.get("date_created", date_from),
                "raw_json": json.dumps(c),
            })

        # Reputação — armazenada como singleton em users/{user_id}.
        # Por ora não persistimos separado; Setor 5 (cálculos) busca direto.
        # Apenas validamos que respondeu.
        ml.get_user(user_id)

        log_run(
            conn, week_start=date_from[:10], week_end=date_to[:10],
            pdf_path=None, status="ok", error_message=None,
        )
        return {
            "orders_fetched": len(all_orders),
            "claims_fetched": len(claims),
        }
    except (MLAPIError, OAuthError) as exc:
        log_run(
            conn, week_start=date_from[:10], week_end=date_to[:10],
            pdf_path=None, status="error", error_message=str(exc),
        )
        raise


def _persist_order(conn, ml: MLClient, raw: dict) -> None:
    """Converte payload bruto do ML para o formato do storage + enriquece itens."""
    payments = raw.get("payments", [])
    marketplace_fee = sum(p.get("marketplace_fee", 0.0) or 0.0 for p in payments)
    shipping = raw.get("shipping", {}) or {}
    shipping_cost = shipping.get("list_cost", 0.0) or 0.0

    order_items = []
    for oi in raw.get("order_items", []):
        item = oi.get("item", {}) or {}
        item_id = item.get("id")
        if not item_id:
            continue
        order_items.append({
            "item_id": item_id,
            "quantity": oi.get("quantity", 1),
            "unit_price": oi.get("unit_price", 0.0),
        })
        _ensure_item_cache(conn, ml, item_id)

    upsert_order(conn, {
        "order_id": raw["id"],
        "date_closed": raw.get("date_closed") or raw.get("date_created"),
        "status": raw["status"],
        "total_amount": raw.get("total_amount", 0.0),
        "marketplace_fee": marketplace_fee,
        "shipping_cost": shipping_cost,
        "buyer_id": (raw.get("buyer") or {}).get("id"),
        "raw_json": json.dumps(raw),
        "items": order_items,
    })


def _ensure_item_cache(conn, ml: MLClient, item_id: str) -> None:
    cached = get_item_cache(conn, item_id)
    if cached is not None:
        return
    item = ml.get_item(item_id)
    title = item.get("title", "")
    category_id = item.get("category_id", "")
    upsert_item_cache(conn, item_id, title, category_id)
    if category_id and get_category_cache(conn, category_id) is None:
        cat = ml.get_category(category_id)
        upsert_category_cache(conn, category_id, cat.get("name", ""))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingestão semanal Mercado Livre.")
    parser.add_argument("--week", help="Semana ISO no formato YYYY-WNN.")
    parser.add_argument("--from", dest="date_from", help="Início (YYYY-MM-DD).")
    parser.add_argument("--to", dest="date_to", help="Fim exclusivo (YYYY-MM-DD).")
    return parser.parse_args(argv)


def _resolve_window(args: argparse.Namespace) -> tuple[str, str]:
    if args.week:
        year, week = args.week.split("-W")
        start = datetime.fromisocalendar(int(year), int(week), 1)
        end = start + timedelta(days=7)
    elif args.date_from and args.date_to:
        start = datetime.fromisoformat(args.date_from)
        end = datetime.fromisoformat(args.date_to)
    else:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
    return start.isoformat(), end.isoformat()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    date_from, date_to = _resolve_window(args)
    try:
        result = ingest_window(
            tokens_path=DEFAULT_TOKENS_PATH, db_path=DEFAULT_DB_PATH,
            date_from=date_from, date_to=date_to,
        )
        print(f"OK — {result['orders_fetched']} pedidos, "
              f"{result['claims_fetched']} reclamações.")
        return 0
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
