from typing import Dict


def run_pm_agent(
    metric_summary: Dict[str, float], feedback_summary: Dict[str, object], scenario: str = "baseline"
) -> Dict[str, object]:
    rationale = []
    neg = float(feedback_summary.get("negative_ratio", 0.0))

    if scenario == "optimistic":
        rationale.append(
            "Rejection-count transparency is pairing with strong funnel metrics; riders get clarity without a spike in abandonment."
        )
        rationale.append(
            f"Ride confirmation at {metric_summary['ride_confirmation_rate_pct']:.1f}% and churn at {metric_summary['churn_pct']:.1f}% support a confident proceed with routine monitoring."
        )
        if metric_summary["cancellation_dropoff_rate_pct"] <= 28:
            rationale.append("Drop-off stays within guardrails even while rejection activity is visible.")
        if neg < 0.35:
            rationale.append("Qualitative feedback skews toward trust and transparency themes.")
        view = "supportive"
    else:
        if metric_summary["ride_confirmation_rate_pct"] >= 76:
            rationale.append("Ride confirmation remains healthy after exposing rejection counts.")
        else:
            rationale.append("Ride confirmation is below target and needs intervention.")

        if metric_summary["cancellation_dropoff_rate_pct"] > 28:
            rationale.append("Drop-off is elevated, suggesting user frustration after seeing rejections.")

        if metric_summary["churn_pct"] > 4.0:
            rationale.append("Churn is elevated and may indicate user dissatisfaction.")

        if neg > 0.5:
            rationale.append("User sentiment trend is net negative in the launch window.")
        view = "cautious"

    return {
        "agent": "PM Agent",
        "go_no_go_view": view,
        "success_criteria_check": {
            "ride_confirmation_target_met": metric_summary["ride_confirmation_rate_pct"] >= 76,
            "dropoff_within_guardrail": metric_summary["cancellation_dropoff_rate_pct"] <= 28,
            "churn_within_guardrail": metric_summary["churn_pct"] <= 4.0,
        },
        "rationale_points": rationale,
    }
