from typing import Dict


def run_data_analyst_agent(metric_summary: Dict[str, float], feedback_summary: Dict[str, object]) -> Dict[str, object]:
    findings = []

    if metric_summary["cancellation_dropoff_rate_pct"] > 30.0:
        findings.append("Drop-off is high after users see repeated rejection counts.")

    if metric_summary["delta_support_tickets"] > 60:
        findings.append("Support tickets have increased sharply around the rejection-visibility flow.")

    if metric_summary["retry_rate_pct"] > 46.0 and metric_summary["cancellation_dropoff_rate_pct"] > 28.0:
        findings.append("Users are retrying multiple times, which likely reflects irritation instead of healthy engagement.")

    if metric_summary["time_to_ride_confirmation_sec"] > 150 and metric_summary["rejections_per_successful_ride"] > 4.0:
        findings.append("Long confirmation time appears linked to repeated driver rejections, increasing booking stress.")

    if metric_summary["fare_increase_rate_pct"] > 30.0 and metric_summary["price_elasticity_of_conversion"] < 0.2:
        findings.append("Many riders are increasing fare but conversion gain is weak, suggesting wait-for-higher-payout behavior.")

    if feedback_summary.get("negative_ratio", 0.0) > 0.5:
        findings.append("Feedback indicates emotional stress and trust erosion after exposing rejection counts.")

    if metric_summary["delta_rejections_per_success"] > 0.4:
        findings.append("Rejections per successful ride are rising, showing higher marketplace friction for this feature cohort.")

    return {
        "agent": "Data Analyst Agent",
        "metric_snapshot": metric_summary,
        "findings": findings,
        "signal_strength": "high" if len(findings) >= 3 else "medium",
    }


def compute_evidence_signals(metric_summary: Dict[str, float], feedback_negative_ratio: float) -> Dict[str, bool]:
    return {
        "ride_confirmation_low": metric_summary["ride_confirmation_rate_pct"] < 72.0,
        "dropoff_high": metric_summary["cancellation_dropoff_rate_pct"] > 30.0,
        "driver_acceptance_low": metric_summary["driver_acceptance_rate_pct"] < 58.0,
        "support_spike": metric_summary["delta_support_tickets"] > 60,
        "friction_rising": metric_summary["delta_rejections_per_success"] > 0.4,
        "sentiment_negative": feedback_negative_ratio > 0.5,
    }
