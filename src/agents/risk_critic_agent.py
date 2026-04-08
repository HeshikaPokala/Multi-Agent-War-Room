from typing import Dict, List


def run_risk_critic_agent(metric_summary: Dict[str, float], feedback_summary: Dict[str, object]) -> Dict[str, object]:
    risks: List[Dict[str, str]] = []

    if metric_summary["rejections_per_successful_ride"] > 3.8:
        risks.append(
            {
                "risk": "High marketplace friction may normalize repeated rejection loops.",
                "severity": "high",
                "mitigation": "Tune dispatch logic and introduce smarter retry suggestions.",
            }
        )
    if metric_summary["cancellation_dropoff_rate_pct"] > 30.0:
        risks.append(
            {
                "risk": "Visible rejection counts may increase rider frustration and abandonment.",
                "severity": "high",
                "mitigation": "A/B test alternate framing and show confidence-building UX prompts.",
            }
        )
    if feedback_summary["negative_ratio"] > 0.5:
        risks.append(
            {
                "risk": "Negative sentiment may amplify support load and social backlash.",
                "severity": "medium",
                "mitigation": "Publish status communication and proactive customer outreach.",
            }
        )

    return {
        "agent": "Risk/Critic Agent",
        "risk_register": risks,
        "critic_note": "Current evidence is sufficient for a temporary pause decision if thresholds are breached.",
    }
