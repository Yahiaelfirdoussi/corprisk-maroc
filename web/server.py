"""FastAPI backend + single-page web interface.

Run:  uvicorn web.server:app --reload        (then open http://localhost:8000)

API (JSON unless noted):
  GET  /api/health                      liveness
  GET  /api/config                      provider, whether a key / password is configured
  GET  /api/demo                        the fictitious demo companies
  POST /api/demo/{company_id}           run the pipeline on a demo company
  POST /api/extract      (multipart)    read uploaded documents with the LLM -> draft to review
  POST /api/run                         run the pipeline on a reviewed draft
  POST /api/review/{thread_id}          record the human decision on an escalated file
  GET  /api/template.csv                transaction history template

Endpoints that spend API credits (extract, run, review) require the X-App-Password header
when APP_PASSWORD is set. Paused reviews and drafts live in memory: one process, lost on
restart (use a persistent LangGraph checkpointer for production).
"""
import hashlib
import hmac
import os
import uuid
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, ValidationError

from corprisk.config import DATA_DIR, SECTOR_RISK
from corprisk.documents import DOC_TYPES
from corprisk.data_access import list_companies, parse_transactions_csv
from corprisk.extraction import (Extraction, ExtractionError, UploadedFile, api_key_variable, extract,
                                 provider, to_company)
from corprisk.graph import build_graph

STATIC = Path(__file__).parent / "static"
MAX_FILES = 30
MAX_DRAFTS = 200

app = FastAPI(title="CorpRisk Maroc", version="2.0")
graph = build_graph()
drafts: "OrderedDict[str, dict]" = OrderedDict()


def require_password(x_app_password: str = Header(default="")) -> None:
    expected = os.getenv("APP_PASSWORD")
    if expected and not hmac.compare_digest(x_app_password.encode(), expected.encode()):
        raise HTTPException(401, "Password required.")


def _outcome(result: dict, thread_id: str) -> dict:
    """Shape a graph result for the web page."""
    company = result["company"]
    base = {"thread_id": thread_id,
            "company": {k: company.get(k) for k in ("company_id", "name", "legal_form", "city", "sector_label",
                                                    "requested_product")},
            "intake": result.get("intake"), "audit_log": result.get("audit_log", [])}
    if result.get("intake", {}).get("stopped"):
        return {"status": "stopped", **base}
    if "__interrupt__" in result:
        return {"status": "review", "review": result["__interrupt__"][0].value, **base}
    return {"status": "done", **base, "risk": result["risk"], "findings": result["assessed_findings"],
            "escalation": result.get("escalation"), "human_decision": result.get("human_decision"),
            "metrics": result.get("metrics", {}),
            "report_html": result["report_html"], "report_md": result["report_md"]}


def _invoke(initial: dict) -> dict:
    thread_id = uuid.uuid4().hex
    result = graph.invoke(initial, {"configurable": {"thread_id": thread_id}})
    return _outcome(result, thread_id)


# --- read-only endpoints ----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict:
    try:
        name, key_var = provider(), api_key_variable()
    except ExtractionError as e:
        return {"provider": None, "error": str(e), "key_configured": False,
                "password_required": bool(os.getenv("APP_PASSWORD"))}
    return {"provider": name, "key_configured": bool(os.getenv(key_var)), "key_variable": key_var,
            "password_required": bool(os.getenv("APP_PASSWORD")),
            "doc_types": DOC_TYPES, "sectors": [*SECTOR_RISK, "other"]}


@app.get("/api/demo")
def demo_companies() -> list[dict]:
    return list_companies()


@app.get("/api/template.csv")
def template() -> FileResponse:
    return FileResponse(DATA_DIR / "templates" / "transactions_template.csv", media_type="text/csv",
                        filename="transactions_template.csv")


@app.post("/api/demo/{company_id}")
def run_demo(company_id: str) -> dict:
    if company_id not in {c["company_id"] for c in list_companies()}:
        raise HTTPException(404, f"Unknown demo company {company_id}.")
    return _invoke({"company_id": company_id})


# --- upload flow --------------------------------------------------------------------

