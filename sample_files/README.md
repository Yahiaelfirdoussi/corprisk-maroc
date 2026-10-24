# Sample customer files (FICTITIOUS)

Test files for the **New analysis** mode. Every company, person, ID number and figure is invented;
each document is stamped "DOCUMENT FICTIF" (credit bureau reports come from a "Bureau de crédit FICTIF").
Regenerate with `python generate_samples.py`. The modèle J must be **less than 3 months old**
(POL-KYC-01 §1): the files are dated 20 days before generation, so regenerate them after ~2 months.

Upload **all files of one folder** (PDFs + PNG in the documents box, the CSV in the transactions box),
enter the credit request below, click **Read documents**, review, then **Run due diligence**.

| Folder | Credit request | Expected result |
|---|---|---|
| `01_complete_low_risk` — Fes Ceramique Fictive SARL | Equipment loan, **8,000,000 MAD** | Complete file, **0/100 Low**, standard due diligence |
| `02_incomplete` — Meknes Emballage Fictif SARL | Equipment loan, **8,000,000 MAD** | **Pipeline stops**: tax certificate, bilan 2024, the manager's ID and the credit bureau reports (company and both shareholders) are missing |
| `03_high_risk` — Atlas Negoce International Fictif SARL | Trade finance line, **12,000,000 MAD** | **100/100 High, BLOCKED**: payment to a sanctioned counterparty, PEP manager, BVI shareholder, cash structuring, pass-through, turnover far above revenue, high leverage, leveraged transaction (debt/EBITDA > 6), fails the stress test → human review |

Scenario 3 deliberately reuses fictitious names from `data/watchlists.json`
("Samira Bennis Alaoui" on the PEP list, "Golden Crescent Shipping LLC" on the sanctions list).

Results depend on the document reading: check the review tables before running. If a figure was
misread, correct it there.
