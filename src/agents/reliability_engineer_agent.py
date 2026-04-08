from typing import Dict


def run_reliability_engineer_agent(metric_summary: Dict[str, float]) -> Dict[str, object]:
    sev = "low"
    if metric_summary["time_to_ride_confirmation_sec"] > 160 or metric_summary["rejections_per_successful_ride"] > 4.0:
        sev = "high"
    elif metric_summary["time_to_ride_confirmation_sec"] > 130 or metric_summary["rejections_per_successful_ride"] > 3.0:
        sev = "medium"

    guardrails = {
        "confirmation_time_hotspot": metric_summary["time_to_ride_confirmation_sec"] > 150,
        "marketplace_friction_high": metric_summary["rejections_per_successful_ride"] > 3.8,
    }

    recommendation = "Keep rollout on current pace."
    if sev == "medium":
        recommendation = "Slow rollout and increase monitoring frequency."
    if sev == "high":
        recommendation = "Pause rollout and prioritize reliability hotfix."

    return {
        "agent": "Reliability Engineer Agent",
        "incident_severity": sev,
        "guardrails": guardrails,
        "recommendation": recommendation,
    }
