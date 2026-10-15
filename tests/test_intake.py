"""Tests for the upload flow: document gate, extraction mapping, robustness to partial data.

No API key needed: the Claude extraction is replaced by a hand-built Extraction (FICTITIOUS data).
"""
from datetime import date

import pytest

from corprisk.data_access import get_company, parse_transactions_csv
from corprisk.documents import missing_documents
from corprisk.extraction import (BeneficialOwner, DocumentInfo, Extraction, FinancialYear, Person,
                                 Shareholder, to_company)
from corprisk.graph import build_graph

AS_OF = "2026-10-15"


def _doc(i, doc_type, year=None, holder=""):
    return DocumentInfo(file_index=i, doc_type=doc_type, year=year, holder=holder, summary="")


def _fin(year, revenue):
    return FinancialYear(year=year, revenue=revenue, ebitda=revenue * 0.15, net_income=revenue * 0.06,
                         total_assets=revenue * 0.9, total_liabilities=revenue * 0.4, equity=revenue * 0.5,
                         current_assets=revenue * 0.5, current_liabilities=revenue * 0.3,
                         annual_debt_service=revenue * 0.05)


def _extraction(**overrides) -> Extraction:
    data = dict(
        company_name="FICTIONAL Test Industries SARL", legal_form="SARL", ice="000000000000001",
        rc="RC Rabat 1", city="Rabat", incorporation_date="2015-01-10", activity="Manufacturing of parts",
        sector="manufacturing",
        directors=[Person(name="Amina Fictive", role="Gérante", nationality="MA")],
        shareholders=[Shareholder(name="Amina Fictive", type="person", country="MA", pct=100, ubos=[])],
        financials=[_fin(2024, 40e6), _fin(2025, 44e6)],
        documents=[_doc(0, "statuts"), _doc(1, "modele_J"), _doc(2, "attestation_fiscale"),
                   _doc(3, "bilan", 2024), _doc(4, "bilan", 2025), _doc(5, "id_document", holder="AMINA FICTIVE")],
        warnings=[],
    )
    data.update(overrides)
    return Extraction(**data)


def _run(company):
    graph = build_graph()
    config = {"configurable": {"thread_id": company["company_id"]}}
    return graph.invoke({"company_id": company["company_id"], "company": company, "transactions": [],
                         "as_of": AS_OF, "enforce_documents": True}, config)


def test_complete_file_runs_all_agents():
    company = to_company(_extraction(), ["a.pdf"], "Equipment loan", 8_000_000, "T1")
    result = _run(company)
    assert result["intake"]["status"] == "complete"
    assert "risk" in result and result["report_html"]
    assert any(f["code"] == "AML-NO-DATA" for f in result["assessed_findings"])


def test_missing_documents_stop_pipeline():
    ex = _extraction(documents=[_doc(0, "statuts"), _doc(1, "bilan", 2025)])
    result = _run(to_company(ex, ["a.pdf"], "Equipment loan", 8_000_000, "T2"))
    assert result["intake"]["stopped"] is True
    assert "risk" not in result and "report_html" not in result
    missing = {m["code"] for m in result["intake"]["missing"]}
    assert missing == {"modele_J", "attestation_fiscale", "bilan_2024", "id:Amina Fictive"}
    assert all(m["policy"] for m in result["intake"]["missing"])


def test_offshore_shareholder_requires_register_and_ubo_declaration():
    ex = _extraction(shareholders=[
        Shareholder(name="Amina Fictive", type="person", country="MA", pct=40, ubos=[]),
        Shareholder(name="Fictional Holdings Ltd", type="company", country="VG", pct=60,
                    ubos=[BeneficialOwner(name="Karim Fictif", country="MA", pct_of_entity=100)]),
    ])
    company = to_company(ex, [], "Loan", 1_000_000, "T3")
    codes = {r.code for r in missing_documents(company, date.fromisoformat(AS_OF))}
    assert codes == {"declaration_ubo", "registre:Fictional Holdings Ltd"}


def test_young_company_not_asked_for_impossible_statements():
    ex = _extraction(incorporation_date="2025-03-01", financials=[_fin(2025, 10e6)],
                     documents=[_doc(0, "statuts"), _doc(1, "modele_J"), _doc(2, "attestation_fiscale"),
                                _doc(3, "bilan", 2025), _doc(4, "id_document", holder="Amina Fictive")])
    company = to_company(ex, [], "Loan", 8_000_000, "T4")
    assert missing_documents(company, date.fromisoformat(AS_OF)) == []


def test_partial_financials_do_not_crash():
    fy = _fin(2025, 20e6).model_copy(update={"current_liabilities": None, "annual_debt_service": None,
                                             "revenue": None})
    company = to_company(_extraction(financials=[fy], documents=[]), [], "Loan", 1_000_000, "T5")
    graph = build_graph()
    result = graph.invoke({"company_id": "T5", "company": company, "transactions": [], "as_of": AS_OF},
                          {"configurable": {"thread_id": "T5"}})
    codes = {f["code"] for f in result["assessed_findings"]}
    assert "FIN-INCOMPLETE" in codes and "KYC-DOCS" in codes


def test_demo_files_are_not_stopped():
    result = build_graph().invoke({"company_id": "C001"}, {"configurable": {"thread_id": "demo"}})
    assert result["intake"]["stopped"] is False and result["risk"]["score"] == 0


def test_demo_kyc_still_reports_missing_documents():
    company = get_company("C003")
    codes = [r.code for r in missing_documents(company, date(2026, 10, 14), strict=False)]
    assert codes == ["attestation_fiscale", "bilan_2025", "declaration_ubo"]


def test_transactions_csv_validation():
    ok = "date,type,amount_mad,counterparty,counterparty_country,channel\n2026-01-05,wire_in,100,A,FR,SWIFT\n"
    assert parse_transactions_csv(ok, "X")[0]["amount_mad"] == 100.0
    with pytest.raises(ValueError, match="type"):
        parse_transactions_csv(ok.replace("wire_in", "gift"), "X")
    with pytest.raises(ValueError, match="Missing column"):
        parse_transactions_csv("date,amount_mad\n2026-01-01,5\n", "X")
