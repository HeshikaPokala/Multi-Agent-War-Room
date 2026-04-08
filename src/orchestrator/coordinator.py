from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.agents.business_impact_agent import run_business_impact_agent
from src.agents.data_analyst_agent import run_data_analyst_agent
from src.agents.marketing_comms_agent import run_marketing_comms_agent
from src.agents.pm_agent import run_pm_agent
from src.agents.reliability_engineer_agent import run_reliability_engineer_agent
from src.agents.risk_critic_agent import run_risk_critic_agent
from src.llm.agent_brain import run_llm_agent
from src.llm.client import LLMUnavailableError
from src.schemas.final_output_schema import build_final_output
from src.tools.feedback_tools import load_feedback, summarize_sentiment
from src.tools.metrics_tools import load_metrics, summarize_metrics
from src.utils.io_helpers import ensure_dir, write_json, write_yaml
from src.utils.logger import TraceLogger


def _decide(metric_summary: Dict[str, float]) -> str:
    if (
        metric_summary["ride_confirmation_rate_pct"] < 68.0
        or metric_summary["cancellation_dropoff_rate_pct"] > 34.0
        or metric_summary["driver_acceptance_rate_pct"] < 52.0
        or metric_summary["churn_pct"] > 4.5
    ):
        return "Roll Back"
    if (
        metric_summary["ride_confirmation_rate_pct"] < 74.0
        or metric_summary["cancellation_dropoff_rate_pct"] > 28.0
        or metric_summary["time_to_ride_confirmation_sec"] > 145.0
        or metric_summary["rejections_per_successful_ride"] > 3.5
        or metric_summary["churn_pct"] > 3.6
    ):
        return "Pause"
    return "Proceed"


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(value, maximum))


def _agent_vote_from_metrics(metric_summary: Dict[str, float], feedback_summary: Dict[str, Any], agent_name: str) -> str:
    if agent_name == "pm":
        if metric_summary["churn_pct"] > 4.0 or feedback_summary["negative_ratio"] > 0.55:
            return "Pause"
        return "Proceed"
    if agent_name == "data":
        if metric_summary["ride_confirmation_rate_pct"] < 68.0 or metric_summary["driver_acceptance_rate_pct"] < 52.0:
            return "Roll Back"
        if metric_summary["ride_confirmation_rate_pct"] < 74.0 or metric_summary["cancellation_dropoff_rate_pct"] > 28.0:
            return "Pause"
        return "Proceed"
    if agent_name == "comms":
        if feedback_summary["negative_ratio"] > 0.7:
            return "Roll Back"
        if feedback_summary["negative_ratio"] > 0.5:
            return "Pause"
        return "Proceed"
    if agent_name == "risk":
        high_risk = 0
        if metric_summary["rejections_per_successful_ride"] > 3.8:
            high_risk += 1
        if metric_summary["cancellation_dropoff_rate_pct"] > 30.0:
            high_risk += 1
        if high_risk >= 2:
            return "Roll Back"
        if high_risk == 1:
            return "Pause"
        return "Proceed"
    if agent_name == "reliability":
        if metric_summary["time_to_ride_confirmation_sec"] > 165 or metric_summary["rejections_per_successful_ride"] > 4.1:
            return "Roll Back"
        if metric_summary["time_to_ride_confirmation_sec"] > 145 or metric_summary["rejections_per_successful_ride"] > 3.5:
            return "Pause"
        return "Proceed"
    if agent_name == "business":
        if metric_summary["ride_confirmation_rate_pct"] < 68.0:
            return "Roll Back"
        if metric_summary["ride_confirmation_rate_pct"] < 74.0 or metric_summary["churn_pct"] > 3.6:
            return "Pause"
        return "Proceed"
    return "Pause"


