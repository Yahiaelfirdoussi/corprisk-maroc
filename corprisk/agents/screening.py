"""Agent 2 - Sanctions / PEP / adverse media screening.

Screens the company, directors, shareholders, UBOs and transaction counterparties.
"""
from ..config import PEP_LOOKBACK_YEARS, POTENTIAL_MATCH, PROBABLE_MATCH
from ..data_access import get_watchlists
from ..name_matching import similarity
from ..state import DDState, analysis_date, log


def _parties(company: dict, txns: list[dict]) -> list[tuple[str, str]]:
    parties = [(company["name"], "company")]
    parties += [(d["name"], f"director ({d['role']})") for d in company.get("directors", [])]
    for s in company.get("shareholders", []):
        if s["type"] != "other":
            parties.append((s["name"], f"shareholder {s['pct']}%"))
        parties += [(u["name"], f"UBO via {s['name']}") for u in s.get("ubos", [])]
    for cp in sorted({t["counterparty"] for t in txns if t["type"].startswith("wire")}):
        parties.append((cp, "transaction counterparty"))
    seen, out = set(), []
    for name, role in parties:  # de-duplicate, keep first role
        if name not in seen:
            seen.add(name)
            out.append((name, role))
    return out


def screening_agent(state: DDState) -> dict:
    wl = get_watchlists()
    parties = _parties(state["company"], state["transactions"])
    findings, hits = [], 0
    as_of = analysis_date(state)

    for name, role in parties:
        for entry in wl["sanctions"]:
            s = similarity(name, entry["name"])
            if s >= POTENTIAL_MATCH:
                hits += 1
                probable = s >= PROBABLE_MATCH
                findings.append({
                    "agent": "screening", "category": "screening",
                    "code": "SAN-MATCH" if probable else "SAN-POTENTIAL",
                    "title": f"{'Probable' if probable else 'Potential'} sanctions match: {name}",
                    "severity": "critical" if probable else "high",
                    "evidence": f"{name} ({role}) matches '{entry['name']}' on {entry['list']} "
                                f"(similarity {s:.0%}; {entry['reason']}).",
                    "policy_query": "sanctions list match block relationship escalate compliance freeze",
                    "policy_doc": "POL-SAN-03",
                    "action": "Block pending transactions and escalate to Compliance to confirm or clear the match "
                              "(compare date of birth, nationality, identifiers).",
                })
        for entry in wl["pep"]:
            s = similarity(name, entry["name"])
            if s >= POTENTIAL_MATCH:
                until = entry.get("until")
                recent = until is None or (as_of.year - int(until)) <= PEP_LOOKBACK_YEARS
                hits += 1
                findings.append({
                    "agent": "screening", "category": "screening", "code": "PEP",
                    "title": f"Politically exposed person: {name}",
                    "severity": "high" if recent else "medium",
                    "evidence": f"{name} ({role}) matches PEP '{entry['name']}' - {entry['position']}"
                                f"{', until ' + until if until else ', current'} (similarity {s:.0%}).",
                    "policy_query": "politically exposed person PEP enhanced due diligence source of wealth senior management approval",
                    "policy_doc": "POL-SAN-03",
                    "action": "Verify source of wealth and source of funds; obtain senior management approval.",
                })
        for entry in wl["internal_blacklist"]:
            s = similarity(name, entry["name"])
            if s >= POTENTIAL_MATCH:
                hits += 1
                findings.append({
                    "agent": "screening", "category": "screening", "code": "BLACKLIST",
                    "title": f"Internal blacklist match: {name}",
                    "severity": "high",
                    "evidence": f"{name} ({role}) is on the internal blacklist: {entry['reason']} (similarity {s:.0%}).",
                    "policy_query": "internal blacklist compliance review before new product credit",
                    "policy_doc": "POL-SAN-03",
                    "action": "Compliance review required before any new product or credit.",
                })
        for entry in wl["adverse_media"]:
            s = similarity(name, entry["name"])
            if s >= POTENTIAL_MATCH:
                hits += 1
                findings.append({
                    "agent": "screening", "category": "screening", "code": "ADVERSE-MEDIA",
                    "title": f"Adverse media: {name}",
                    "severity": entry.get("severity", "medium"),
                    "evidence": entry["headline"],
                    "policy_query": "adverse media negative press reputational risk",
                    "policy_doc": "POL-SAN-03",
                    "action": "Document the press coverage and assess reputational risk.",
                })

    return {
        "findings": findings,
        "metrics": {"screened_parties": len(parties), "screening_hits": hits},
        "audit_log": log("screening", "screened parties against watchlists",
                         f"{len(parties)} parties screened, {hits} hit(s)"),
    }
