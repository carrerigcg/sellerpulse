"""Orquestração do backfill dos últimos 6 meses de dados ML.

Puro Python — zero import de streamlit. UI de progresso é passada via
callback opcional on_progress(fase, atual, total).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.ml_client import MLClient
from src.storage import (
    get_category_cache,
    get_item_cache,
    upsert_category_cache,
    upsert_claim,
    upsert_item_cache,
    upsert_order,
)


@dataclass
class IngestResult:
    """Sumário do que foi ingerido — mostrado no sidebar após conclusão."""

    total_orders: int = 0
    distinct_items: int = 0
    distinct_buyers: int = 0
    total_claims: int = 0
    warnings: list[str] = field(default_factory=list)


# ProgressCallback: chamada em cada fase da ingestão.
# Assinatura: (fase: str, atual: int, total: int) -> None
#   - fase: nome legível da fase corrente (ex: "Baixando pedidos pagos")
#   - atual: itens processados nesta fase
#   - total: itens totais nesta fase; 0 significa INDETERMINADO
#     (fase sem contagem prévia — a UI deve mostrar spinner, não barra;
#     não computar atual/total sem checar total > 0 antes)
ProgressCallback = Callable[[str, int, int], None]


def _noop_progress(_fase: str, _atual: int, _total: int) -> None:
    return None


def ingest_last_6_months(
    *,
    client: MLClient,
    seller_id: int,
    conn: sqlite3.Connection,
    on_progress: ProgressCallback | None = None,
    now: datetime | None = None,
) -> IngestResult:
    """Backfill dos últimos 6 meses de dados do vendedor `seller_id`.

    Sequencial (paid -> cancelled -> items -> categories -> claims), grava
    incrementalmente via storage.*. Falhas parciais preservam o que já
    foi persistido e aparecem em IngestResult.warnings.

    Args:
        client: MLClient já autenticado (access_token válido).
        seller_id: id numérico do vendedor (vem de /users/me).
        conn: SQLite :memory: com schema pronto (via create_session_db).
        on_progress: callback(fase, atual, total) — UI reage em tempo real.
        now: injetado nos testes para janela determinística. Default = agora.
    """
    progress = on_progress or _noop_progress
    now_ts = now or datetime.now(UTC)
    date_to = now_ts.isoformat()
    date_from = (now_ts - timedelta(days=180)).isoformat()

    result = IngestResult()

    # Fase 1: pedidos pagos
    progress("Baixando pedidos pagos", 0, 0)
    try:
        paid = client.get_orders(
            seller_id=seller_id,
            status="paid",
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:  # noqa: BLE001 — boundary
        result.warnings.append(f"Falha na fase pedidos pagos: {exc}")
        paid = []

    progress("Baixando pedidos cancelados", 0, 0)
    try:
        cancelled = client.get_orders(
            seller_id=seller_id,
            status="cancelled",
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Falha na fase pedidos cancelados: {exc}")
        cancelled = []

    all_orders = paid + cancelled
    total_orders_to_process = len(all_orders)
    persisted_count = 0

    # Fase 2 + 3 + 4: normaliza e persiste + enriquece items/categories inline
    item_ids_seen: set[str] = set()
    buyer_ids_seen: set[int] = set()
    for idx, raw in enumerate(all_orders, start=1):
        try:
            enrich_warnings = _persist_order(conn, client, raw, item_ids_seen)
        except Exception as exc:  # noqa: BLE001
            order_id = raw.get("id") or f"idx={idx}"
            result.warnings.append(f"Falha ao persistir pedido {order_id}: {exc}")
            continue
        result.warnings.extend(enrich_warnings)
        persisted_count += 1
        buyer = (raw.get("buyer") or {}).get("id")
        if buyer:
            buyer_ids_seen.add(int(buyer))
        progress("Processando pedidos", idx, total_orders_to_process)

    # Fase 5: claims
    progress("Baixando reclamações", 0, 0)
    try:
        claims = client.get_claims(seller_id=seller_id, date_from=date_from)
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Falha na fase claims: {exc}")
        claims = []

    for c in claims:
        try:
            upsert_claim(
                conn,
                {
                    "claim_id": c.get("id") or c.get("claim_id"),
                    "order_id": c.get("resource_id") or c.get("order_id"),
                    "status": c.get("status", "unknown"),
                    "date_created": c.get("date_created", date_from),
                    "raw_json": json.dumps(c),
                },
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Falha ao persistir claim: {exc}")

    result.total_orders = persisted_count
    result.distinct_items = len(item_ids_seen)
    result.distinct_buyers = len(buyer_ids_seen)
    result.total_claims = len(claims)
    progress("Concluído", total_orders_to_process, total_orders_to_process)
    return result


def _persist_order(
    conn: sqlite3.Connection,
    client: MLClient,
    raw: dict,
    item_ids_seen: set[str],
) -> list[str]:
    """Normaliza payload raw do ML e grava via storage.upsert_order.

    Enrichment (items_cache/categories_cache) roda DEPOIS do upsert em loop
    isolado — falha de API em um item não descarta a order já persistida.
    Retorna warnings coletados no enrichment. Exceptions só saem em erros de
    dados/persistência (payload malformado, DB error), sinalizando pro caller
    que a order não foi persistida.

    Espelha src/main._persist_order (mantido lá pra CLI da Fase 1 continuar
    funcionando; a consolidação dessas duas versões é refactor da Fase 6).
    """
    warnings: list[str] = []
    order_id = raw["id"]

    payments = raw.get("payments", []) or []
    marketplace_fee = sum(p.get("marketplace_fee", 0.0) or 0.0 for p in payments)
    shipping = raw.get("shipping", {}) or {}
    shipping_cost = shipping.get("list_cost", 0.0) or 0.0

    order_items: list[dict] = []
    for oi in raw.get("order_items", []) or []:
        item = oi.get("item", {}) or {}
        item_id = item.get("id")
        if not item_id:
            continue
        order_items.append(
            {
                "item_id": item_id,
                "quantity": oi.get("quantity", 1),
                "unit_price": oi.get("unit_price", 0.0),
            }
        )
        item_ids_seen.add(item_id)

    upsert_order(
        conn,
        {
            "order_id": order_id,
            "date_closed": raw.get("date_closed") or raw.get("date_created"),
            "status": raw["status"],
            "total_amount": raw.get("total_amount", 0.0),
            "marketplace_fee": marketplace_fee,
            "shipping_cost": shipping_cost,
            "buyer_id": (raw.get("buyer") or {}).get("id"),
            "raw_json": json.dumps(raw),
            "items": order_items,
        },
    )

    for oi_row in order_items:
        try:
            _ensure_item_cache(conn, client, oi_row["item_id"])
        except Exception as exc:  # noqa: BLE001 — boundary
            warnings.append(
                f"Falha ao enriquecer item {oi_row['item_id']} do pedido {order_id}: {exc}"
            )

    return warnings


def _ensure_item_cache(conn: sqlite3.Connection, client: MLClient, item_id: str) -> None:
    if get_item_cache(conn, item_id) is not None:
        return
    item = client.get_item(item_id)
    title = item.get("title", "")
    category_id = item.get("category_id", "")
    upsert_item_cache(conn, item_id, title, category_id)
    if category_id and get_category_cache(conn, category_id) is None:
        cat = client.get_category(category_id)
        upsert_category_cache(conn, category_id, cat.get("name", ""))
