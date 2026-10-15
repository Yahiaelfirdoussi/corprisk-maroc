"""Web API: demo runs, upload flow (fake extraction), document gate, human review, password.

No API key needed: extract() is replaced by a function returning a FICTITIOUS extraction.
"""
import pytest
from fastapi.testclient import TestClient

from tests.test_intake import _doc, _extraction
from web import server

PDF = ("statuts.pdf", b"%PDF-1.4 fictional", "application/pdf")
CSV = "date,type,amount_mad,counterparty,counterparty_country,channel\n2026-01-05,wire_in,100000,A,FR,SWIFT\n"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    return TestClient(server.app)


def _fake_extract(extraction):
    return lambda files: (extraction, "Read by fake-model.")


def test_page_and_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200 and "CorpRisk Maroc" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/template.csv").text.startswith("date,type,amount_mad")


def test_demo_low_risk(client):
    out = client.post("/api/demo/C001").json()
    assert out["status"] == "done" and out["risk"]["score"] == 0 and out["report_html"].startswith("<!doctype html>")


def test_demo_escalation_then_decision(client):
    out = client.post("/api/demo/C003").json()
    assert out["status"] == "review" and out["review"]["blocked"] is True
    done = client.post(f"/api/review/{out['thread_id']}",
                       json={"decision": "REJECT", "reviewer": "Analyst", "comment": "FICTIONAL test"}).json()
    assert done["status"] == "done" and done["human_decision"]["decision"] == "REJECT"
    # the same file cannot be decided twice
    assert client.post(f"/api/review/{out['thread_id']}", json={"decision": "REJECT"}).status_code == 404


def test_unknown_demo(client):
    assert client.post("/api/demo/C999").status_code == 404


def test_upload_incomplete_file_is_stopped(client, monkeypatch):
    ex = _extraction(documents=[_doc(0, "statuts")])
    monkeypatch.setattr(server, "extract", _fake_extract(ex))
    draft = client.post("/api/extract", files=[("files", PDF)]).json()
    assert draft["model_note"] == "Read by fake-model." and draft["transactions"] == 0
    out = client.post("/api/run", json={"draft_id": draft["draft_id"], "extraction": draft["extraction"],
                                        "product": "Loan", "amount_mad": 8_000_000}).json()
    assert out["status"] == "stopped"
    assert {m["code"] for m in out["intake"]["missing"]} >= {"modele_J", "attestation_fiscale"}


def test_upload_complete_file_runs_with_transactions(client, monkeypatch):
    monkeypatch.setattr(server, "extract", _fake_extract(_extraction()))
    draft = client.post("/api/extract", files=[("files", PDF), ("transactions", ("t.csv", CSV, "text/csv"))]).json()
    assert draft["transactions"] == 1
    out = client.post("/api/run", json={"draft_id": draft["draft_id"], "extraction": draft["extraction"],
                                        "product": "Loan", "amount_mad": 8_000_000}).json()
    assert out["status"] == "done" and out["metrics"]["txn_summary"]["count"] == 1


def test_bad_csv_rejected_before_any_ai_call(client, monkeypatch):
    called = []
    monkeypatch.setattr(server, "extract", lambda files: called.append(1))
    r = client.post("/api/extract", files=[("files", PDF), ("transactions", ("t.csv", "a,b\n1,2\n", "text/csv"))])
    assert r.status_code == 400 and "Missing column" in r.json()["detail"] and not called


def test_reviewed_data_is_validated(client, monkeypatch):
    monkeypatch.setattr(server, "extract", _fake_extract(_extraction()))
    draft = client.post("/api/extract", files=[("files", PDF)]).json()
    bad = {**draft["extraction"], "incorporation_date": "15/03/2014"}
    r = client.post("/api/run", json={"draft_id": draft["draft_id"], "extraction": bad, "product": "Loan",
                                      "amount_mad": 1_000_000})
    assert r.status_code == 400
    assert client.post("/api/run", json={"draft_id": "nope", "extraction": {}, "product": "", "amount_mad": 1}
                       ).status_code == 404


def test_password_protects_paid_endpoints(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "fictional-secret")
    monkeypatch.setattr(server, "extract", _fake_extract(_extraction()))
    assert client.get("/api/config").json()["password_required"] is True
    assert client.post("/api/extract", files=[("files", PDF)]).status_code == 401
    assert client.post("/api/extract", files=[("files", PDF)], headers={"X-App-Password": "wrong"}).status_code == 401
    ok = client.post("/api/extract", files=[("files", PDF)], headers={"X-App-Password": "fictional-secret"})
    assert ok.status_code == 200
    assert client.post("/api/demo/C001").status_code == 200   # demo stays free and open