def _confidence(metric_summary: Dict[str, float], feedback_summary: Dict[str, Any], decision: str) -> Dict[str, Any]:
    # Confidence = certainty in decision from evidence quality, agreement, and data completeness.
    confirmation_strength = _clamp(abs(metric_summary["ride_confirmation_rate_pct"] - 74.0) / 10.0)
    dropoff_strength = _clamp(abs(metric_summary["cancellation_dropoff_rate_pct"] - 28.0) / 12.0)
    retry_strength = _clamp(abs(metric_summary["retry_rate_pct"] - 44.0) / 20.0)
    support_strength = _clamp(abs(metric_summary["delta_support_tickets"] - 60.0) / 180.0)
    friction_strength = _clamp(abs(metric_summary["rejections_per_successful_ride"] - 3.5) / 2.0)
    sentiment_strength = _clamp(abs(feedback_summary["negative_ratio"] - 0.5) / 0.5)

    evidence_quality = (
        0.24 * confirmation_strength
        + 0.22 * dropoff_strength
        + 0.16 * retry_strength
        + 0.16 * support_strength
        + 0.12 * friction_strength
        + 0.10 * sentiment_strength
    )

    votes = {
        "pm": _agent_vote_from_metrics(metric_summary, feedback_summary, "pm"),
        "data": _agent_vote_from_metrics(metric_summary, feedback_summary, "data"),
        "comms": _agent_vote_from_metrics(metric_summary, feedback_summary, "comms"),
        "risk": _agent_vote_from_metrics(metric_summary, feedback_summary, "risk"),
        "reliability": _agent_vote_from_metrics(metric_summary, feedback_summary, "reliability"),
        "business": _agent_vote_from_metrics(metric_summary, feedback_summary, "business"),
    }
    aligned_votes = sum(1 for v in votes.values() if v == decision)
    agreement_score = aligned_votes / max(len(votes), 1)

    metric_fields_total = 10
    metric_fields_present = sum(
        1
        for key in [
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
        if key in metric_summary
    )
    feedback_count = sum(feedback_summary.get("sentiment_counts", {}).values())
    feedback_completeness = _clamp(feedback_count / 30.0)
    data_completeness = _clamp(0.7 * (metric_fields_present / metric_fields_total) + 0.3 * feedback_completeness)

    score = 0.10 + 0.45 * evidence_quality + 0.30 * agreement_score + 0.15 * data_completeness
    score = round(_clamp(score, 0.45, 0.95), 2)

    return {
        "score": score,
        "components": {
            "evidence_quality": round(evidence_quality, 3),
            "agent_agreement": round(agreement_score, 3),
            "data_completeness": round(data_completeness, 3),
        },
        "evidence_strength_factors": {
            "confirmation": round(confirmation_strength, 3),
            "dropoff": round(dropoff_strength, 3),
            "retry": round(retry_strength, 3),
            "support": round(support_strength, 3),
            "friction": round(friction_strength, 3),
            "sentiment": round(sentiment_strength, 3),
        },
        "agent_votes": votes,
    }


def _emit(event_callback: Optional[Callable[[str], None]], message: str) -> None:
    if event_callback:
        event_callback(message)


def _run_agent_smart(
    role: str,
    task: str,
    context: Dict[str, Any],
    fallback_fn: Callable[[], Dict[str, Any]],
    logger: TraceLogger,
    event_callback: Optional[Callable[[str], None]],
) -> Dict[str, Any]:
    try:
        result = run_llm_agent(role=role, task=task, context=context)
        logger.log(role, "LLM reasoning used (Ollama)")
        _emit(event_callback, f"{role}: smart reasoning completed")
        return result
    except (LLMUnavailableError, ValueError, KeyError) as exc:
        logger.log(role, f"LLM unavailable, using fallback rules ({exc})")
        _emit(event_callback, f"{role}: fallback rules used")
        return fallback_fn()


def _normalize_agent_output(
    role_key: str,
    payload: Dict[str, Any],
    metric_summary: Dict[str, float],
    feedback_summary: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = dict(payload)
    if "agent" not in normalized:
        normalized["agent"] = role_key
    if "findings" not in normalized or not isinstance(normalized.get("findings"), list):
        normalized["findings"] = []
    if "recommendation" not in normalized:
        normalized["recommendation"] = "No recommendation provided."
    if "summary" not in normalized:
        normalized["summary"] = "No summary provided."
    if normalized.get("decision_lean") not in {"Proceed", "Pause", "Roll Back"}:
        lean = _agent_vote_from_metrics(metric_summary, feedback_summary, role_key)
        normalized["decision_lean"] = lean
    # Guardrail: if narrative is clearly negative but LLM says Proceed, enforce metric vote.
    text_blob = " ".join(
        [
            str(normalized.get("summary", "")),
            str(normalized.get("recommendation", "")),
            " ".join(str(x) for x in normalized.get("findings", [])),
            " ".join(str(x) for x in normalized.get("risk_flags", [])),
        ]
    ).lower()
    negative_markers = [
        "high drop-off",
        "frustration",
        "stress",
        "churn",
        "roll back",
        "critical",
        "rising rejections",
        "support spike",
        "trust erosion",
        "negatively impact",
    ]
    narrative_negative = any(marker in text_blob for marker in negative_markers)
    if normalized.get("decision_lean") == "Proceed" and narrative_negative:
        normalized["decision_lean"] = _agent_vote_from_metrics(metric_summary, feedback_summary, role_key)
    return normalized


def run_war_room(project_root: Path, scenario: str, event_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    data_dir = project_root / "data" / scenario
    output_dir = project_root / "outputs"
    trace_dir = project_root / "traces"
    ensure_dir(output_dir)
    ensure_dir(trace_dir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = trace_dir / f"trace_{scenario}_{ts}.log"
    logger = TraceLogger(trace_path)
    logger.log("Coordinator", f"Run started for scenario={scenario}")
    _emit(event_callback, f"Run started for scenario: {scenario}")

    metric_rows = load_metrics(data_dir / "metrics_timeseries.csv")
    feedback_path = data_dir / "user_feedback.csv"
    if not feedback_path.exists():
        feedback_path = project_root / "data" / "baseline" / "user_feedback.csv"
    feedback_rows = load_feedback(feedback_path)
    metric_summary = summarize_metrics(metric_rows)
    feedback_summary = summarize_sentiment(feedback_rows)
    logger.log("Tool:metrics", "Loaded and summarized metrics data")
    logger.log("Tool:feedback", "Loaded and summarized feedback data")
    logger.log("Tool:feedback", f"Feedback source: {feedback_path}")
    _emit(event_callback, "Tools completed: metrics summary + feedback sentiment")

    shared_ctx = {
        "scenario": scenario,
        "metric_summary": metric_summary,
        "feedback_summary": feedback_summary,
    }

    pm_view = _run_agent_smart(
        role="PM Agent",
        task="Assess whether this feature should proceed, pause, or roll back from product-impact perspective.",
        context=shared_ctx,
        fallback_fn=lambda: run_pm_agent(metric_summary, feedback_summary),
        logger=logger,
        event_callback=event_callback,
    )
    pm_view = _normalize_agent_output("pm", pm_view, metric_summary, feedback_summary)
    if "rationale_points" not in pm_view:
        pm_view["rationale_points"] = pm_view.get("findings", [])
    logger.log("PM Agent", "Completed go/no-go framing")
    _emit(event_callback, "PM Agent completed framing")
    data_view = _run_agent_smart(
        role="Data Analyst Agent",
        task="Analyze feature-level metric and sentiment patterns, focusing on rider stress, retries, drop-off, and supply friction.",
        context=shared_ctx,
        fallback_fn=lambda: run_data_analyst_agent(metric_summary, feedback_summary),
        logger=logger,
        event_callback=event_callback,
    )
    data_view = _normalize_agent_output("data", data_view, metric_summary, feedback_summary)
    if "metric_snapshot" not in data_view:
        data_view["metric_snapshot"] = metric_summary
    if "findings" not in data_view:
        data_view["findings"] = []
    logger.log("Data Analyst Agent", "Completed metric trend and threshold checks")
    _emit(event_callback, "Data Analyst Agent completed analysis")
    comms_view = _run_agent_smart(
        role="Marketing/Comms Agent",
        task="Create internal and external communication guidance specific to this feature rollout impact.",
        context=shared_ctx,
        fallback_fn=lambda: run_marketing_comms_agent(feedback_summary),
        logger=logger,
        event_callback=event_callback,
    )
    comms_view = _normalize_agent_output("comms", comms_view, metric_summary, feedback_summary)
    if "communication_plan" not in comms_view:
        comms_view["communication_plan"] = {
            "internal": comms_view.get("recommendation", "Align support and product messaging."),
            "external": comms_view.get("summary", "Provide transparent user communication."),
        }
    logger.log("Marketing/Comms Agent", "Completed communication guidance")
    _emit(event_callback, "Marketing/Comms Agent completed messaging plan")
    risk_view = _run_agent_smart(
        role="Risk/Critic Agent",
        task="Challenge assumptions and produce top risks plus mitigations for this feature rollout.",
        context=shared_ctx,
        fallback_fn=lambda: run_risk_critic_agent(metric_summary, feedback_summary),
        logger=logger,
        event_callback=event_callback,
    )
    risk_view = _normalize_agent_output("risk", risk_view, metric_summary, feedback_summary)
    if "risk_register" not in risk_view:
        risk_view["risk_register"] = [
            {"risk": r, "severity": "medium", "mitigation": "Investigate and mitigate"} for r in risk_view.get("risk_flags", [])
        ]
    logger.log("Risk/Critic Agent", "Completed risk challenge and mitigations")
    _emit(event_callback, "Risk/Critic Agent completed challenge phase")
    reliability_view = _run_agent_smart(
        role="Reliability Engineer Agent",
        task="Assess operational reliability impact (confirmation time, friction, repeated rejections) and suggest immediate safeguards.",
        context=shared_ctx,
        fallback_fn=lambda: run_reliability_engineer_agent(metric_summary),
        logger=logger,
        event_callback=event_callback,
    )
    reliability_view = _normalize_agent_output("reliability", reliability_view, metric_summary, feedback_summary)
    logger.log("Reliability Engineer Agent", "Assessed incident severity and guardrails")
    _emit(event_callback, "Reliability Engineer Agent completed reliability assessment")
    business_view = _run_agent_smart(
        role="Business Impact Agent",
        task="Estimate business impact on conversion, churn, and support burden for this feature.",
        context=shared_ctx,
        fallback_fn=lambda: run_business_impact_agent(metric_summary),
        logger=logger,
        event_callback=event_callback,
    )
    business_view = _normalize_agent_output("business", business_view, metric_summary, feedback_summary)
    logger.log("Business Impact Agent", "Estimated business exposure and support impact")
    _emit(event_callback, "Business Impact Agent completed impact assessment")

    decision = _decide(metric_summary)
    confidence_info = _confidence(metric_summary, feedback_summary, decision)
    confidence = confidence_info["score"]
    logger.log("Coordinator", f"Decision computed: {decision} (confidence={confidence})")
    _emit(event_callback, f"Coordinator decision: {decision} (confidence={confidence})")

    action_plan = [
        {"action": "Tune rider UX copy around rejection count context", "owner": "Product + Design"},
        {"action": "Optimize dispatch and driver ping sequencing", "owner": "Engineering + Marketplace Ops"},
        {"action": "Roll out contextual fare guidance only in high-friction zones", "owner": "Growth + Pricing"},
        {"action": "Run 6-hour metric checkpoint review", "owner": "Data Analyst"},
    ]

    final_output = build_final_output(
        decision=decision,
        rationale={
            "key_metric_drivers": data_view["findings"],
            "feedback_summary": feedback_summary,
            "pm_perspective": pm_view["rationale_points"],
            "reliability_perspective": reliability_view,
            "business_perspective": business_view,
        },
        risk_register=risk_view["risk_register"],
        action_plan=action_plan,
        communication_plan=comms_view["communication_plan"],
        confidence_score=confidence,
        confidence_increase_factors=[
            "Zone-level analysis of rejection count impact on rider behavior",
            "Segmented elasticity analysis by trip distance/time band",
            "Post-intervention 24h confirmation and drop-off trend stability",
        ],
    )
    final_output["agent_decisions"] = {
        "pm": pm_view.get("decision_lean"),
        "data": data_view.get("decision_lean"),
        "comms": comms_view.get("decision_lean"),
        "risk": risk_view.get("decision_lean"),
        "reliability": reliability_view.get("decision_lean"),
        "business": business_view.get("decision_lean"),
    }
    final_output["agent_summaries"] = {
        "pm": pm_view.get("summary"),
        "data": data_view.get("summary"),
        "comms": comms_view.get("summary"),
        "risk": risk_view.get("summary"),
        "reliability": reliability_view.get("summary"),
        "business": business_view.get("summary"),
    }
    final_output["confidence_breakdown"] = confidence_info

    json_path = output_dir / f"final_decision_{scenario}.json"
    yaml_path = output_dir / f"final_decision_{scenario}.yaml"
    write_json(json_path, final_output)
    write_yaml(yaml_path, final_output)
    logger.log("Coordinator", f"Outputs written: {json_path.name}, {yaml_path.name}")
    _emit(event_callback, "Outputs generated in JSON and YAML")

    final_output["_meta"] = {
        "json_path": str(json_path),
        "yaml_path": str(yaml_path),
        "trace_path": str(trace_path),
        "scenario": scenario,
    }
    return final_output
