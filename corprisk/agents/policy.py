"""Agent 6 - Policy (RAG): links every finding to the internal policy section that governs it."""
from ..policy_rag import get_index
from ..state import DDState, log


def policy_agent(state: DDState) -> dict:
    index = get_index()
    enriched = []
    for f in state.get("findings", []):
        hits = index.search(f.get("policy_query") or f["title"], doc_id=f.get("policy_doc"), k=1)
        if hits:
            chunk, score = hits[0]
            f = {**f, "policy_ref": chunk.ref, "policy_excerpt": chunk.text[:320] + ("…" if len(chunk.text) > 320 else ""),
                 "policy_score": round(score, 3)}
        enriched.append(f)
    return {
        "assessed_findings": enriched,
        "audit_log": log("policy", "retrieved governing policy sections",
                         f"{len(enriched)} finding(s) linked to {len({f.get('policy_ref') for f in enriched})} policy section(s)"),
    }
