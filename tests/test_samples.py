"""The three sample customer files give the outcome documented in sample_files/README.md."""
from pathlib import Path

import pytest
from langgraph.types import Command

from corprisk.data_access import parse_transactions_csv
from corprisk.extraction import Extraction, to_company
from corprisk.graph import build_graph
from tests.samples import SAMPLES

ROOT = Path(__file__).parent.parent


def run_sample(name: str, as_of: str = "2026-10-24") -> dict:
    data, amount = SAMPLES[name]
    company = to_company(Extraction(**data), [], "Credit facility", amount, name)
    csv = (ROOT / "sample_files" / name / "transactions_12_months.csv").read_text(encoding="utf-8")
    graph, config = build_graph(), {"configurable": {"thread_id": name}}
    result = graph.invoke({"company_id": name, "company": company, "transactions": parse_transactions_csv(csv, name),
                           "as_of": as_of, "enforce_documents": True}, config)
    if "__interrupt__" in result:
        result = graph.invoke(Command(resume={"decision": "PENDING"}), config)
    return result


def test_complete_file_is_low_risk():
    r = run_sample("01_complete_low_risk")
    assert r["risk"]["score"] == 0 and r["risk"]["level"] == "Low"


def test_incomplete_file_is_stopped():
    r = run_sample("02_incomplete")
    assert r["intake"]["stopped"] and "risk" not in r
    assert {m["code"] for m in r["intake"]["missing"]} == {
        "attestation_fiscale", "bilan_2024", "id:Hamza Fictif Chraibi", "rapport_solvabilite",
        "bureau:Hamza Fictif Chraibi", "bureau:Nora Fictive Lahlou"}


@pytest.mark.parametrize("code", ["SAN-MATCH", "PEP", "KYC-OFFSHORE", "AML-STRUCTURING", "AML-PASS-THROUGH",
                                  "FIN-LEVERAGED", "FIN-STRESS"])
def test_high_risk_file_is_blocked(code):
    r = run_sample("03_high_risk")
    assert r["risk"]["blocked"] and r["risk"]["level"] == "High"
    assert code in {f["code"] for f in r["assessed_findings"]}
