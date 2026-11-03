"""Os links de fatura e comprovante não ficam no log de eventos do Asaas.

Daqui para frente pelo `sem_dados_pessoais`, e no que já estava gravado pela 0022.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.pagamentos import eventos

MIGRATION = (
    Path(__file__).resolve().parent.parent / "migrations" / "0022_eventos_sem_link_de_fatura.sql"
)
LINKS = ("invoiceUrl", "transactionReceiptUrl", "bankSlipUrl", "link")


def _estorno(evento_id="evt_estorno") -> dict:
    """No formato dos eventos guardados em produção, anonimizado."""
    return {
        "id": evento_id,
        "event": "PAYMENT_REFUNDED",
        "payment": {
            "id": "pay_1",
            "value": 49.9,
            "status": "REFUNDED",
            "dueDate": "2026-10-30",
            "invoiceUrl": "https://www.asaas.com/i/abc",
            "bankSlipUrl": None,
            "transactionReceiptUrl": "https://www.asaas.com/comprovantes/abc",
            "refunds": [
                {
                    "value": 49.9,
                    "status": "DONE",
                    "transactionReceiptUrl": "https://www.asaas.com/comprovantes/def",
                }
            ],
        },
        "checkout": {"id": "chk_x", "link": "https://www.asaas.com/checkoutSession/show/x"},
    }


def _sem_links(payload) -> bool:
    texto = json.dumps(payload)
    return all(f'"{chave}"' not in texto for chave in LINKS)


def test_o_payload_novo_sai_sem_os_links():
    limpo = eventos.sem_dados_pessoais(_estorno())
    assert _sem_links(limpo)
    assert limpo["payment"]["value"] == 49.9
    assert limpo["payment"]["refunds"] == [{"value": 49.9, "status": "DONE"}]
    assert limpo["checkout"] == {"id": "chk_x"}


async def test_a_migration_limpa_o_que_ja_estava_gravado(pg_pool):
    sql = MIGRATION.read_text(encoding="utf-8")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO eventos_do_gateway (id, tipo, payload) VALUES ($1, $2, $3::jsonb)",
            "evt_antigo",
            "PAYMENT_REFUNDED",
            json.dumps(_estorno("evt_antigo")),
        )
        try:
            await conn.execute(sql)
            # Rodar de novo não muda nada: a migration só toca quem ainda tem link.
            await conn.execute(sql)
            bruto = await conn.fetchval(
                "SELECT payload FROM eventos_do_gateway WHERE id = 'evt_antigo'"
            )
        finally:
            await conn.execute("DELETE FROM eventos_do_gateway WHERE id = 'evt_antigo'")
    payload = json.loads(bruto) if isinstance(bruto, str) else bruto
    assert _sem_links(payload)
    assert payload["payment"]["refunds"] == [{"value": 49.9, "status": "DONE"}]
    assert payload["payment"]["value"] == 49.9
    assert payload["checkout"] == {"id": "chk_x"}
