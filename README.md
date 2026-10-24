# CorpRisk Maroc — AI agents for corporate due diligence

A prototype of an agentic KYC / AML / credit due diligence system for a Moroccan bank.
Upload a company's documents: an LLM reads them, a document gate stops the process if anything
required is missing, then ten agents collaborate in a LangGraph workflow to produce an auditable
risk report in which every finding cites the policy section that requires it.

**Live demo:** _add your Render link here_ — the **Demo files** tab runs instantly with no setup.

> All companies, people, identifiers and watchlists are **fictitious**. This is decision support:
> final decisions, and any suspicious transaction report to the ANRF, belong to authorised staff.

## How it works

1. **Upload** the customer file: statuts, modèle J, bilans, tax certificate, CNIE/passports, UBO
   declaration, credit bureau reports (PDF or photos, scans accepted), the credit request and,
   optionally, a 12-month transaction history (CSV).
2. **An LLM reads the documents** in one call with structured outputs: it classifies each file and
   extracts the company profile, directors, shareholders, beneficial owners, financial statements and
   document dates. A low-cost model reads first; a stronger model re-reads only when the first result
   fails or looks incomplete.
3. **You review** the extracted data in editable tables. The agents use the reviewed data, not the PDFs.
4. **Document gate.** The required documents are derived from the file itself. If anything is missing
   — for example a modèle J older than 3 months or a credit bureau report — the process **stops** and
   lists each document to request with the policy section that requires it.
5. **The agents assess the risk** and return a score, a recommendation and a full report. High-risk
   files **pause for a human decision** before the report is issued.

## The agents

| # | Agent | What it does |
|---|---|---|
| 1 | Data retriever | Loads the company file and its transactions |
| 2 | Document gate | Checks completeness; stops the process when required documents are missing |
| 3 | Screening | Fuzzy-matches the company, directors, shareholders, UBOs and counterparties against sanctions, PEP, internal blacklist and adverse media lists |
| 4 | KYC & ownership | Beneficial owners (≥25%, look-through), offshore structures, company age, sector risk |
| 5 | Financial analysis | Debt/equity, liquidity, DSCR and stressed DSCR (EBITDA −20%, rates +200 bp), interest cover, debt/EBITDA after the financing, growth, exposure vs revenue |
| 6 | Transaction monitoring | Cash structuring, cash intensity, turnover consistency, pass-through, high-risk jurisdictions, round amounts |
| 7 | Policy (RAG) | Links every finding to the governing section of the bank's policies |
| 8 | Risk scoring | Transparent 0–100 score with per-category caps and blocking issues |
| 9 | Escalation + human review | Compliance checklist and required approvals; pauses for the reviewer's decision |
| 10 | Report writer | HTML / Markdown / JSON report with a full audit trail |

```
upload → LLM reading → human review of the data
      → retriever → document gate ── incomplete → STOP: list of documents to request
                                  └─ complete  → screening │ KYC │ financial │ transactions   (in parallel)
                                               → policy (RAG) → scoring ── high risk → escalation → human decision ⏸
                                                                        └──────────────────────────────────────→ report
```

## Design choices

- **Deterministic detection, LLM only for reading.** Every flag comes from an explicit rule with its
  evidence, so results are reproducible and explainable to auditors and to the regulator.
- **Policy-grounded.** The policies in `policies/` state, section by section, the **regulatory
  requirement** (law 43-05, Bank Al-Maghrib circulars and directives, EBA/GL/2020/06, FATF, ECB) and the
  bank's **internal calibration** — the thresholds the code applies (`corprisk/config.py`).
- **Human in the loop.** The system never approves credit or files a report by itself.
- **Provider-agnostic.** Document reading works with OpenAI or Anthropic models, chosen by configuration.

## Tech stack

Python · LangGraph · FastAPI · OpenAI / Anthropic structured outputs · scikit-learn (TF-IDF policy
retrieval) · vanilla HTML/CSS/JS front end · Render

## Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...            # only needed to read uploaded documents; demo files work without it
uvicorn web.server:app --reload      # http://localhost:8000 — API docs at /docs
```

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Reads uploaded documents |
| `EXTRACTION_PROVIDER` | `openai` or `anthropic` (default: whichever key is set) |
| `EXTRACTION_MODEL`, `EXTRACTION_FALLBACK_MODEL` | Override the reading models |
| `APP_PASSWORD` | Protects the upload mode, which spends API credits |

**Deploy on Render:** New → Blueprint → select this repository; `render.yaml` configures the service.

## Limitations and path to production

- **Data:** connect the core banking system, the commercial register and a licensed screening provider.
- **Screening:** use a dedicated engine (Arabic/Latin transliteration, aliases, date-of-birth matching).
- **Policies:** check every regulatory reference against the official texts and use the bank's
  approved calibrations; move from TF-IDF to an embedding model.
- **Persistence:** paused reviews are kept in memory; use a database-backed checkpointer.
- **Governance:** model validation, access control, PII masking, monitoring, back-testing.
- **Data protection:** documents are sent to the LLM provider; for real customer data, check
  Compliance and CNDP requirements (law 09-08) and prefer an approved hosting region or on-premise model.
