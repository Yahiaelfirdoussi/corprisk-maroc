"""Agent 1 - Data Retriever: gathers the company file and its transactions."""
from ..data_access import get_company, get_transactions
from ..state import DDState, log


def retriever_agent(state: DDState) -> dict:
    company = get_company(state["company_id"])
    txns = get_transactions(state["company_id"])
    return {
        "company": company,
        "transactions": txns,
        "audit_log": log("retriever", "loaded company file",
                         f"{company['name']}: {len(company.get('financials', {}))} financial years, "
                         f"{len(txns)} transactions, {len(company.get('documents_on_file', []))} documents"),
    }
