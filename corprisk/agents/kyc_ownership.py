"""Agent 3 - KYC & ownership: UBO identification, offshore structures, documents."""
from datetime import date

from ..config import (AS_OF_DATE, HIGH_SECRECY, LARGE_REQUEST_MAD, NEW_COMPANY_MONTHS,
                      SECTOR_RISK, UBO_THRESHOLD_PCT)
from ..state import DDState, log


def kyc_agent(state: DDState) -> dict:
    c = state["company"]
    findings, ubos = [], []
    as_of = date.fromisoformat(AS_OF_DATE)

    # --- beneficial owners -------------------------------------------------
    for s in c.get("shareholders", []):
        if s["type"] == "person" and s["pct"] >= UBO_THRESHOLD_PCT:
            ubos.append({"name": s["name"], "country": s["country"], "effective_pct": s["pct"], "via": "direct"})
        elif s["type"] == "company":
            if s["country"] in HIGH_SECRECY:
                findings.append({
                    "agent": "kyc", "category": "kyc", "code": "KYC-OFFSHORE",
                    "title": f"Shareholder in high-secrecy jurisdiction: {s['name']}",
                    "severity": "high",
                    "evidence": f"{s['name']} holds {s['pct']}% and is incorporated in {HIGH_SECRECY[s['country']]}.",
                    "policy_query": "offshore opaque structures high secrecy jurisdiction shareholder register UBO declaration economic rationale",
                    "policy_doc": "POL-KYC-01",
                    "action": "Obtain the offshore entity's shareholder register, a certified UBO declaration and the economic rationale.",
                })
            identified = 0
            for u in s.get("ubos", []):
                eff = s["pct"] * u["pct_of_entity"] / 100
                identified += u["pct_of_entity"]
                if eff >= UBO_THRESHOLD_PCT:
                    ubos.append({"name": u["name"], "country": u["country"], "effective_pct": eff, "via": s["name"]})
            if s["pct"] >= UBO_THRESHOLD_PCT and identified < 100:
                findings.append({
                    "agent": "kyc", "category": "kyc", "code": "KYC-UBO-UNKNOWN",
                    "title": "Beneficial owner not identified",
                    "severity": "critical" if identified == 0 else "high",
                    "evidence": f"{s['name']} holds {s['pct']}% but only {identified}% of its own ownership is identified.",
                    "policy_query": "beneficial owner 25% look through ownership chain not identified escalate compliance",
                    "policy_doc": "POL-KYC-01",
                    "action": "Look through the ownership chain to the natural persons; escalate to Compliance if not possible.",
                })

    for u in ubos:
        if u["country"] != "MA":
            findings.append({
                "agent": "kyc", "category": "kyc", "code": "KYC-FOREIGN-UBO",
                "title": f"Foreign beneficial owner: {u['name']}",
                "severity": "low",
                "evidence": f"{u['name']} ({u['country']}) holds an effective {u['effective_pct']:.0f}% ({u['via']}).",
                "policy_query": "beneficial owners identity documents natural person",
                "policy_doc": "POL-KYC-01",
                "action": "Collect passport and proof of address for the foreign UBO.",
            })

    # --- company age -------------------------------------------------------
    inc = date.fromisoformat(c["incorporation_date"])
    age_months = (as_of.year - inc.year) * 12 + as_of.month - inc.month
    if age_months < NEW_COMPANY_MONTHS:
        sev = "high" if c["requested_amount_mad"] > LARGE_REQUEST_MAD else "medium"
        findings.append({
            "agent": "kyc", "category": "inherent", "code": "KYC-NEW-COMPANY",
            "title": "Recently incorporated company",
            "severity": sev,
            "evidence": f"Incorporated {age_months} months ago ({c['incorporation_date']}); "
                        f"requested amount {c['requested_amount_mad']:,} MAD.",
            "policy_query": "newly incorporated companies less than 24 months enhanced due diligence site visit",
            "policy_doc": "POL-KYC-01",
            "action": "Perform enhanced due diligence and a site visit.",
        })

    # --- sector inherent risk ----------------------------------------------
    level, _pts = SECTOR_RISK.get(c["sector"], ("Medium", 5))
    if level != "Low":
        findings.append({
            "agent": "kyc", "category": "inherent", "code": "KYC-SECTOR",
            "title": f"{level} inherent-risk sector",
            "severity": "medium" if level == "High" else "low",
            "evidence": f"Sector: {c['sector_label']}.",
            "policy_query": "sector inherent risk real estate trading logistics classification",
            "policy_doc": "POL-KYC-01",
            "action": "Apply sector-specific vigilance.",
        })

    # --- document completeness ---------------------------------------------
    required = ["statuts", "modele_J", "attestation_fiscale"]
    if c["requested_amount_mad"] > LARGE_REQUEST_MAD:
        required += ["bilan_2024", "bilan_2025"]
    if any(s["type"] == "company" for s in c.get("shareholders", [])) or any(u["country"] != "MA" for u in ubos):
        required.append("declaration_ubo")
    missing = [d for d in required if d not in c.get("documents_on_file", [])]
    if missing:
        findings.append({
            "agent": "kyc", "category": "kyc", "code": "KYC-DOCS",
            "title": "Incomplete KYC / credit file",
            "severity": "high" if len(missing) >= 3 else "medium",
            "evidence": "Missing: " + ", ".join(missing) + ".",
            "policy_query": "identification legal entities statutes commercial register missing documents cannot be approved",
            "policy_doc": "POL-KYC-01",
            "action": "Request the missing documents before any decision.",
        })

    return {
        "findings": findings,
        "metrics": {"ubos": ubos, "company_age_months": age_months, "missing_documents": missing,
                    "sector_risk": level},
        "audit_log": log("kyc", "analysed ownership and KYC file",
                         f"{len(ubos)} UBO(s) identified, {len(missing)} missing document(s)"),
    }
