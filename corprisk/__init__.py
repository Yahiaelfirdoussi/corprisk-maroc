"""CorpRisk Maroc - multi-agent corporate due diligence prototype (LangGraph)."""
from langgraph.types import Command

from .graph import build_graph


def run_due_diligence(company_id: str, reviewer_decision: dict | None = None, thread_id: str | None = None,
                      graph=None) -> dict:
    """Run the full workflow. If the file is escalated, the workflow pauses for human
    review; `reviewer_decision` (dict with decision/reviewer/comment) is used to resume it.
    Without a decision the file is recorded as PENDING."""
    graph = graph or build_graph()
    config = {"configurable": {"thread_id": thread_id or f"dd-{company_id}"}}
    result = graph.invoke({"company_id": company_id}, config)
    if "__interrupt__" in result:
        result = graph.invoke(Command(resume=reviewer_decision or {"decision": "PENDING"}), config)
    return result
