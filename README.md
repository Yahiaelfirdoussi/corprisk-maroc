# CorpRisk Maroc — Multi-agent corporate due diligence (LangGraph)

A working prototype of an agentic KYC / AML / credit due diligence system for a Moroccan bank. 
Upload a company's documents (or pick a demo file): an LLM reads them,
a document gate stops the pipeline if anything required is missing, then ten agents collaborate in a
LangGraph workflow to produce an auditable risk report with policy references.

> **All data is fictitious** (companies, people, ICE/RC numbers, watchlists, policies).
> The policies are mock documents written in the spirit of law 43-05 and Bank Al-Maghrib vigilance
> requirements; replace them with your bank's approved procedures. This is decision support:
> final decisions, and any suspicious transaction report to the ANRF, belong to authorised staff.

## Quick start

```bash
pip install -r requirements.txt
python run.py --list               # the 4 demo companies
python run.py --all                # writes reports/C00X.html / .md / .json
python run.py C003 --interactive   # pauses for your decision at human review
uvicorn web.server:app --reload   # web interface + API on http://localhost:8000 (docs at /docs)
pip install -r requirements-dev.txt && pytest -q   # tests (no API key needed)
```

The demo mode runs fully offline. Reading uploaded documents needs `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

## Analyse your own customer file

In the web interface (tab **New analysis**):

1. **Upload** the company's documents (PDF or photos, scans accepted): statuts, modèle J, bilans,
   attestation fiscale, CNIE/passports, UBO declaration… plus the credit request and, optionally,
   the 12-month transaction history (CSV, template provided).
2. **An LLM reads them** in one call (`corprisk/extraction.py`, structured outputs): it classifies each
   file and extracts the company profile, directors, shareholders, beneficial owners and financials.
   A cheap model reads first (about $0.01 per file); if it fails, declines, or returns an incomplete
   result (no company name, a file left unclassified), a stronger model re-reads the file (about $0.20).
   Works with **OpenAI** (`gpt-6-luna` → `gpt-6.1-sol`, needs `OPENAI_API_KEY`) or **Anthropic**
   (`claude-haiku-5-5` → `claude-sonnet-5-5`, needs `ANTHROPIC_API_KEY`). Choose with
   `EXTRACTION_PROVIDER`; override models with `EXTRACTION_MODEL` / `EXTRACTION_FALLBACK_MODEL`.
3. **You review** everything in editable tables. The agents use the reviewed data, not the raw PDFs.
4. **Document gate.** The required documents are derived from the file itself (`corprisk/documents.py`):
   always statuts, modèle J, tax certificate and an ID for every director; two years of bilans above
   5M MAD; a UBO declaration when a shareholder is a company or a UBO is non-resident; the shareholder
   register of any offshore shareholder. **If anything is missing the pipeline stops** and lists each
   document with the reason and the policy section that requires it (downloadable as a request list).
5. Otherwise the agents run and you get the score, report and, for high risk, the human review step.

Documents are sent to the provider's API (OpenAI or Anthropic). Use fictitious data for demos; for real customer data check
Compliance / CNDP requirements (law 09-08) first.

## The agents

| # | Agent | What it does | File |
|---|---|---|---|
| 1 | Data retriever | Loads company profile, financials, shareholders, 12 months of transactions | `agents/retriever.py` |
| 1b | Document gate | Checks the file is complete; stops the pipeline for uploaded files with missing documents | `agents/document_check.py`, `documents.py` |
| 2 | Screening | Fuzzy-matches company, directors, shareholders, UBOs and counterparties against sanctions, PEP, internal blacklist, adverse media | `agents/screening.py` |
| 3 | KYC & ownership | Identifies UBOs (≥25%, look-through), offshore structures, company age, sector risk, missing documents | `agents/kyc_ownership.py` |
| 4 | Financial analysis | Debt/equity, current ratio, DSCR, margins, growth, exposure vs revenue | `agents/financial.py` |
| 5 | Transaction monitoring | Structuring, cash intensity, turnover consistency, pass-through, high-risk jurisdictions, round amounts | `agents/transactions.py` |
| 6 | Policy (RAG) | Links every finding to the governing internal policy section | `agents/policy.py`, `policy_rag.py` |
| 7 | Risk scoring | Transparent score 0–100 with per-category caps; blocking issues | `agents/scoring.py` |
| 8 | Escalation + human review | Compliance checklist, required approvals, STR-assessment flag; **pauses** for a human decision | `agents/escalation.py` |
| 9 | Report writer | Narrative (template or LLM) + HTML/Markdown/JSON report with audit trail | `agents/reporter.py`, `report.py` |

```
START → retriever → document gate ─ incomplete? → STOP (list of documents to request)
                    │
                    ┬ screening    ┐
                    ├ kyc          ├→ policy (RAG) → scoring ─ High? ─yes→ escalation → human_review ⏸ → report → END
                    ├ financial    │                           └─no──────────────────────────────────→ report
                    └ transactions ┘   (agents 2–5 run in parallel)
