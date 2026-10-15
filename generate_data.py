"""Generate a FICTITIOUS 12-month transaction history for the demo companies.

Run:  python generate_data.py
Writes data/transactions.csv. The seed is fixed so results are reproducible.
Replace this file with an extract from your core banking system in production.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
START = date(2025, 10, 1)
END = date(2026, 9, 30)
rows = []
_id = 0


def add(cid, d, ttype, amount, counterparty, country, channel):
    global _id
    _id += 1
    rows.append({
        "txn_id": f"T{_id:06d}", "company_id": cid, "date": d.isoformat(),
        "type": ttype, "amount_mad": round(amount, 2),
        "counterparty": counterparty, "counterparty_country": country, "channel": channel,
    })


def month_starts():
    d = START
    while d <= END:
        yield d
        d = date(d.year + (d.month // 12), d.month % 12 + 1, 1)


def rand_day(m):
    return m + timedelta(days=random.randint(0, 27))


# C001 - clean exporter: EU buyers pay in, local suppliers paid out
for m in month_starts():
    for buyer, cc in [("Fruits du Sud SAS", "FR"), ("Hortaliza Iberica SA", "ES"), ("Dutch Fresh BV", "NL")]:
        add("C001", rand_day(m), "wire_in", random.uniform(1.2e6, 2.4e6), buyer, cc, "SWIFT")
    for sup, cc in [("Coopérative Souss Agrumes", "MA"), ("Emballages Agadir SARL", "MA"), ("Transport Frigo Sud", "MA")]:
        add("C001", rand_day(m), "wire_out", random.uniform(0.8e6, 1.6e6), sup, cc, "Virement national")
    add("C001", rand_day(m), "cash_withdrawal", random.uniform(20e3, 45e3), "Caisse - salaires journaliers", "MA", "Agence")

# C002 - logistics: mostly normal, a few offshore flows and one pass-through
for m in month_starts():
    for cl, cc in [("Renault Tanger Exploitation", "MA"), ("Iberia Freight Holdings SL", "ES"), ("Maersk Line Agency", "DK")]:
        add("C002", rand_day(m), "wire_in", random.uniform(0.9e6, 1.7e6), cl, cc, "SWIFT")
    for sup, cc in [("Tanger Med Port Authority", "MA"), ("Afriquia SMDC", "MA"), ("Leasing Equip Maroc", "MA")]:
        add("C002", rand_day(m), "wire_out", random.uniform(0.6e6, 1.3e6), sup, cc, "Virement national")
add("C002", date(2026, 2, 10), "wire_in", 1_500_000, "Pacific Cargo Trust SA", "PA", "SWIFT")
add("C002", date(2026, 2, 12), "wire_out", 1_450_000, "Seaview Consulting Ltd", "PA", "SWIFT")
add("C002", date(2026, 6, 3), "wire_in", 750_000, "Pacific Cargo Trust SA", "PA", "SWIFT")

# C003 - high-risk trading company: structuring, offshore pass-through, round amounts
for m in month_starts():
    # cash deposits just below the 100,000 MAD internal threshold, several per month
    for _ in range(random.randint(4, 7)):
        add("C003", rand_day(m), "cash_deposit", random.uniform(91_000, 99_800), "Dépôt espèces", "MA", random.choice(["Agence Derb Omar", "Agence Maarif", "Agence Ain Sebaa"]))
    # large round inflow from the offshore shareholder, quickly sent out
    d_in = rand_day(m)
    amt = random.choice([1_000_000, 1_500_000, 2_000_000, 2_500_000])
    add("C003", d_in, "wire_in", amt, "Bluewater Global Ventures Ltd", "VG", "SWIFT")
    cp, cc = random.choice([("Shenzhen Brightstar Trading", "HK"), ("Al Noor General Trading FZE", "AE")])
    add("C003", d_in + timedelta(days=random.randint(1, 2)), "wire_out", amt * random.uniform(0.93, 0.99), cp, cc, "SWIFT")
    add("C003", rand_day(m), "wire_out", random.choice([250_000, 500_000]), "Al Noor General Trading FZE", "AE", "SWIFT")

# C004 - real estate: buyers' funds from Cyprus, cash for villa sales, one sanctioned counterparty
for m in month_starts():
    add("C004", rand_day(m), "wire_in", random.choice([2_000_000, 3_000_000, 5_000_000]), "Aleksandrov Family Office Ltd", "CY", "SWIFT")
    for _ in range(random.randint(1, 3)):
        add("C004", rand_day(m), "cash_deposit", random.uniform(150_000, 600_000), "Avance acquéreur villa", "MA", "Agence Guéliz")
    for sup, cc in [("BTP Atlas Construction", "MA"), ("Marbre & Design Marrakech", "MA")]:
        add("C004", rand_day(m), "wire_out", random.uniform(1.5e6, 3.5e6), sup, cc, "Virement national")
add("C004", date(2026, 4, 18), "wire_out", 2_200_000, "Golden Crescent Shipping L.L.C.", "AE", "SWIFT")

rows.sort(key=lambda r: (r["company_id"], r["date"]))
out = Path(__file__).parent / "data" / "transactions.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"Wrote {len(rows)} transactions to {out}")
