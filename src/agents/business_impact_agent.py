from typing import Dict


def run_business_impact_agent(metric_summary: Dict[str, float]) -> Dict[str, object]:
    revenue_risk = "low"
    if metric_summary["ride_confirmation_rate_pct"] < 72.0 or metric_summary["churn_pct"] > 4.0:
        revenue_risk = "high"
    elif metric_summary["ride_confirmation_rate_pct"] < 76.0 or metric_summary["churn_pct"] > 3.2:
        revenue_risk = "medium"

    estimated_order_loss_pct = round(max(0.0, 82.0 - metric_summary["ride_confirmation_rate_pct"]), 2)
    estimated_support_load_increase = round(max(0.0, metric_summary["delta_support_tickets"]), 1)

    return {
        "agent": "Business Impact Agent",
        "revenue_risk": revenue_risk,
        "estimated_order_loss_pct": estimated_order_loss_pct,
        "estimated_support_load_increase": estimated_support_load_increase,
        "recommendation": "Prioritize payment reliability and protect high-value cohorts.",
    }
