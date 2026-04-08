import json
from typing import Any, Dict

from src.llm.client import call_ollama


def _extract_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def run_llm_agent(role: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""
You are a {role} in a ride-booking launch war room.
Feature under analysis: show users driver rejection count during ride search.
Important terminology:
- Correct: "riders are rejected by drivers"
- Incorrect: "drivers are rejected by riders"
- Keep analysis feature-specific (do not generalize to whole app health).

Task:
{task}

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
