"""Shared state passed between the agents of the LangGraph workflow.

Fields annotated with a reducer (operator.add / merge_dicts) can be written by
several agents running in parallel; LangGraph combines their outputs.
"""
import operator
from datetime import date, datetime, timezone
from typing import Annotated, Any, TypedDict

from .config import AS_OF_DATE


def merge_dicts(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


class Finding(TypedDict, total=False):
    agent: str            # which agent raised it
    category: str         # screening | kyc | transactions | financial | inherent
    code: str             # short rule code, e.g. AML-STRUCTURING
    title: str
    severity: str         # info | low | medium | high | critical
    evidence: str         # facts supporting the finding
    policy_query: str     # text used to retrieve the governing policy
    policy_doc: str       # optional policy id to restrict retrieval
    policy_ref: str       # filled by the policy agent
    policy_excerpt: str
    action: str           # what the analyst should do


class DDState(TypedDict, total=False):
    company_id: str
    as_of: str                    # analysis date (ISO); defaults to config.AS_OF_DATE
    enforce_documents: bool       # True: stop the pipeline when required documents are missing
    intake: dict[str, Any]        # result of the document gate
    company: dict[str, Any]
    transactions: list[dict[str, Any]]
    findings: Annotated[list[Finding], operator.add]   # raw, appended by parallel agents
    assessed_findings: list[Finding]                    # findings enriched with policy refs
    metrics: Annotated[dict[str, Any], merge_dicts]
    audit_log: Annotated[list[dict[str, Any]], operator.add]
    risk: dict[str, Any]
    escalation: dict[str, Any]
    human_decision: dict[str, Any]
    narrative: str
    report_md: str
    report_html: str


def log(agent: str, action: str, detail: str = "") -> list[dict]:
    """Return a one-item audit log list (to be merged into state)."""
    return [{
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": agent, "action": action, "detail": detail,
    }]


def analysis_date(state: dict) -> date:
    return date.fromisoformat(state.get("as_of") or AS_OF_DATE)
