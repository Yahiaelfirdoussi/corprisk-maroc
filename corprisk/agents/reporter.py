"""Agent 9 - Report synthesizer: narrative (LLM or template) + Markdown/HTML report."""
from ..llm import generate_narrative
from ..report import render_html, render_markdown
from ..state import DDState, log


def report_agent(state: DDState) -> dict:
    narrative, source = generate_narrative(state)
    entry = log("reporter", "wrote report", f"narrative source: {source}")
    full = {**state, "narrative": narrative, "audit_log": state.get("audit_log", []) + entry,
            "metrics": {**state.get("metrics", {}), "narrative_source": source}}
    return {
        "narrative": narrative,
        "metrics": {"narrative_source": source},
        "report_md": render_markdown(full),
        "report_html": render_html(full),
        "audit_log": entry,
    }
