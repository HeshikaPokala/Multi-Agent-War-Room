from typing import Dict


def run_pm_agent(metric_summary: Dict[str, float], feedback_summary: Dict[str, object]) -> Dict[str, object]:
    rationale = []
    if metric_summary["ride_confirmation_rate_pct"] >= 76:
        rationale.append("Ride confirmation remains healthy after exposing rejection counts.")
    else:
        rationale.append("Ride confirmation is below target and needs intervention.")

    if metric_summary["cancellation_dropoff_rate_pct"] > 28:
        rationale.append("Drop-off is elevated, suggesting user frustration after seeing rejections.")

    if metric_summary["churn_pct"] > 4.0:
        rationale.append("Churn is elevated and may indicate user dissatisfaction.")

    if feedback_summary["negative_ratio"] > 0.5:
        rationale.append("User sentiment trend is net negative in the launch window.")

    return {
        "agent": "PM Agent",
        "go_no_go_view": "cautious",
        "success_criteria_check": {
            "ride_confirmation_target_met": metric_summary["ride_confirmation_rate_pct"] >= 76,
            "dropoff_within_guardrail": metric_summary["cancellation_dropoff_rate_pct"] <= 28,
            "churn_within_guardrail": metric_summary["churn_pct"] <= 4.0,
        },
        "rationale_points": rationale,
    }
