from typing import Any, Dict


def build_final_output(
    decision: str,
    rationale: Dict[str, Any],
    risk_register: Any,
    action_plan: Any,
    communication_plan: Dict[str, str],
    confidence_score: float,
    confidence_increase_factors: Any,
) -> Dict[str, Any]:
    return {
        "decision": decision,
        "rationale": rationale,
        "risk_register": risk_register,
        "action_plan_24_48h": action_plan,
        "communication_plan": communication_plan,
        "confidence_score": confidence_score,
        "what_would_increase_confidence": confidence_increase_factors,
    }
