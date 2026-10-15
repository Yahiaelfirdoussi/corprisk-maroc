"""Streamlit web interface.   Run:  streamlit run app.py"""
import uuid

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from langgraph.types import Command

from corprisk.data_access import list_companies
from corprisk.graph import build_graph

st.set_page_config(page_title="CorpRisk Maroc", page_icon="🏦", layout="wide")
st.title("🏦 CorpRisk Maroc — Corporate Due Diligence Agents")
st.caption("Prototype · fictitious data · decision support only, final decisions by authorised staff")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
graph = st.session_state.graph

companies = list_companies()
labels = {f"{c['company_id']} · {c['name']} ({c['city']})": c["company_id"] for c in companies}
with st.sidebar:
    st.header("Customer file")
    choice = st.selectbox("Company", list(labels))
    if st.button("Run due diligence", type="primary", use_container_width=True):
        st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        with st.spinner("Agents working: screening, KYC, financials, transactions, policies…"):
            st.session_state.result = graph.invoke({"company_id": labels[choice]}, st.session_state.config)
    st.divider()
    st.markdown("**Agents**\n1. Data retriever\n2. Sanctions/PEP screening\n3. KYC & ownership\n4. Financial analysis\n"
                "5. Transaction monitoring\n6. Policy (RAG)\n7. Risk scoring\n8. Escalation + human review\n9. Report writer")

result = st.session_state.get("result")
if not result:
    st.info("Select a company and click **Run due diligence**.")
    st.stop()

# --- human-in-the-loop pause ------------------------------------------------
if "__interrupt__" in result:
    p = result["__interrupt__"][0].value
    st.error(f"**{p['company']}** escalated — score {p['score']}/100 ({p['level']}"
             f"{', BLOCKED' if p['blocked'] else ''}). The workflow is paused for your review.")
    st.subheader("Compliance checklist")
    for item in p["checklist"]:
        st.checkbox(f"{item['action']} — *{item['reason']}* `{item['policy']}`", key=item["action"])
    with st.form("review"):
        decision = st.radio("Decision", ["REQUEST_INFORMATION", "APPROVE_WITH_CONDITIONS", "REJECT", "PENDING"], horizontal=True)
        reviewer = st.text_input("Reviewer")
        comment = st.text_area("Comment")
        if st.form_submit_button("Record decision and finish report", type="primary"):
            st.session_state.result = graph.invoke(
                Command(resume={"decision": decision, "reviewer": reviewer, "comment": comment}), st.session_state.config)
            st.rerun()
    st.stop()

# --- final results -------------------------------------------------------------
risk, c = result["risk"], result["company"]
cols = st.columns(4)
cols[0].metric("Risk score", f"{risk['score']}/100")
cols[1].metric("Risk level", risk["level"] + (" · BLOCKED" if risk["blocked"] else ""))
cols[2].metric("Findings", len(result["assessed_findings"]))
cols[3].metric("Next review", risk["next_review"])
(st.error if risk["level"] == "High" else st.warning if risk["level"] == "Medium" else st.success)(risk["recommendation"])

tab_report, tab_findings, tab_audit = st.tabs(["Report", "Findings", "Audit trail"])
with tab_report:
    components.html(result["report_html"], height=1400, scrolling=True)
    st.download_button("Download HTML report", result["report_html"], file_name=f"{c['company_id']}_due_diligence.html")
    st.download_button("Download Markdown report", result["report_md"], file_name=f"{c['company_id']}_due_diligence.md")
with tab_findings:
    df = pd.DataFrame(result["assessed_findings"])
    if df.empty:
        st.success("No findings.")
    else:
        st.dataframe(df[["severity", "category", "code", "title", "evidence", "policy_ref", "action"]],
                     use_container_width=True, hide_index=True)
with tab_audit:
    st.dataframe(pd.DataFrame(result["audit_log"]), use_container_width=True, hide_index=True)
