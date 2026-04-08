import csv
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Dict, List


@lru_cache(maxsize=16)
def load_metrics(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def trend_delta(rows: List[Dict[str, str]], metric_key: str, window: int = 3) -> float:
    if len(rows) < window * 2:
        return 0.0
    first = [float(r[metric_key]) for r in rows[:window]]
    last = [float(r[metric_key]) for r in rows[-window:]]
    return round(mean(last) - mean(first), 4)


def summarize_metrics(rows: List[Dict[str, str]]) -> Dict[str, float]:
    latest = rows[-1]
    keys = [
        "ride_confirmation_rate_pct",
        "cancellation_dropoff_rate_pct",
        "retry_rate_pct",
        "time_to_ride_confirmation_sec",
        "fare_increase_rate_pct",
        "price_elasticity_of_conversion",
        "driver_acceptance_rate_pct",
        "rejections_per_successful_ride",
        "support_tickets",
        "churn_pct",
    ]
    summary = {k: float(latest[k]) for k in keys}
    summary["delta_ride_confirmation_rate"] = trend_delta(rows, "ride_confirmation_rate_pct")
    summary["delta_cancellation_dropoff"] = trend_delta(rows, "cancellation_dropoff_rate_pct")
    summary["delta_retry_rate"] = trend_delta(rows, "retry_rate_pct")
    summary["delta_time_to_confirmation_sec"] = trend_delta(rows, "time_to_ride_confirmation_sec")
    summary["delta_driver_acceptance_rate"] = trend_delta(rows, "driver_acceptance_rate_pct")
    summary["delta_rejections_per_success"] = trend_delta(rows, "rejections_per_successful_ride")
    summary["delta_support_tickets"] = trend_delta(rows, "support_tickets")
    summary["delta_churn"] = trend_delta(rows, "churn_pct")
    return summary
