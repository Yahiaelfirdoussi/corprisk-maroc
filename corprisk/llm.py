"""Optional LLM layer used only to WRITE the narrative summary.

All detection, scoring and decisions are deterministic code, so the system is
explainable and auditable. The LLM only turns structured findings into prose.

Provider is chosen with the LLM_PROVIDER environment variable:
  none       (default) template-based narrative, no data leaves the machine
  anthropic  Claude API         -> ANTHROPIC_API_KEY, LLM_MODEL (default claude-sonnet-5-5)
  openai     any OpenAI-compatible endpoint, e.g. Mistral, Azure, or a model
             hosted inside the bank with Ollama / vLLM
             -> OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

Data residency: for real customer data, prefer a model hosted on-premise or in a
cloud region approved by Compliance, and only send the minimum data needed.
"""
import json
import os

SYSTEM_PROMPT = (
    "You are a senior KYC/AML analyst at a Moroccan bank. Write a concise due diligence "
    "summary (max 220 words) in {language} for the credit and compliance committee. "
    "Use ONLY the facts provided in the JSON. Do not invent facts, names or numbers. "
    "Cite policy references in brackets, e.g. [POL-AML-02 §1]. End with the recommended "
    "next steps. Never state that a suspicious transaction report must be filed; say that "
    "Compliance should assess it."
)


def _payload(state: dict) -> str:
    c = state["company"]
    return json.dumps({
        "company": {k: c.get(k) for k in ("name", "city", "sector_label", "incorporation_date", "requested_product")},
        "risk": state.get("risk"),
        "findings": [{k: f.get(k) for k in ("severity", "title", "evidence", "policy_ref")}
                     for f in state.get("assessed_findings", []) if f.get("severity") != "info"],
        "metrics": state.get("metrics"),
    }, ensure_ascii=False, default=str)


def generate_narrative(state: dict) -> tuple[str, str]:
    """Return (narrative, source). Falls back to the template on any error."""
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    language = os.getenv("REPORT_LANGUAGE", "English")
    system = SYSTEM_PROMPT.format(language=language)
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic()
            msg = client.messages.create(
                model=os.getenv("LLM_MODEL", "claude-sonnet-5-5"), max_tokens=700,
                system=system, messages=[{"role": "user", "content": _payload(state)}])
            return msg.content[0].text.strip(), f"anthropic:{msg.model}"
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
            model = os.getenv("LLM_MODEL", "mistral-large-latest")
            resp = client.chat.completions.create(model=model, max_tokens=700, messages=[
                {"role": "system", "content": system}, {"role": "user", "content": _payload(state)}])
            return resp.choices[0].message.content.strip(), f"openai-compatible:{model}"
    except Exception as e:  # never let the LLM break the pipeline
        return template_narrative(state) + f"\n\n_(LLM unavailable: {type(e).__name__}; template used.)_", "template"
    return template_narrative(state), "template"


def template_narrative(state: dict) -> str:
    c, risk = state["company"], state["risk"]
    findings = [f for f in state.get("assessed_findings", []) if f.get("severity") in ("critical", "high", "medium")]
    order = {"critical": 0, "high": 1, "medium": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    lines = [
        f"{c['name']} ({c['sector_label']}, {c['city']}) requests: {c['requested_product']}. "
        f"The automated review gives a risk score of {risk['score']}/100, classified **{risk['level']}**"
        + (" with a **blocking** issue." if risk.get("blocked") else ".")
    ]
    if findings:
        lines.append("Main concerns:")
        for f in findings[:6]:
            lines.append(f"- **{f['title']}** ({f['severity']}): {f['evidence']} [{f.get('policy_ref', '-')}]")
    else:
        lines.append("No material KYC, AML or credit concern was detected.")
    lines.append(f"Recommendation: {risk['recommendation']}")
    return "\n".join(lines)
