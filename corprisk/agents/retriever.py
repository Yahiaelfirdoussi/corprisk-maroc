"""Agent 1 - Data Retriever: gathers the company file and its transactions.

Demo files are loaded from data/ by company_id. An uploaded file arrives already
built (company + transactions in the initial state) and is used as is.
"""
from ..data_access import get_company, get_transactions
from ..state import DDState, log


def retriever_agent(state: DDState) -> dict:
    if state.get("company"):
        company, txns, source = state["company"], state.get("transactions", []), "uploaded file"
    else:
        company, txns, source = get_company(state["company_id"]), get_transactions(state["company_id"]), "data store"
    return {
        "company": company,
        "transactions": txns,
        "audit_log": log("retriever", f"loaded company file ({source})",
                         f"{company['name']}: {len(company.get('financials', {}))} financial years, "
                         f"{len(txns)} transactions, {len(company.get('documents_on_file', []))} documents"),
    }
