"""Generate FICTITIOUS customer files to test the upload mode.

Run:  pip install -r requirements-dev.txt && python generate_samples.py
Writes sample_files/<scenario>/ : PDFs (statuts, modèle J, bilans, attestation fiscale,
UBO declaration, shareholder register), PNG identity cards marked SPECIMEN, and a
12-month transactions CSV. Every company, person and number is invented; names that
match data/watchlists.json are deliberate (they are fictitious watchlist entries).
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "sample_files"
BANNER = "DOCUMENT FICTIF - FICTITIOUS TEST DOCUMENT"


# --- renderers -------------------------------------------------------------------

def pdf(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> None:
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", "B", 10)
    doc.set_text_color(170, 30, 30)
    doc.cell(0, 6, BANNER, new_x="LMARGIN", new_y="NEXT", align="C")
    doc.set_text_color(0, 0, 0)
    doc.set_font("Helvetica", "B", 15)
    doc.multi_cell(0, 9, title, new_x="LMARGIN", new_y="NEXT", align="C")
    doc.ln(3)
    for heading, lines in sections:
        if heading:
            doc.set_font("Helvetica", "B", 11)
            doc.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        doc.set_font("Helvetica", "", 10)
        for line in lines:
            doc.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
        doc.ln(2)
    doc.output(str(path))


def id_card(path: Path, name: str, number: str, birth: str, nationality: str = "MAROCAINE") -> None:
    """A plainly fake identity card (no official design), stamped SPECIMEN."""
    img = Image.new("RGB", (860, 540), (236, 242, 240))
    d = ImageDraw.Draw(img)
    try:
        big, mid = ImageFont.truetype("Arial.ttf", 34), ImageFont.truetype("Arial.ttf", 26)
    except OSError:
        big = mid = ImageFont.load_default()
    d.rectangle([0, 0, 860, 70], fill=(15, 92, 77))
    d.text((24, 18), "CARTE D'IDENTITE - SPECIMEN FICTIF", font=big, fill="white")
    d.rectangle([30, 110, 250, 390], outline=(90, 90, 90), width=3)
    d.text((88, 235), "PHOTO", font=mid, fill=(120, 120, 120))
    rows = [("Nom / Name", name), ("N°", number), ("Né(e) le", birth), ("Nationalité", nationality),
            ("Valable jusqu'au", "2031-12-31")]
    for i, (label, value) in enumerate(rows):
        d.text((290, 115 + i * 56), f"{label} : {value}", font=mid, fill=(20, 20, 20))
    d.text((150, 440), "FICTITIOUS - TEST ONLY - NOT A REAL DOCUMENT", font=mid, fill=(170, 30, 30))
    img.save(path)


def transactions(path: Path, rows: list[dict]) -> None:
    rows.sort(key=lambda r: r["date"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "type", "amount_mad", "counterparty", "counterparty_country",
                                          "channel"])
        w.writeheader()
        w.writerows(rows)


def months(start=date(2025, 10, 1), end=date(2026, 9, 30)):
    d = start
    while d <= end:
        yield d
        d = date(d.year + d.month // 12, d.month % 12 + 1, 1)


def tx(d, t, amount, cp, cc, channel):
    return {"date": d.isoformat(), "type": t, "amount_mad": round(amount, 2), "counterparty": cp,
            "counterparty_country": cc, "channel": channel}


# --- shared document templates ------------------------------------------------------

def statuts(path, c):
    capital_lines = [f"  - {s['name']} ({s['desc']}) : {s['pct']} % du capital" for s in c["shareholders"]]
    pdf(path, f"STATUTS\n{c['name']}", [
        ("", [f"Société à responsabilité limitée au capital de {c['capital']} dirhams.",
              f"Siège social : {c['address']}."]),
        ("Article 2 - Objet", [c["activity"]]),
        ("Article 6 - Répartition du capital", capital_lines),
        ("Article 14 - Gérance", [f"La société est gérée par {c['manager']}, {c['manager_title']}."]),
        ("", [f"Fait à {c['city']}, le {c['signed']}."]),
    ])


def modele_j(path, c):
    pdf(path, "REGISTRE DE COMMERCE - MODÈLE J (EXTRAIT)", [
        ("", [f"Tribunal de commerce de {c['city']} - {c['rc']} (fictif)",
              f"Dénomination : {c['name'].upper()}",
              "Forme juridique : SARL",
              f"ICE : {c['ice']} (fictif)",
              f"Date d'immatriculation : {c['incorporated']}",
              f"Activité : {c['activity']}",
              f"Gérant : {c['manager']}, nationalité marocaine",
              "Extrait délivré le 2026-09-01."]),
    ])


def attestation(path, c):
    pdf(path, "ATTESTATION DE RÉGULARITÉ FISCALE", [
        ("", ["Direction Générale des Impôts (fictif) - Direction régionale de " + c["city"],
              f"Il est attesté que la société {c['name']}, ICE {c['ice']}, identifiant fiscal "
              f"{c['if']}, est en situation fiscale régulière à la date du 2026-08-20.",
              "Cette attestation est valable trois mois à compter de sa date de délivrance."]),
    ])


def bilan(path, c, year, f):
    pdf(path, f"ÉTATS DE SYNTHÈSE - EXERCICE {year}\n(montants en dirhams)", [
        ("", [f"{c['name']} - Exercice clos le 31/12/{year}"]),
        ("Compte de produits et charges (CPC)", [
            f"  Chiffre d'affaires : {f['revenue']:,}".replace(",", " "),
            f"  Excédent brut d'exploitation (EBE) : {f['ebitda']:,}".replace(",", " "),
            f"  Charges d'intérêts : {f['interest']:,}".replace(",", " "),
            f"  Remboursement du capital des emprunts : {f['principal']:,}".replace(",", " "),
            f"  Résultat net : {f['net_income']:,}".replace(",", " ")]),
        ("Bilan - Actif", [
            f"  Actif immobilisé : {f['fixed_assets']:,}".replace(",", " "),
            f"  Actif circulant : {f['current_assets']:,}".replace(",", " "),
            f"  Trésorerie actif : {f['cash']:,}".replace(",", " "),
            f"  TOTAL ACTIF : {f['fixed_assets'] + f['current_assets'] + f['cash']:,}".replace(",", " ")]),
        ("Bilan - Passif", [
            f"  Capitaux propres : {f['equity']:,}".replace(",", " "),
            f"  Dettes de financement : {f['lt_debt']:,}".replace(",", " "),
            f"  Passif circulant : {f['current_liabilities']:,}".replace(",", " "),
            f"  Trésorerie passif : {f['bank_overdraft']:,}".replace(",", " "),
            f"  TOTAL PASSIF : {f['equity'] + f['lt_debt'] + f['current_liabilities'] + f['bank_overdraft']:,}"
            .replace(",", " ")]),
    ])


def balanced(revenue, ebitda, interest, principal, net_income, equity, lt_debt, current_liabilities,
             bank_overdraft, current_assets, cash):
    """Financial year whose balance sheet balances (fixed assets are the plug)."""
    passif = equity + lt_debt + current_liabilities + bank_overdraft
    return dict(revenue=revenue, ebitda=ebitda, interest=interest, principal=principal, net_income=net_income,
                equity=equity, lt_debt=lt_debt, current_liabilities=current_liabilities,
                bank_overdraft=bank_overdraft, current_assets=current_assets, cash=cash,
                fixed_assets=passif - current_assets - cash)


# --- scenario 1: complete, low risk --------------------------------------------------

def clean_company(name, city, ice, rc, if_, manager, partner):
    return dict(
        name=name, city=city, ice=ice, rc=rc, **{"if": if_}, capital="3 000 000",
        address=f"Zone industrielle, {city}", activity="Fabrication et vente de carreaux céramiques.",
        incorporated="2012-05-21", signed="2012-05-02", manager=manager, manager_title="gérant unique",
        shareholders=[{"name": manager, "desc": "nationalité marocaine", "pct": 65},
                      {"name": partner, "desc": "nationalité marocaine", "pct": 35}],
    )


def clean_financials():
    return {
        2024: balanced(43_500_000, 6_400_000, 520_000, 1_600_000, 2_700_000, 26_000_000, 11_000_000,
                       13_500_000, 900_000, 24_000_000, 2_100_000),
        2025: balanced(47_800_000, 7_100_000, 480_000, 1_600_000, 3_050_000, 28_500_000, 9_500_000,
                       14_200_000, 700_000, 26_300_000, 2_800_000),
    }


def clean_transactions(rng):
    rows = []
    for m in months():
        for cp, cc in [("Bati Distribution Fictive SARL", "MA"), ("Casa Carrelage Fictif", "MA"),
                       ("Iberia Azulejos Ficticios SL", "ES")]:
            rows.append(tx(m + timedelta(days=rng.randint(0, 27)), "wire_in", rng.uniform(1.0e6, 1.6e6), cp, cc,
                           "SWIFT" if cc != "MA" else "Virement national"))
        for cp in ["Argiles du Saiss Fictif", "Energie Industrielle Fictive", "Transport Fes Fictif"]:
            rows.append(tx(m + timedelta(days=rng.randint(0, 27)), "wire_out", rng.uniform(0.7e6, 1.2e6), cp, "MA",
                           "Virement national"))
        rows.append(tx(m + timedelta(days=rng.randint(0, 27)), "cash_withdrawal", rng.uniform(25e3, 45e3),
                       "Caisse - salaires journaliers", "MA", "Agence Fes Centre"))
    return rows


def scenario_complete(rng):
    d = OUT / "01_complete_low_risk"
    d.mkdir(parents=True, exist_ok=True)
    c = clean_company("Fes Ceramique Fictive SARL", "Fes", "008888888000088", "RC Fes 88001", "88001234",
                      "Youssef Fictif Alami", "Leila Fictive Berrada")
    statuts(d / "statuts.pdf", c)
    modele_j(d / "modele_j.pdf", c)
    attestation(d / "attestation_fiscale.pdf", c)
    for y, f in clean_financials().items():
        bilan(d / f"bilan_{y}.pdf", c, y, f)
    id_card(d / "cnie_gerant.png", "Youssef Fictif Alami", "XF000001", "1975-04-12")
    transactions(d / "transactions_12_months.csv", clean_transactions(rng))


# --- scenario 2: incomplete (no tax certificate, no 2024 bilan, no manager ID) -----

def scenario_incomplete(rng):
    d = OUT / "02_incomplete"
    d.mkdir(parents=True, exist_ok=True)
    c = clean_company("Meknes Emballage Fictif SARL", "Meknes", "007777777000077", "RC Meknes 77001",
                      "77001234", "Hamza Fictif Chraibi", "Nora Fictive Lahlou")
    c["activity"] = "Fabrication d'emballages en carton."
    statuts(d / "statuts.pdf", c)
    modele_j(d / "modele_j.pdf", c)
    bilan(d / "bilan_2025.pdf", c, 2025, clean_financials()[2025])
    transactions(d / "transactions_12_months.csv", clean_transactions(rng))


# --- scenario 3: high risk ------------------------------------------------------------

def scenario_high_risk(rng):
    d = OUT / "03_high_risk"
    d.mkdir(parents=True, exist_ok=True)
    c = dict(
        name="Atlas Negoce International Fictif SARL", city="Casablanca", ice="006666666000066",
        rc="RC Casablanca 66001", **{"if": "66001234"}, capital="1 000 000", address="Bd Fictif, Casablanca",
        activity="Négoce général import-export (électronique, textile).", incorporated="2023-05-10",
        signed="2023-04-28", manager="Samira Bennis Alaoui", manager_title="gérante",
        shareholders=[{"name": "Samira Bennis Alaoui", "desc": "nationalité marocaine", "pct": 30},
                      {"name": "Coral Bay Holdings Ltd", "desc": "société de droit des Îles Vierges "
                                                             "britanniques (BVI)", "pct": 70}],
    )
    statuts(d / "statuts.pdf", c)
    modele_j(d / "modele_j.pdf", c)
    attestation(d / "attestation_fiscale.pdf", c)
    fin = {
        2024: balanced(9_800_000, 900_000, 210_000, 450_000, 380_000, 2_100_000, 3_500_000, 6_900_000,
                       1_200_000, 8_600_000, 400_000),
        2025: balanced(14_200_000, 1_150_000, 260_000, 500_000, 420_000, 2_500_000, 4_200_000, 9_800_000,
                       1_700_000, 11_900_000, 300_000),
    }
    for y, f in fin.items():
        bilan(d / f"bilan_{y}.pdf", c, y, f)
    id_card(d / "cnie_gerante.png", "Samira Bennis Alaoui", "XF000003", "1968-09-30")
    pdf(d / "declaration_beneficiaires_effectifs.pdf", "DÉCLARATION DES BÉNÉFICIAIRES EFFECTIFS", [
        ("", [f"Société déclarante : {c['name']} - ICE {c['ice']}",
              "Bénéficiaires effectifs (détention directe ou indirecte >= 25 %) :",
              "  - Samira Bennis Alaoui, nationalité marocaine, 30 % en direct",
              "  - Karim Fictif Tazi, nationalité marocaine, 70 % via Coral Bay Holdings Ltd (BVI), "
              "dont il détient 100 % du capital",
              "Fait à Casablanca, le 2026-07-15."]),
    ])
    pdf(d / "registre_actionnaires_coral_bay.pdf", "REGISTER OF MEMBERS - CORAL BAY HOLDINGS LTD", [
        ("", ["British Virgin Islands business company (fictitious), company no. FX-000666",
              "Registered agent: Fictional Corporate Services Ltd, Road Town, Tortola",
              "Members:",
              "  - Karim Fictif Tazi (Moroccan) - 50,000 shares - 100 %",
              "Certified extract dated 2026-06-30."]),
    ])
    rows = []
    for m in months():
        for _ in range(rng.randint(3, 5)):   # cash just below the 100,000 MAD threshold, several branches
            rows.append(tx(m + timedelta(days=rng.randint(0, 27)), "cash_deposit", rng.uniform(91_000, 99_500),
                           "Dépôt espèces", "MA", rng.choice(["Agence Derb Omar", "Agence Maarif", "Agence Anfa"])))
        d_in = m + timedelta(days=rng.randint(0, 24))
        amount = rng.choice([1_000_000, 1_500_000, 2_000_000])
        rows.append(tx(d_in, "wire_in", amount, "Coral Bay Holdings Ltd", "VG", "SWIFT"))
        rows.append(tx(d_in + timedelta(days=rng.randint(1, 2)), "wire_out", amount * rng.uniform(0.93, 0.98),
                       "Dubai Bright Trading FZE (fictif)", "AE", "SWIFT"))
        rows.append(tx(m + timedelta(days=rng.randint(0, 27)), "wire_in", rng.uniform(0.6e6, 1.0e6),
                       "Client Casablanca Fictif", "MA", "Virement national"))
    rows.append(tx(date(2026, 5, 14), "wire_out", 1_800_000, "Golden Crescent Shipping LLC", "AE", "SWIFT"))
    transactions(d / "transactions_12_months.csv", rows)


if __name__ == "__main__":
    rng = random.Random(7)
    scenario_complete(rng)
    scenario_incomplete(rng)
    scenario_high_risk(rng)
    for p in sorted(OUT.rglob("*.*")):
        print(p.relative_to(OUT))
