import json
from typing import Any, Dict

from src.llm.client import call_ollama


def _narrative_tone_block(context: Dict[str, Any]) -> str:
    scenario = str(context.get("scenario", "baseline"))
    fs = context.get("feedback_summary") or {}
    neg = float(fs.get("negative_ratio", 0.0))

    if scenario == "optimistic":
        return f"""
NARRATIVE TONE (mandatory — scenario is optimistic):
This run uses the optimistic dataset: overall metrics and sentiment skew healthy (e.g. feedback negative_ratio in context is {neg:.3f} unless you see otherwise).
- summary and findings MUST be net-positive: lead with strengthening ride confirmation, driver acceptance, falling rejections per success, and contained drop-off/churn. Describe rejection-count visibility as delivering transparency without breaking core funnel health.
- If retry_rate_pct looks high but cancellation_dropoff_rate_pct is not elevated, interpret retries as marketplace or fare exploration, not mass user failure.
- recommendation: support continuing rollout with routine monitoring.
- risk_flags: use [] or at most one low-severity watch item (e.g. "keep monitoring retries").
- Do NOT open with frustration, trust collapse, revenue loss, or hypothetical widespread rejection pain unless negative_ratio >= 0.45 or the metric_summary clearly shows breach-level deterioration.
"""
    if scenario == "critical":
        return """
NARRATIVE TONE (mandatory — scenario is critical):
This run uses the critical dataset: stress degradation. Emphasize rising friction, sentiment pressure, support load, and need for mitigation. findings and risk_flags should reflect real hazards in context; summary may be cautionary.
"""
    return """
NARRATIVE TONE (scenario baseline):
Balanced war-room voice. Acknowledge tradeoffs of showing rejection counts: transparency benefits vs. perceived rejection stress. Cite both supportive and concerning signals from metric_summary and feedback_summary.
"""


def _extract_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def run_llm_agent(role: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    tone = _narrative_tone_block(context)
    prompt = f"""
You are a {role} in a ride-booking launch war room.
Feature under analysis: show users driver rejection count during ride search.
Important terminology:
- Correct: "riders are rejected by drivers"
- Incorrect: "drivers are rejected by riders"
- Keep analysis feature-specific (do not generalize to whole app health).

Task:
{task}
{tone}
Context JSON:
{json.dumps(context, indent=2)}

Return ONLY valid JSON with this exact shape:
{{
  "agent": "{role}",
  "summary": "short summary",
  "findings": ["bullet1", "bullet2"],
  "recommendation": "specific recommendation",
  "decision_lean": "Proceed|Pause|Roll Back",
  "risk_flags": ["risk1", "risk2"]
}}
"""
    raw = call_ollama(prompt)
    result = _extract_json(raw)
    # Safety normalization for common phrasing errors.
    for key in ["summary", "recommendation"]:
        if isinstance(result.get(key), str):
            result[key] = (
                result[key]
                .replace("drivers were rejected", "riders were rejected by drivers")
                .replace("drivers are rejected", "riders are rejected by drivers")
            )
    if isinstance(result.get("findings"), list):
        result["findings"] = [
            str(item)
            .replace("drivers were rejected", "riders were rejected by drivers")
            .replace("drivers are rejected", "riders are rejected by drivers")
            for item in result["findings"]
        ]
    return result
