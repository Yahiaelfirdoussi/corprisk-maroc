"""Agent 8 - Escalation + human-in-the-loop review for high-risk files.

The escalation agent prepares the compliance checklist. The human review node
then PAUSES the workflow (LangGraph interrupt) until an analyst or the
Compliance Officer records a decision. The system never takes that decision.
"""
from langgraph.types import interrupt

from ..state import DDState, log

AML_STR_CODES = {"AML-STRUCTURING", "AML-PASS-THROUGH", "AML-TURNOVER", "AML-CASH-INTENSITY", "SAN-MATCH"}


def escalation_agent(state: DDState) -> dict:
    findings = state.get("assessed_findings", [])
    order = {"critical": 0, "high": 1, "medium": 2}
    serious = [f for f in findings if f["severity"] in ("critical", "high")]
    actions, seen = [], set()
    for f in sorted((f for f in findings if f["severity"] in order), key=lambda f: order[f["severity"]]):
        if f["action"] not in seen:
            seen.add(f["action"])
            actions.append({"action": f["action"], "reason": f["title"], "severity": f["severity"],
                            "policy": f.get("policy_ref")})

    approvals = ["Compliance Officer"]
    if any(f["category"] == "financial" for f in serious) or state["risk"]["level"] == "High":
        approvals.append("Credit Committee")
    if any(f["code"] == "PEP" for f in findings):
        approvals.append("Senior management (PEP relationship)")

    str_assessment = any(f["code"] in AML_STR_CODES and f["severity"] in ("critical", "high") for f in findings)
    escalation = {
        "required": True,
        "approvals": approvals,
        "checklist": actions,
        "str_assessment_needed": str_assessment,
        "notes": ("Compliance must assess whether a suspicious transaction report (déclaration de soupçon) "
                  "to the ANRF is warranted. Do not inform the customer (no tipping-off).") if str_assessment else "",
    }
    return {"escalation": escalation,
            "audit_log": log("escalation", "prepared compliance escalation",
                             f"{len(actions)} action(s); approvals: {', '.join(approvals)}; STR assessment: {str_assessment}")}


def human_review_node(state: DDState) -> dict:
    decision = interrupt({
        "company": state["company"]["name"],
        "score": state["risk"]["score"],
        "level": state["risk"]["level"],
        "blocked": state["risk"]["blocked"],
        "checklist": state["escalation"]["checklist"],
        "question": "Record the reviewer decision: APPROVE_WITH_CONDITIONS, REQUEST_INFORMATION, REJECT or PENDING.",
    })
    decision = decision or {}
    record = {
        "decision": decision.get("decision", "PENDING"),
        "reviewer": decision.get("reviewer") or "not recorded",
        "comment": decision.get("comment", ""),
    }
    return {"human_decision": record,
            "audit_log": log("human_review", "reviewer decision recorded",
                             f"{record['decision']} by {record['reviewer']}")}
