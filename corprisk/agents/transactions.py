"""Agent 5 - Transaction monitoring: AML scenarios on the last 12 months."""
from collections import Counter
from datetime import date, timedelta

from ..config import (CASH_INTENSITY_MAX, CASH_THRESHOLD_MAD, FATF_CALL_FOR_ACTION, HIGH_SECRECY,
                      PASS_THROUGH_DAYS, PASS_THROUGH_MIN_SHARE, ROUND_AMOUNT_MAX_SHARE,
                      ROUND_AMOUNT_UNIT, STRUCTURING_LOWER_MAD, STRUCTURING_MIN_COUNT,
                      STRUCTURING_WINDOW_DAYS, TURNOVER_MAX_RATIO)
from ..state import DDState, log


def _f(code, title, severity, evidence, query, action):
    return {"agent": "transactions", "category": "transactions", "code": code, "title": title,
            "severity": severity, "evidence": evidence, "policy_query": query,
            "policy_doc": "POL-AML-02", "action": action}


def transaction_agent(state: DDState) -> dict:
    # work on copies so the shared state is never mutated by this agent
    txns = [{**t, "_d": date.fromisoformat(t["date"])} for t in state["transactions"]]
    c = state["company"]
    fin = c.get("financials", {})
    revenue = fin[max(fin)]["revenue"] if fin else 0
    findings = []
    cash_in = [t for t in txns if t["type"] == "cash_deposit"]
    wires_in = [t for t in txns if t["type"] == "wire_in"]
    wires_out = [t for t in txns if t["type"] == "wire_out"]
    credits = sum(t["amount_mad"] for t in cash_in + wires_in)
    cash_total = sum(t["amount_mad"] for t in cash_in)

    # 1. structuring: deposits just under the threshold, >= N inside a rolling window
    near = sorted((t for t in cash_in if STRUCTURING_LOWER_MAD <= t["amount_mad"] < CASH_THRESHOLD_MAD), key=lambda t: t["_d"])
    max_window, windows_flagged = 0, 0
    for i, t in enumerate(near):
        n = sum(1 for u in near[i:] if u["_d"] - t["_d"] <= timedelta(days=STRUCTURING_WINDOW_DAYS))
        max_window = max(max_window, n)
    months = {t["date"][:7] for t in near}
    for m in months:
        if sum(1 for t in near if t["date"].startswith(m)) >= STRUCTURING_MIN_COUNT:
            windows_flagged += 1
    if max_window >= STRUCTURING_MIN_COUNT:
        branches = {t["channel"] for t in near}
        findings.append(_f("AML-STRUCTURING", "Possible cash structuring", "high",
                           f"{len(near)} cash deposits between {STRUCTURING_LOWER_MAD:,} and {CASH_THRESHOLD_MAD - 1:,} MAD "
                           f"(total {sum(t['amount_mad'] for t in near):,.0f} MAD) across {len(branches)} branch(es); "
                           f"up to {max_window} within {STRUCTURING_WINDOW_DAYS} days, threshold breached in {windows_flagged} month(s).",
                           "cash deposit structuring just below reporting threshold 100,000 MAD several branches",
                           "Review deposit slips and depositors' identities; Compliance to assess a suspicious transaction report."))

    # 2. cash intensity
    cash_ratio = cash_total / revenue if revenue else 0
    if cash_ratio > CASH_INTENSITY_MAX:
        findings.append(_f("AML-CASH-INTENSITY", "High cash intensity", "high",
                           f"Cash deposits {cash_total:,.0f} MAD = {cash_ratio:.0%} of declared revenue (limit {CASH_INTENSITY_MAX:.0%}).",
                           "cash deposits exceed 30% declared annual revenue origin of funds",
                           "Obtain justification of the origin of the cash."))

    # 3. turnover consistency
    turnover_ratio = credits / revenue if revenue else 0
    if turnover_ratio > TURNOVER_MAX_RATIO:
        findings.append(_f("AML-TURNOVER", "Account credits inconsistent with declared revenue", "high",
                           f"12-month credits {credits:,.0f} MAD = {turnover_ratio:.0%} of declared revenue {revenue:,.0f} MAD.",
                           "turnover consistency total account credits exceeding 150% declared annual revenue",
                           "Obtain supporting documents for the excess inflows."))

    # 4. pass-through: international inflow mostly sent out within N days
    pass_through = []
    for w in wires_in:
        if w["counterparty_country"] == "MA":
            continue
        out = sum(o["amount_mad"] for o in wires_out
                  if o["counterparty_country"] != "MA" and timedelta(0) <= o["_d"] - w["_d"] <= timedelta(days=PASS_THROUGH_DAYS))
        if out >= PASS_THROUGH_MIN_SHARE * w["amount_mad"]:
            pass_through.append(w)
    if pass_through:
        sev = "high" if len(pass_through) >= 3 else "medium"
        total = sum(w["amount_mad"] for w in pass_through)
        findings.append(_f("AML-PASS-THROUGH", "Rapid pass-through of funds", sev,
                           f"{len(pass_through)} international inflow(s) totalling {total:,.0f} MAD were sent out "
                           f"(>= {PASS_THROUGH_MIN_SHARE:.0%}) within {PASS_THROUGH_DAYS} days.",
                           "pass-through incoming international transfer followed within 3 days outgoing 90% layering",
                           "Obtain invoices and contracts linking inflows and outflows."))

    # 5. high-risk jurisdictions
    by_country = Counter()
    amt_country = Counter()
    for t in wires_in + wires_out:
        cc = t["counterparty_country"]
        if cc in FATF_CALL_FOR_ACTION or cc in HIGH_SECRECY:
            by_country[cc] += 1
            amt_country[cc] += t["amount_mad"]
    if by_country:
        fatf = any(cc in FATF_CALL_FOR_ACTION for cc in by_country)
        detail = "; ".join(f"{(FATF_CALL_FOR_ACTION | HIGH_SECRECY)[cc]}: {n} transfer(s), {amt_country[cc]:,.0f} MAD"
                           for cc, n in by_country.items())
        findings.append(_f("AML-JURISDICTION", "Flows with high-risk jurisdictions", "critical" if fatf else "high",
                           detail + ".",
                           "transfers high-risk jurisdictions FATF high-secrecy country risk list counterparty contract invoice",
                           "Enhanced review of counterparties and underlying contracts."))

    # 6. round amounts on international wires
    intl = [t for t in wires_in + wires_out if t["counterparty_country"] != "MA"]
    rounds = [t for t in intl if t["amount_mad"] % ROUND_AMOUNT_UNIT == 0]
    round_share = len(rounds) / len(intl) if intl else 0
    if intl and round_share > ROUND_AMOUNT_MAX_SHARE:
        findings.append(_f("AML-ROUND", "High share of round-amount transfers", "medium",
                           f"{len(rounds)}/{len(intl)} international transfers ({round_share:.0%}) are multiples of {ROUND_AMOUNT_UNIT:,} MAD.",
                           "round-amount transfers multiples of 50,000 MAD without invoices non-commercial",
                           "Match transfers with commercial invoices."))

    # top counterparties for the report
    cp_tot = Counter()
    for t in wires_in + wires_out:
        cp_tot[(t["counterparty"], t["counterparty_country"])] += t["amount_mad"]
    metrics = {
        "txn_summary": {
            "count": len(txns), "total_credits": round(credits), "cash_deposits": round(cash_total),
            "cash_ratio": round(cash_ratio, 3), "turnover_ratio": round(turnover_ratio, 3),
            "near_threshold_deposits": len(near), "pass_through_events": len(pass_through),
            "round_share_international": round(round_share, 3),
            "top_counterparties": [{"name": n, "country": cc, "amount": round(a)} for (n, cc), a in cp_tot.most_common(5)],
        }
    }
    return {
        "findings": findings,
        "metrics": metrics,
        "audit_log": log("transactions", "ran AML scenarios",
                         f"{len(txns)} transactions, {len(findings)} scenario(s) triggered"),
    }
