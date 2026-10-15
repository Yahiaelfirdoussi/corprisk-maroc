"""Data access layer.

In this demo the data comes from JSON/CSV files. In production replace these
functions with read-only queries to your core banking system, data warehouse,
the commercial register (OMPIC) extracts and your screening provider.
"""
import csv
import json
import re
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
