"""Document gate: checks the file is complete before any analysis runs.

For uploaded files (enforce_documents=True) a missing document stops the pipeline
and the user receives the list of documents to request, each with the policy that
requires it. For demo files the gate only records the result; the KYC agent then
reports missing documents as a finding.
"""
from ..documents import missing_documents, modele_j_age, required_documents
from ..state import DDState, analysis_date, log


def document_check_agent(state: DDState) -> dict:
    company = state["company"]
    as_of = analysis_date(state)
    missing = missing_documents(company, as_of, strict=True)
    required = required_documents(company, as_of, strict=True)
    notes = []
    if not company.get("shareholders"):
        notes.append("No shareholders could be identified; more documents (UBO declaration, registers) "
                     "may be required once the statuts and modèle J are provided.")
    if not company.get("directors"):
        notes.append("No directors could be identified; identity documents of the directors will be required.")
    if "modele_J" in company.get("documents_on_file", []) and modele_j_age(company, as_of)[0] is None:
        notes.append("The date of the modèle J could not be read: check that it is less than 3 months old.")
    stop = bool(state.get("enforce_documents")) and bool(missing)
    intake = {
        "status": "incomplete" if missing else "complete",
        "stopped": stop,
        "required": [r.as_dict() for r in required],
        "missing": [r.as_dict() for r in missing],
        "notes": notes,
    }
    detail = (f"{len(required) - len(missing)}/{len(required)} required documents on file"
              + (f"; missing: {', '.join(r.label for r in missing)}" if missing else ""))
    action = "file incomplete - pipeline stopped" if stop else "checked document completeness"
    return {"intake": intake, "audit_log": log("document_check", action, detail)}