```

## Demo results

| Company | Profile | Result |
|---|---|---|
| C001 Atlas Agro Export (Agadir) | Clean exporter | 0/100 Low → standard due diligence |
| C002 Detroit Logistique (Tanger) | High leverage, Panama flows | 57/100 Medium → EDD on specific points |
| C003 Sahara Trading (Casablanca) | Structuring, BVI shareholder with unknown UBO, PEP, pass-through | 100/100 High, **blocked** |
| C004 Menara Prestige Immobilier (Marrakech) | Shareholder and a counterparty match sanctions list | 87/100 High, **blocked** |

## Design choices (why banks can accept it)

- **Deterministic detection, LLM only for prose.** Every flag comes from an explicit rule with evidence,
  so results are reproducible and explainable to auditors and Bank Al-Maghrib.
- **Policy-grounded.** Each finding cites the policy section that requires the action.
- **Human in the loop.** High-risk files pause (LangGraph `interrupt`) until a reviewer records a decision.
  The system never files an STR or approves credit by itself.
- **Audit trail.** Every agent logs what it did; the JSON output can be archived.
- **Configurable.** All thresholds live in `corprisk/config.py`.

## Optional LLM narrative

```bash
# Claude
pip install anthropic
export LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=...        # optional: LLM_MODEL=claude-sonnet-5-5
# Any OpenAI-compatible endpoint: Mistral, Azure, or a model hosted inside the bank (Ollama, vLLM)
pip install openai
export LLM_PROVIDER=openai OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama LLM_MODEL=qwen2.5
export REPORT_LANGUAGE=French                               # English / French / Arabic
```

If the LLM fails, the template narrative is used automatically. For real customer data, check with
Compliance / CNDP requirements (law 09-08) and prefer an on-premise model or an approved hosting region.

## Deploy

**Render:** New → Blueprint → pick this repo. `render.yaml` sets up a free web service running the
web app (`uvicorn web.server:app`, health check `/api/health`). Render asks for two secrets:
`OPENAI_API_KEY` (reads uploaded documents) and `APP_PASSWORD` (protects the upload mode, since it
spends API credits and the URL is public). To use Claude instead, set `EXTRACTION_PROVIDER=anthropic`,
clear the two model variables and add `ANTHROPIC_API_KEY`. Set `LLM_PROVIDER=anthropic` (or `openai` + `LLM_MODEL`) to also have an LLM write the
report narrative.

**Railway:** New Project → Deploy from GitHub repo; the `Procfile` provides the start command.

Note: the free tier sleeps when idle, so the first request after a pause takes ~30–60 s.

## Path to production

1. **Data:** replace `data_access.py` with read-only queries to the core banking system / data warehouse,
   OMPIC register extracts and the licensed screening provider (UN consolidated list, national list).
2. **Screening:** use a dedicated engine (Arabic/Latin transliteration, aliases, DOB matching).
3. **Policies:** load the bank's real procedures; move from TF-IDF to an internal embedding model + vector DB.
4. **Scenarios:** calibrate thresholds on historical alerts with the AML team (reduce false positives).
5. **Persistence:** swap `InMemorySaver` for a Postgres/SQLite checkpointer so paused reviews survive restarts.
6. **Governance:** model validation, access control (RBAC), PII masking, monitoring, periodic back-testing.

## Project structure

```
corprisk_maroc/
├── run.py · generate_data.py · generate_samples.py · requirements.txt
├── web/           server.py (FastAPI) + static/ (index.html, app.js, styles.css)
├── data/          companies.json, transactions.csv, watchlists.json, templates/   (fictitious)
├── policies/      POL-KYC-01, POL-AML-02, POL-SAN-03, POL-CRD-04       (mock)
├── corprisk/      config, state, graph, documents, extraction, data_access, name_matching, policy_rag, llm, report
│   └── agents/    retriever, document_check, screening, kyc_ownership, financial, transactions, policy, scoring,
│                  escalation, reporter
├── sample_files/  three fictitious customer files to upload
├── tests/         pytest (no API key needed)
└── reports/       generated reports
```
