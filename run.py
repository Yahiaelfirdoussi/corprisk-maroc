"""Command-line entry point.

Examples:
  python run.py --list
  python run.py C003                 # run one company, write reports/C003.md and .html
  python run.py --all                # run every demo company
  python run.py C004 --interactive   # pause at human review and type the decision
"""
import argparse
import json

from langgraph.types import Command

from corprisk.config import REPORT_DIR
from corprisk.data_access import list_companies
from corprisk.graph import build_graph


def run_one(company_id: str, interactive: bool) -> dict:
    graph = build_graph()
    config = {"configurable": {"thread_id": f"cli-{company_id}"}}
    result = graph.invoke({"company_id": company_id}, config)

    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print(f"\n⚠  {payload['company']} escalated: score {payload['score']} ({payload['level']}"
              f"{', BLOCKED' if payload['blocked'] else ''}). Workflow paused for human review.")
        for i, item in enumerate(payload["checklist"], 1):
            print(f"   {i}. {item['action']}  [{item['policy']}]")
        if interactive:
            decision = input("Decision (APPROVE_WITH_CONDITIONS / REQUEST_INFORMATION / REJECT / PENDING): ").strip().upper() or "PENDING"
            reviewer = input("Reviewer name: ").strip()
            comment = input("Comment: ").strip()
            resume = {"decision": decision, "reviewer": reviewer, "comment": comment}
        else:
            resume = {"decision": "PENDING"}
            print("   (non-interactive run: recorded as PENDING; use --interactive to enter a decision)")
        result = graph.invoke(Command(resume=resume), config)

    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / f"{company_id}.md").write_text(result["report_md"], encoding="utf-8")
    (REPORT_DIR / f"{company_id}.html").write_text(result["report_html"], encoding="utf-8")
    findings = result["assessed_findings"]
    (REPORT_DIR / f"{company_id}.json").write_text(json.dumps({
        "company_id": company_id, "risk": result["risk"], "findings": findings,
        "escalation": result.get("escalation"), "human_decision": result.get("human_decision"),
        "audit_log": result["audit_log"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    r = result["risk"]
    print(f"✔ {result['company']['name']}: {r['score']}/100 {r['level']}{' BLOCKED' if r['blocked'] else ''} "
          f"- {len(findings)} finding(s) -> reports/{company_id}.html")
    return result


def main():
    ap = argparse.ArgumentParser(description="CorpRisk Maroc - multi-agent corporate due diligence")
    ap.add_argument("company_id", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--interactive", action="store_true")
    a = ap.parse_args()
    if a.list or not (a.company_id or a.all):
        for c in list_companies():
            print(f"{c['company_id']}  {c['name']:<34} {c['city']:<11} {c['sector']}")
        return
    ids = [c["company_id"] for c in list_companies()] if a.all else [a.company_id]
    for cid in ids:
        run_one(cid, a.interactive)


if __name__ == "__main__":
    main()
