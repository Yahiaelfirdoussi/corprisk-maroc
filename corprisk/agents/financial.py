"""Agent 4 - Financial analysis: ratios against the credit risk appetite."""
from ..config import (LARGE_REQUEST_MAD, MAX_DEBT_TO_EQUITY, MAX_EXPOSURE_TO_REVENUE,
                      MIN_CURRENT_RATIO, MIN_DSCR, UNUSUAL_GROWTH)
from ..state import DDState, log


def _f(agent_code, title, severity, evidence, query, action):
    return {"agent": "financial", "category": "financial", "code": agent_code, "title": title,
            "severity": severity, "evidence": evidence, "policy_query": query,
            "policy_doc": "POL-CRD-04", "action": action}


def _ratio(a, b, digits: int) -> float | None:
    """a / b rounded, or None when a figure is missing or b is zero."""
    if a is None or not b:
        return None
    return round(a / b, digits)


def financial_agent(state: DDState) -> dict:
    c = state["company"]
    fin = c.get("financials", {})
    years = sorted(fin)
    findings = []
    if not years:
        return {"findings": [_f("FIN-NO-DATA", "No financial statements", "high", "No financial statements on file.",
                                "financial history two years statements required", "Obtain financial statements.")],
                "metrics": {"financial_ratios": {}},
                "audit_log": log("financial", "no financial data")}

    y = fin[years[-1]]
    equity = y.get("equity")
    ratios = {
        "year": years[-1],
        "revenue": y.get("revenue") or 0,
        "debt_to_equity": _ratio(y.get("total_liabilities"), equity, 2) if equity and equity > 0 else None,
        "current_ratio": _ratio(y.get("current_assets"), y.get("current_liabilities"), 2),
        "dscr": _ratio(y.get("ebitda"), y.get("annual_debt_service"), 2),
        "net_margin": _ratio(y.get("net_income"), y.get("revenue"), 3),
        "exposure_to_revenue": _ratio(c["requested_amount_mad"], y.get("revenue"), 2),
        "revenue_growth": None,
    }
    if len(years) >= 2:
        growth = _ratio(y.get("revenue"), fin[years[-2]].get("revenue"), 3)
        ratios["revenue_growth"] = round(growth - 1, 3) if growth is not None else None
    unknown = [k for k in ("revenue", "equity", "total_liabilities", "current_assets", "current_liabilities",
                           "ebitda", "net_income") if y.get(k) is None]
    if unknown:
        findings.append(_f("FIN-INCOMPLETE", "Financial statements partly unreadable", "low",
                           f"Not found in the {years[-1]} statements: {', '.join(unknown)}.",
                           "financial history statements required", "Check the figures manually."))

    if equity is not None and equity <= 0:
        findings.append(_f("FIN-NEG-EQUITY", "Negative equity", "high", f"Equity {equity:,} MAD.",
                           "negative net income negative equity recovery plan", "Request a recovery plan."))
    elif ratios["debt_to_equity"] is not None and ratios["debt_to_equity"] > MAX_DEBT_TO_EQUITY:
        findings.append(_f("FIN-LEVERAGE", "Leverage above risk appetite", "medium",
                           f"Debt-to-equity {ratios['debt_to_equity']} (limit {MAX_DEBT_TO_EQUITY}).",
                           "leverage debt to equity ratio exceed 3.0 guarantees",
                           "Require additional guarantees or reduce the exposure."))
    if ratios["current_ratio"] is not None and ratios["current_ratio"] < MIN_CURRENT_RATIO:
        findings.append(_f("FIN-LIQUIDITY", "Working capital pressure", "medium",
                           f"Current ratio {ratios['current_ratio']} (minimum {MIN_CURRENT_RATIO}).",
                           "liquidity current ratio below 1.0 working capital", "Review the cash-flow plan."))
    if ratios["dscr"] is not None and ratios["dscr"] < MIN_DSCR:
        sev = "high" if ratios["dscr"] < 1.0 else "medium"
        findings.append(_f("FIN-DSCR", "Weak debt service capacity", sev,
                           f"DSCR {ratios['dscr']} (minimum {MIN_DSCR}).",
                           "debt service coverage ratio EBITDA annual debt service 1.5",
                           "Strengthen guarantees or restructure the repayment schedule."))
    if ratios["net_margin"] is not None and ratios["net_margin"] < 0:
        findings.append(_f("FIN-LOSS", "Loss-making", "medium", f"Net margin {ratios['net_margin']:.1%}.",
                           "negative net income recovery plan", "Request a recovery plan."))
    if ratios["revenue_growth"] is not None and ratios["revenue_growth"] > UNUSUAL_GROWTH:
        findings.append(_f("FIN-GROWTH", "Unusual revenue growth", "medium",
                           f"Revenue grew {ratios['revenue_growth']:.0%} between {years[-2]} and {years[-1]}.",
                           "revenue growth above 100% unusual explained contracts audited accounts",
                           "Obtain contracts or audited accounts supporting the growth."))
    if c["requested_amount_mad"] > LARGE_REQUEST_MAD and len(years) < 2:
        findings.append(_f("FIN-HISTORY", "Insufficient financial history", "high",
                           f"Only {len(years)} year(s) of statements for a {c['requested_amount_mad']:,} MAD request.",
                           "financial history two years statements required above 5,000,000 MAD",
                           "Credit Committee exception required."))
    if ratios["exposure_to_revenue"] is not None and ratios["exposure_to_revenue"] > MAX_EXPOSURE_TO_REVENUE:
        sev = "high" if ratios["exposure_to_revenue"] > 1.0 else "medium"
        findings.append(_f("FIN-EXPOSURE", "Requested exposure large relative to size", sev,
                           f"Request = {ratios['exposure_to_revenue']:.0%} of annual revenue (limit {MAX_EXPOSURE_TO_REVENUE:.0%}).",
                           "exposure relative to size 50% annual revenue credit committee",
                           "Credit Committee approval required."))

    return {
        "findings": findings,
        "metrics": {"financial_ratios": ratios},
        "audit_log": log("financial", "computed credit ratios",
                         f"D/E={ratios['debt_to_equity']}, CR={ratios['current_ratio']}, DSCR={ratios['dscr']}"),
    }
