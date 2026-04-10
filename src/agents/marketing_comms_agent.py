from typing import Dict


def run_marketing_comms_agent(feedback_summary: Dict[str, object], scenario: str = "baseline") -> Dict[str, object]:
    top_tags = feedback_summary["top_issue_tags"]

    if scenario == "optimistic":
        external_guidance = (
            "Celebrate wider rollout of rejection-count transparency as proof the marketplace is actively working; pair with rider tips on fares and wait times."
        )
        internal_guidance = (
            "Arm support with rider quotes on trust and clarity; keep macros focused on education, not apology loops."
        )
    else:
        external_guidance = "Explain rejection count transparency as a rider decision aid and share marketplace context."
        internal_guidance = "Align support scripts on retries, fare guidance, and wait-time expectations."
        if "rollback_request" in top_tags:
            external_guidance = "Acknowledge instability and communicate phased mitigation plan."
        if "fare" in top_tags or "price_sensitivity" in top_tags:
            internal_guidance = "Train support on fair-pricing explanations and rider alternatives."

    return {
        "agent": "Marketing/Comms Agent",
        "perception_summary": f"Top concern themes: {', '.join(top_tags[:4])}",
        "communication_plan": {
            "internal": internal_guidance,
            "external": external_guidance,
        },
    }
