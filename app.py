"""Streamlit web interface.   Run:  streamlit run app.py

Two modes:
  * Analyse a customer file: upload the company's documents, an LLM reads them, you review the
    extracted data, then the agents run. Missing documents stop the pipeline.
  * Demo companies: the 4 fictitious files shipped in data/.
"""
import hmac
import os
import uuid
from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from langgraph.types import Command
from pydantic import ValidationError

from corprisk.config import DATA_DIR, SECTOR_RISK
from corprisk.data_access import list_companies, parse_transactions_csv
from corprisk.documents import DOC_TYPES
from corprisk.extraction import (DocumentInfo, Extraction, ExtractionError, UploadedFile, api_key_variable,
                                 extract, provider, to_company)
from corprisk.graph import build_graph

st.set_page_config(page_title="CorpRisk Maroc", page_icon="🏦", layout="wide")
st.title("🏦 CorpRisk Maroc — Corporate Due Diligence Agents")
st.caption("Prototype · decision support only, final decisions by authorised staff")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
graph = st.session_state.graph


def records(df: pd.DataFrame) -> list[dict]:
    """Data-editor rows as dicts, empty cells as None, blank rows dropped."""
    df = df.astype(object).where(df.notna(), None)
    return [r for r in df.to_dict("records") if any(v not in (None, "") for v in r.values())]


def run_pipeline(initial: dict) -> None:
    st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    with st.spinner("Agents working: documents, screening, KYC, financials, transactions, policies…"):
        st.session_state.result = graph.invoke(initial, st.session_state.config)


def show_result() -> None:
    result = st.session_state.get("result")
    if not result:
        return
    st.divider()

    # --- document gate stopped the pipeline -----------------------------------
    intake = result.get("intake", {})
    if intake.get("stopped"):
        st.error(f"**Pipeline stopped — the file of {result['company']['name']} is incomplete.** "
                 f"{len(intake['missing'])} document(s) must be provided before the analysis can run.")
        st.dataframe(pd.DataFrame(intake["missing"])[["label", "reason", "policy"]]
                     .rename(columns={"label": "Document required", "reason": "Why", "policy": "Policy"}),
                     width="stretch", hide_index=True)
        for note in intake["notes"]:
            st.warning(note)
        letter = "\n".join([f"Documents to request from {result['company']['name']}:", ""]
                           + [f"- {m['label']} ({m['reason']} {m['policy']})" for m in intake["missing"]])
        st.download_button("Download the list of documents to request", letter,
                           file_name="documents_to_request.txt")
        st.info("Add the missing documents in step 1, click **Read documents** again, then re-run.")
        return

    # --- human-in-the-loop pause ---------------------------------------------------
    if "__interrupt__" in result:
        p = result["__interrupt__"][0].value
        st.error(f"**{p['company']}** escalated — score {p['score']}/100 ({p['level']}"
                 f"{', BLOCKED' if p['blocked'] else ''}). The workflow is paused for your review.")
        st.subheader("Compliance checklist")
        for item in p["checklist"]:
            st.checkbox(f"{item['action']} — *{item['reason']}* `{item['policy']}`", key=item["action"])
        with st.form("review"):
            decision = st.radio("Decision", ["REQUEST_INFORMATION", "APPROVE_WITH_CONDITIONS", "REJECT", "PENDING"],
                                horizontal=True)
            reviewer = st.text_input("Reviewer")
            comment = st.text_area("Comment")
            if st.form_submit_button("Record decision and finish report", type="primary"):
                st.session_state.result = graph.invoke(
                    Command(resume={"decision": decision, "reviewer": reviewer, "comment": comment}),
                    st.session_state.config)
                st.rerun()
        return

    # --- final results -----------------------------------------------------------
    risk, c = result["risk"], result["company"]
    cols = st.columns(4)
    cols[0].metric("Risk score", f"{risk['score']}/100")
    cols[1].metric("Risk level", risk["level"] + (" · BLOCKED" if risk["blocked"] else ""))
    cols[2].metric("Findings", len(result["assessed_findings"]))
    cols[3].metric("Next review", risk["next_review"])
    (st.error if risk["level"] == "High" else st.warning if risk["level"] == "Medium" else st.success)(
        risk["recommendation"])

    tab_report, tab_findings, tab_audit = st.tabs(["Report", "Findings", "Audit trail"])
    with tab_report:
        components.html(result["report_html"], height=1400, scrolling=True)
        st.download_button("Download HTML report", result["report_html"],
                           file_name=f"{c['company_id']}_due_diligence.html")
        st.download_button("Download Markdown report", result["report_md"],
                           file_name=f"{c['company_id']}_due_diligence.md")
    with tab_findings:
        df = pd.DataFrame(result["assessed_findings"])
        if df.empty:
            st.success("No findings.")
        else:
            st.dataframe(df[["severity", "category", "code", "title", "evidence", "policy_ref", "action"]],
                         width="stretch", hide_index=True)
    with tab_audit:
        st.dataframe(pd.DataFrame(result["audit_log"]), width="stretch", hide_index=True)


