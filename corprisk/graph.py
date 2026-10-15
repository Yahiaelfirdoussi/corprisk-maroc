"""LangGraph workflow wiring the agents together.

    START -> retriever -> document_check -- file incomplete (uploads) --> END
                                         -> [screening | kyc | financial | transactions]  (parallel)
          -> policy (RAG) -> scoring -> High risk?  -- yes --> escalation -> human_review (pause) -> report
                                                     -- no  --------------------------------------> report -> END
"""
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .agents.document_check import document_check_agent
from .agents.escalation import escalation_agent, human_review_node
from .agents.financial import financial_agent
from .agents.kyc_ownership import kyc_agent
from .agents.policy import policy_agent
from .agents.reporter import report_agent
from .agents.retriever import retriever_agent
from .agents.scoring import scoring_agent
from .agents.screening import screening_agent
from .agents.transactions import transaction_agent
from .state import DDState

ANALYSIS_AGENTS = {
    "screening": screening_agent,
    "kyc": kyc_agent,
    "financial": financial_agent,
    "transactions": transaction_agent,
}


def route_after_document_check(state: DDState) -> list[str] | str:
    return END if state["intake"]["stopped"] else list(ANALYSIS_AGENTS)


def route_after_scoring(state: DDState) -> str:
    return "escalation" if state["risk"]["level"] == "High" else "report"


def build_graph(checkpointer=None):
    g = StateGraph(DDState)
    g.add_node("retriever", retriever_agent)
    g.add_node("document_check", document_check_agent)
    for name, fn in ANALYSIS_AGENTS.items():
        g.add_node(name, fn)
    g.add_node("policy", policy_agent)
    g.add_node("scoring", scoring_agent)
    g.add_node("escalation", escalation_agent)
    g.add_node("human_review", human_review_node)
    g.add_node("report", report_agent)

    g.add_edge(START, "retriever")
    g.add_edge("retriever", "document_check")
    # fan-out: the 4 analysts run in parallel, unless the gate stopped an incomplete file
    g.add_conditional_edges("document_check", route_after_document_check, [*ANALYSIS_AGENTS, END])
    g.add_edge(list(ANALYSIS_AGENTS), "policy")   # fan-in: wait for all of them
    g.add_edge("policy", "scoring")
    g.add_conditional_edges("scoring", route_after_scoring, {"escalation": "escalation", "report": "report"})
    g.add_edge("escalation", "human_review")
    g.add_edge("human_review", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