@app.post("/api/extract", dependencies=[Depends(require_password)])
def extract_documents(files: list[UploadFile] = File(...),
                      transactions: UploadFile | None = File(default=None)) -> dict:
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"At most {MAX_FILES} documents per file.")
    txn_text = None
    if transactions is not None and transactions.filename:
        txn_text = transactions.file.read().decode("utf-8-sig")
        try:  # validate before spending API credits
            n_txns = len(parse_transactions_csv(txn_text, "check"))
        except ValueError as e:
            raise HTTPException(400, f"Transactions CSV: {e}") from None
    else:
        n_txns = 0
    uploads = [UploadedFile(f.filename or f"file{i}", f.file.read()) for i, f in enumerate(files)]
    try:
        ex, note = extract(uploads)
    except ExtractionError as e:
        raise HTTPException(422, str(e)) from None

    draft_id = uuid.uuid4().hex
    drafts[draft_id] = {"file_names": [u.name for u in uploads], "transactions_csv": txn_text}
    while len(drafts) > MAX_DRAFTS:
        drafts.popitem(last=False)
    return {"draft_id": draft_id, "file_names": [u.name for u in uploads], "model_note": note,
            "transactions": n_txns, "extraction": ex.model_dump()}


# Fields added after the first release: filled in when an older page (cached script) omits them.
OPTIONAL_DOCUMENT_FIELDS = {"issued": "", "summary": "", "holder": "", "year": None}
OPTIONAL_FINANCIAL_FIELDS = {"interest_expense": None, "financial_debt": None, "annual_debt_service": None}


def _with_defaults(extraction: dict) -> dict:
    return {"requested_amount": None, "requested_product": "", **extraction,
            "warnings": extraction.get("warnings", []),
            "documents": [{**OPTIONAL_DOCUMENT_FIELDS, **d} for d in extraction.get("documents", [])],
            "financials": [{**OPTIONAL_FINANCIAL_FIELDS, **f} for f in extraction.get("financials", [])]}


class RunRequest(BaseModel):
    draft_id: str
    extraction: dict
    product: str
    amount_mad: int


@app.post("/api/run", dependencies=[Depends(require_password)])
def run_upload(req: RunRequest) -> dict:
    draft = drafts.get(req.draft_id)
    if not draft:
        raise HTTPException(404, "This draft has expired; upload the documents again.")
    try:
        reviewed = Extraction.model_validate(_with_defaults(req.extraction))
        if reviewed.incorporation_date:
            date.fromisoformat(reviewed.incorporation_date)
    except (ValidationError, ValueError) as e:
        raise HTTPException(400, f"Please fix the reviewed data: {e}") from None
    if req.amount_mad <= 0:
        raise HTTPException(400, "The requested amount must be positive.")
    company = to_company(reviewed, draft["file_names"], req.product.strip() or "Credit facility", req.amount_mad,
                         company_id=f"UPL-{uuid.uuid4().hex[:6]}")
    txns = parse_transactions_csv(draft["transactions_csv"], company["company_id"]) if draft["transactions_csv"] else []
    return _invoke({"company_id": company["company_id"], "company": company, "transactions": txns,
                    "as_of": date.today().isoformat(), "enforce_documents": True})


class ReviewRequest(BaseModel):
    decision: Literal["APPROVE_WITH_CONDITIONS", "REQUEST_INFORMATION", "REJECT", "PENDING"]
    reviewer: str = ""
    comment: str = ""


@app.post("/api/review/{thread_id}")
def review(thread_id: str, req: ReviewRequest) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.next:
        raise HTTPException(404, "No file is waiting for review under this id (it may have expired).")
    result = graph.invoke(Command(resume=req.model_dump()), config)
    return _outcome(result, thread_id)


# --- web page -------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _versioned_index() -> str:
    """index.html with ?v=<content hash> on the script and stylesheet, so browsers never run a stale copy."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for asset in ("app.js", "styles.css"):
        digest = hashlib.sha256((STATIC / asset).read_bytes()).hexdigest()[:10]
        html = html.replace(f"/static/{asset}", f"/static/{asset}?v={digest}")
    return html


INDEX_HTML = _versioned_index()


@app.get("/", include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML, headers={"Cache-Control": "no-cache"})