def password_ok() -> bool:
    """Optional protection of the upload mode (it spends API credits): set APP_PASSWORD."""
    expected = os.getenv("APP_PASSWORD")
    if not expected or st.session_state.get("auth"):
        return True
    pwd = st.text_input("Password", type="password")
    if pwd and hmac.compare_digest(pwd, expected):
        st.session_state.auth = True
        st.rerun()
    elif pwd:
        st.error("Wrong password.")
    return False


def upload_mode() -> None:
    if not password_ok():
        return
    try:
        key_var, provider_name = api_key_variable(), provider()
    except ExtractionError as e:
        st.error(str(e))
        return
    if not os.getenv(key_var):
        st.warning(f"{key_var} is not set: documents cannot be read. Set it in the environment "
                   "(Render: Environment tab) and restart.")
    st.caption(f"Documents are sent to the {provider_name.capitalize()} API for reading. Use fictitious or "
               "approved data only (CNDP / law 09-08).")

    # --- step 1: upload --------------------------------------------------------
    st.subheader("1 · Upload the customer file")
    files = st.file_uploader("Company documents: statuts, modèle J, bilans, attestation fiscale, CNIE/passports, "
                             "UBO declaration…", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    c1, c2 = st.columns([2, 1])
    product = c1.text_input("Credit request", "Medium-term equipment loan")
    amount = c2.number_input("Amount (MAD)", min_value=0, value=5_000_000, step=100_000)
    tx_file = st.file_uploader("12-month transaction history (CSV, optional)", type=["csv"])
    st.download_button("Download the CSV template", (DATA_DIR / "templates" / "transactions_template.csv")
                       .read_text(encoding="utf-8"), file_name="transactions_template.csv")

    if st.button("Read documents", type="primary", disabled=not files):
        try:
            uploads = [UploadedFile(f.name, f.getvalue()) for f in files]
            with st.spinner(f"Reading {len(uploads)} document(s)… (up to a minute or two)"):
                st.session_state.ex, st.session_state.model_note = extract(uploads)
            st.session_state.file_names = [f.name for f in uploads]
            st.session_state.pop("result", None)
        except ExtractionError as e:
            st.error(str(e))

    ex: Extraction | None = st.session_state.get("ex")
    if not ex:
        return

    # --- step 2: review --------------------------------------------------------
    st.subheader("2 · Review what was extracted")
    st.caption("Correct anything wrong before running the agents; the analysis uses this table, not the PDFs. "
               + st.session_state.get("model_note", ""))
    for w in ex.warnings:
        st.warning(w)

    names = st.session_state.file_names
    by_index = {d.file_index: d for d in ex.documents}
    docs_df = pd.DataFrame([{
        "file": n,
        "doc_type": by_index[i].doc_type if i in by_index else "other",
        "year": by_index[i].year if i in by_index else None,
        "holder": by_index[i].holder if i in by_index else "",
        "summary": by_index[i].summary if i in by_index else "Not classified",
    } for i, n in enumerate(names)])
    st.markdown("**Documents**")
    docs_df = st.data_editor(docs_df, hide_index=True, width="stretch", disabled=["file", "summary"], key="docs",
                             column_config={
                                 "doc_type": st.column_config.SelectboxColumn("Type", options=list(DOC_TYPES),
                                                                              required=True),
                                 "year": st.column_config.NumberColumn("Year (bilan)", format="%d"),
                                 "holder": st.column_config.TextColumn("Person / entity (ID, register)"),
                             })

    st.markdown("**Company**")
    a, b, c = st.columns(3)
    company_name = a.text_input("Name", ex.company_name)
    legal_form = b.text_input("Legal form", ex.legal_form)
    city = c.text_input("City", ex.city)
    ice = a.text_input("ICE", ex.ice)
    rc = b.text_input("RC", ex.rc)
    inc = c.text_input("Incorporation date (YYYY-MM-DD)", ex.incorporation_date)
    sectors = [*SECTOR_RISK, "other"]
    sector = a.selectbox("Sector", sectors, index=sectors.index(ex.sector))
    activity = b.text_input("Activity", ex.activity)

    st.markdown("**Directors / legal representatives**")
    directors = st.data_editor(pd.DataFrame([p.model_dump() for p in ex.directors],
                                            columns=["name", "role", "nationality"]),
                               num_rows="dynamic", hide_index=True, width="stretch", key="dirs")
    st.markdown("**Shareholders**")
    holders = st.data_editor(pd.DataFrame([s.model_dump(exclude={"ubos"}) for s in ex.shareholders],
                                          columns=["name", "type", "country", "pct"]),
                             num_rows="dynamic", hide_index=True, width="stretch", key="sh",
                             column_config={"type": st.column_config.SelectboxColumn(
                                 options=["person", "company", "other"], required=True)})
    st.markdown("**Beneficial owners behind corporate shareholders**")
    ubos = st.data_editor(pd.DataFrame([{"shareholder": s.name, **u.model_dump()}
                                        for s in ex.shareholders for u in s.ubos],
                                       columns=["shareholder", "name", "country", "pct_of_entity"]),
                          num_rows="dynamic", hide_index=True, width="stretch", key="ubos")
    st.markdown("**Financial statements (MAD)**")
    fin_cols = ["year", "revenue", "ebitda", "net_income", "total_assets", "total_liabilities", "equity",
                "current_assets", "current_liabilities", "annual_debt_service"]
    fins = st.data_editor(pd.DataFrame([f.model_dump() for f in ex.financials], columns=fin_cols),
                          num_rows="dynamic", hide_index=True, width="stretch", key="fin")

    # --- step 3: run --------------------------------------------------------------
    if st.button("Run due diligence", type="primary"):
        try:
            ubo_rows = records(ubos)
            reviewed = Extraction(
                company_name=company_name, legal_form=legal_form, ice=ice, rc=rc, city=city,
                incorporation_date=inc.strip(), activity=activity, sector=sector,
                directors=records(directors),
                shareholders=[{**s, "ubos": [u for u in ubo_rows if u["shareholder"] == s["name"]]}
                              for s in records(holders)],
                financials=records(fins),
                documents=[DocumentInfo(file_index=i, doc_type=r["doc_type"],
                                        year=int(r["year"]) if r["year"] else None,
                                        holder=r["holder"] or "", summary=r["summary"] or "")
                           for i, r in enumerate(records(docs_df))],
                warnings=ex.warnings,
            )
            if reviewed.incorporation_date:
                date.fromisoformat(reviewed.incorporation_date)
            company = to_company(reviewed, names, product, int(amount), company_id=f"UPL-{uuid.uuid4().hex[:6]}")
            txns = parse_transactions_csv(tx_file.getvalue().decode("utf-8-sig"), company["company_id"]) \
                if tx_file else []
        except (ValidationError, ValueError, TypeError) as e:
            st.error(f"Please fix the reviewed data: {e}")
            return
        run_pipeline({"company_id": company["company_id"], "company": company, "transactions": txns,
                      "as_of": date.today().isoformat(), "enforce_documents": True})
    show_result()


def demo_mode() -> None:
    companies = list_companies()
    labels = {f"{c['company_id']} · {c['name']} ({c['city']})": c["company_id"] for c in companies}
    choice = st.selectbox("Demo company (fictitious data)", list(labels))
    if st.button("Run due diligence", type="primary"):
        run_pipeline({"company_id": labels[choice]})
    show_result()


with st.sidebar:
    st.header("Mode")
    mode = st.radio("Mode", ["Analyse a customer file", "Demo companies"], label_visibility="collapsed")
    if st.session_state.get("mode") != mode:
        st.session_state.mode = mode
        st.session_state.pop("result", None)
    st.divider()
    st.markdown("**Agents**\n1. Data retriever\n2. Document check (stops if incomplete)\n"
                "3. Sanctions/PEP screening\n4. KYC & ownership\n5. Financial analysis\n"
                "6. Transaction monitoring\n7. Policy (RAG)\n8. Risk scoring\n9. Escalation + human review\n"
                "10. Report writer")

if mode == "Analyse a customer file":
    upload_mode()
else:
    demo_mode()
