"""Agent 7 - Risk scoring: transparent, rule-based score with a per-category breakdown."""
from dateutil.relativedelta import relativedelta

from ..config import CATEGORY_CAPS, RISK_LEVELS, SEVERITY_POINTS
from ..state import DDState, analysis_date, log

BLOCKING_CODES = {"SAN-MATCH", "KYC-UBO-UNKNOWN", "AML-JURISDICTION"}
REVIEW_MONTHS = {"High": 12, "Medium": 24, "Low": 36}


def scoring_agent(state: DDState) -> dict:
    findings = state.get("assessed_findings", [])
    breakdown = {cat: 0 for cat in CATEGORY_CAPS}
    for f in findings:
        breakdown[f["category"]] = breakdown.get(f["category"], 0) + SEVERITY_POINTS[f["severity"]]
    breakdown = {cat: min(v, CATEGORY_CAPS[cat]) for cat, v in breakdown.items()}
    score = min(100, sum(breakdown.values()))

    blocking = [f for f in findings if f["severity"] == "critical" and f["code"] in BLOCKING_CODES]
    level = next(name for threshold, name in RISK_LEVELS if score >= threshold)
    if blocking:
        level = "High"

    if blocking:
        recommendation = ("DO NOT PROCEED. Critical issue(s) must be cleared by Compliance before any decision; "
                          "credit request on hold.")
        dd_level = "Enhanced (EDD) - blocked"
    elif level == "High":
        recommendation = "Enhanced due diligence required; decision reserved to the Compliance Officer and Credit Committee."
        dd_level = "Enhanced (EDD)"
    elif level == "Medium":
        recommendation = "Proceed with enhanced due diligence on the listed points before the Credit Committee."
        dd_level = "Enhanced (EDD) on specific points"
    else:
        recommendation = "Standard due diligence; the file can follow the normal credit approval circuit."
        dd_level = "Standard (SDD)"

    next_review = analysis_date(state) + relativedelta(months=REVIEW_MONTHS[level])
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("critical", "high", "medium", "low")}
    risk = {
        "score": score, "level": level, "blocked": bool(blocking), "breakdown": breakdown,
        "severity_counts": counts, "recommendation": recommendation, "due_diligence": dd_level,
        "next_review": next_review.isoformat(),
        "blocking_issues": [f["title"] for f in blocking],
    }
    return {"risk": risk,
            "audit_log": log("scoring", "computed risk score",
                             f"score={score}, level={level}, blocked={bool(blocking)}")}
