"""Data access layer.

In this demo the data comes from JSON/CSV files. In production replace these
functions with read-only queries to your core banking system, data warehouse,
the commercial register (OMPIC) extracts and your screening provider.
"""
import csv
import io
import json
import re
from datetime import date
from functools import lru_cache

from .config import DATA_DIR


@lru_cache
def _companies() -> dict:
    data = json.loads((DATA_DIR / "companies.json").read_text(encoding="utf-8"))
    return {c["company_id"]: c for c in data["companies"]}


def list_companies() -> list[dict]:
    return [{"company_id": c["company_id"], "name": c["name"], "city": c["city"], "sector": c["sector_label"]}
            for c in _companies().values()]


def get_company(company_id: str) -> dict:
    try:
        company = dict(_companies()[company_id])
    except KeyError:
        raise ValueError(f"Unknown company_id {company_id!r}") from None
    m = re.search(r"([\d,\.]+)\s*MAD", company.get("requested_product", ""))
    company["requested_amount_mad"] = int(m.group(1).replace(",", "").replace(".", "")) if m else 0
    return company


def get_transactions(company_id: str) -> list[dict]:
    with (DATA_DIR / "transactions.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["company_id"] == company_id]
    for r in rows:
        r["amount_mad"] = float(r["amount_mad"])
    return rows


@lru_cache
def get_watchlists() -> dict:
    return json.loads((DATA_DIR / "watchlists.json").read_text(encoding="utf-8"))


TXN_COLUMNS = ["date", "type", "amount_mad", "counterparty", "counterparty_country", "channel"]
TXN_TYPES = {"wire_in", "wire_out", "cash_deposit", "cash_withdrawal"}


def parse_transactions_csv(text: str, company_id: str) -> list[dict]:
    """Validate an uploaded 12-month transaction history (see data/templates/transactions_template.csv)."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in TXN_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(TXN_COLUMNS)}.")
    rows = []
    for n, r in enumerate(reader, start=2):
        if r["type"] not in TXN_TYPES:
            raise ValueError(f"Line {n}: type {r['type']!r} must be one of {', '.join(sorted(TXN_TYPES))}.")
        try:
            date.fromisoformat(r["date"])
            amount = float(r["amount_mad"])
        except ValueError:
            raise ValueError(f"Line {n}: date must be YYYY-MM-DD and amount_mad a number.") from None
        rows.append({**{c: r[c].strip() for c in TXN_COLUMNS}, "amount_mad": amount,
                     "txn_id": r.get("txn_id") or f"U{n:06d}", "company_id": company_id})
    return rows
