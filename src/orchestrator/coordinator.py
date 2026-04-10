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

# Per-scenario LLM task wording so optimistic runs do not inherit "stress-first" prompts.
_AGENT_TASKS: Dict[str, Dict[str, str]] = {
    "baseline": {
        "PM Agent": "Assess whether this feature should proceed, pause, or roll back from product-impact perspective.",
        "Data Analyst Agent": "Analyze feature-level metric and sentiment patterns, focusing on rider stress, retries, drop-off, and supply friction.",
        "Marketing/Comms Agent": "Create internal and external communication guidance specific to this feature rollout impact.",
        "Risk/Critic Agent": "Challenge assumptions and produce top risks plus mitigations for this feature rollout.",
        "Reliability Engineer Agent": "Assess operational reliability impact (confirmation time, friction, repeated rejections) and suggest immediate safeguards.",
        "Business Impact Agent": "Estimate business impact on conversion, churn, and support burden for this feature.",
    },
    "optimistic": {
        "PM Agent": "Assess go/no-go from a product perspective for a rollout that is meeting targets: emphasize validation, retention, transparency value, and where metrics show the feature is helping rather than hurting.",
        "Data Analyst Agent": "Analyze metrics and sentiment for a healthy rollout: highlight improving confirmation, acceptance, rejection trends, and contained drop-off. Explain high retry_rate only in context of stable or improving abandonment metrics.",
        "Marketing/Comms Agent": "Create confident, transparent internal and external messaging for a launch that is performing well; celebrate clarity for riders without dismissing routine monitoring.",
        "Risk/Critic Agent": "Identify only material residual risks; if metrics are strong, state that explicitly and keep mitigations light (routine monitoring, not alarmist).",
        "Reliability Engineer Agent": "Assess reliability: if confirmation time and rejection loops are within guardrails, say so clearly and reserve safeguards for edge cases.",
        "Business Impact Agent": "Estimate business impact when conversion and churn look favorable: stress stability, manageable support, and upside from transparency.",
    },
    "critical": {
        "PM Agent": "Assess go/no-go under degraded signals: prioritize churn, negative sentiment, and whether transparency is doing more harm than good.",
        "Data Analyst Agent": "Analyze stress signals: retries, drop-off, supply friction, and sentiment erosion; tie findings to metric movements.",
        "Marketing/Comms Agent": "Create communication guidance under strain: acknowledge friction, set expectations, and explain mitigations.",
        "Risk/Critic Agent": "Challenge assumptions aggressively; surface top risks, severities, and concrete mitigations.",
        "Reliability Engineer Agent": "Assess operational reliability under load: confirmation delays, rejection loops, and incident-style safeguards.",
        "Business Impact Agent": "Estimate business exposure: conversion loss, churn risk, and support burden from the current trajectory.",
    },
}


def _agent_task(scenario: str, role: str) -> str:
    pack = _AGENT_TASKS.get(scenario) or _AGENT_TASKS["baseline"]
    return pack.get(role) or _AGENT_TASKS["baseline"][role]


def _is_severe_failure(metric_summary: Dict[str, float]) -> bool:
    return (
        metric_summary["ride_confirmation_rate_pct"] < 68.0
        or metric_summary["cancellation_dropoff_rate_pct"] > 34.0
        or metric_summary["driver_acceptance_rate_pct"] < 52.0
        or metric_summary["churn_pct"] > 4.5
        or metric_summary["time_to_ride_confirmation_sec"] > 160.0
        or metric_summary["rejections_per_successful_ride"] > 4.2
    )


def _decide(metric_summary: Dict[str, float]) -> str:
    if _is_severe_failure(metric_summary):
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
        if metric_summary["churn_pct"] > 4.8 or feedback_summary["negative_ratio"] > 0.72:
            return "Roll Back"
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
        if feedback_summary["negative_ratio"] > 0.7:
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
        if metric_summary["ride_confirmation_rate_pct"] < 66.0 or metric_summary["churn_pct"] > 4.8:
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

    severity_signal = _clamp(
        max(
            (68.0 - metric_summary["ride_confirmation_rate_pct"]) / 12.0,
            (metric_summary["cancellation_dropoff_rate_pct"] - 34.0) / 20.0,
            (160.0 - metric_summary["time_to_ride_confirmation_sec"]) / 160.0 * -1.0,
            (metric_summary["rejections_per_successful_ride"] - 4.2) / 4.0,
            (metric_summary["churn_pct"] - 4.5) / 3.0,
            0.0,
        )
    )

    score = 0.10 + 0.50 * evidence_quality + 0.25 * agreement_score + 0.15 * data_completeness + 0.10 * severity_signal
    score = round(_clamp(score, 0.45, 0.95), 2)

    return {
        "score": score,
        "components": {
            "evidence_quality": round(evidence_quality, 3),
            "agent_agreement": round(agreement_score, 3),
            "data_completeness": round(data_completeness, 3),
            "severity_signal": round(severity_signal, 3),
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
    # Always anchor the final lean in deterministic metric evidence.
    normalized["decision_lean"] = _agent_vote_from_metrics(metric_summary, feedback_summary, role_key)
    return normalized


def _normalize_risk_register(
    candidate_risks: Any,
    metric_summary: Dict[str, float],
    feedback_summary: Dict[str, Any],
    scenario: str = "baseline",
) -> Any:
    generic_mitigations = {"investigate and mitigate", "monitor"}
    normalized = []
    if isinstance(candidate_risks, list):
        for item in candidate_risks:
            if not isinstance(item, dict):
                continue
            risk_text = str(item.get("risk", "")).strip().lstrip("* ").strip()
            severity = str(item.get("severity", "medium")).strip().lower()
            if severity not in {"low", "medium", "high"}:
                severity = "medium"
            mitigation = str(item.get("mitigation", "")).strip().lstrip("* ").strip()
            if not risk_text:
                continue
            if not mitigation or mitigation.lower() in generic_mitigations:
                if "rejection" in risk_text.lower():
                    mitigation = "Add rejection-sensitive dispatch fallback and alert when rejections per success exceeds 4.0."
                elif "drop" in risk_text.lower() or "abandon" in risk_text.lower():
                    mitigation = "Ship alternative UX copy and auto-trigger A/B rollback if drop-off remains above 30% for 6 hours."
                elif "sentiment" in risk_text.lower() or "support" in risk_text.lower():
                    mitigation = "Activate proactive comms and support macros with 2-hour sentiment tracking."
                else:
                    mitigation = "Define threshold-based owner actions and verify impact in 6-hour checkpoints."
            normalized.append({"risk": risk_text, "severity": severity, "mitigation": mitigation})

    if normalized:
        return normalized[:4]

    fallback = []
    if metric_summary["rejections_per_successful_ride"] > 4.0:
        fallback.append(
            {
                "risk": "Repeated rejection loops are increasing rider frustration and booking failure risk.",
                "severity": "high",
                "mitigation": "Enable stricter dispatch retries and alert marketplace ops when rejection ratio exceeds 4.0.",
            }
        )
    if metric_summary["cancellation_dropoff_rate_pct"] > 30.0:
        fallback.append(
            {
                "risk": "Elevated drop-off after rejection visibility can reduce conversion and trust.",
                "severity": "high",
                "mitigation": "Roll out alternative UX framing and auto-trigger rollback if drop-off stays above 30% for 6 hours.",
            }
        )
    if feedback_summary.get("negative_ratio", 0.0) > 0.5:
        fallback.append(
            {
                "risk": "Sustained negative feedback can increase support load and social escalation.",
                "severity": "medium",
                "mitigation": "Use targeted in-app communication and prioritize high-frequency complaint tags in support routing.",
            }
        )
    if not fallback:
        if scenario == "optimistic":
            fallback.append(
                {
                    "risk": "Residual risk is limited to normal marketplace variance; current trajectory supports continued rollout.",
                    "severity": "low",
                    "mitigation": "Keep six-hour metric reviews and align new experiments with existing guardrails.",
                }
            )
        else:
            fallback.append(
                {
                    "risk": "No immediate high-severity risks detected, but trend regression remains possible.",
                    "severity": "low",
                    "mitigation": "Maintain 6-hour metric checks and freeze new experiments until trend stability is confirmed.",
                }
            )
    return fallback


def _build_action_plan(decision: str) -> Any:
    if decision == "Roll Back":
        return [
            {"action": "Pause rollout and revert rejection-count UI for all unstable zones", "owner": "Engineering + Release Manager"},
            {"action": "Launch incident review with marketplace and product within 2 hours", "owner": "PM + Reliability"},
            {"action": "Deploy mitigation experiment for dispatch retry ordering", "owner": "Marketplace Ops + Data"},
            {"action": "Re-evaluate go/no-go after 24-hour stabilized metrics window", "owner": "War Room Coordinator"},
        ]
    if decision == "Pause":
        return [
            {"action": "Hold rollout expansion and keep current cohort size fixed", "owner": "Release Manager"},
            {"action": "Tune rider UX copy around rejection count context", "owner": "Product + Design"},
            {"action": "Optimize dispatch and driver ping sequencing", "owner": "Engineering + Marketplace Ops"},
            {"action": "Run 6-hour metric checkpoint review with rollback trigger criteria", "owner": "Data Analyst"},
        ]
    return [
        {"action": "Continue phased rollout with zone-level guardrails", "owner": "PM + Release Manager"},
        {"action": "Monitor confirmation, drop-off, and rejection metrics every 6 hours", "owner": "Data Analyst"},
        {"action": "Keep support macros ready for emerging complaint clusters", "owner": "Support Operations"},
        {"action": "Publish weekly post-launch performance update", "owner": "Marketing/Comms"},
    ]


def _build_communication_plan(
    decision: str, feedback_summary: Dict[str, Any], metric_summary: Dict[str, float]
) -> Dict[str, str]:
    negative_ratio = feedback_summary.get("negative_ratio", 0.0)
    if decision == "Roll Back":
        return {
            "internal": "Communicate immediate rollback, incident owners, and 6-hour checkpoint cadence across product, support, and ops.",
            "external": "Acknowledge temporary rollback of rejection-count visibility, explain reliability-first intent, and share near-term fix timeline.",
        }
    if decision == "Pause":
        return {
            "internal": "Share pause decision with guardrail thresholds and owner-level actions for UX, dispatch, and support handling.",
            "external": (
                "Communicate that rejection-count visibility remains limited while we improve ride confirmation quality and reduce booking friction."
            ),
        }
    if negative_ratio > 0.35 or metric_summary["rejections_per_successful_ride"] > 3.0:
        return {
            "internal": "Proceed carefully with targeted monitoring and rapid-response messaging templates for support.",
            "external": "Announce phased rollout with transparent quality monitoring and quick follow-up improvements.",
        }
    return {
        "internal": "Proceed with confidence; maintain standard monitoring and weekly status updates.",
        "external": "Announce wider rollout of rejection-count transparency as a rider trust and decision-aid improvement.",
    }


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
        task=_agent_task(scenario, "PM Agent"),
        context=shared_ctx,
        fallback_fn=lambda: run_pm_agent(metric_summary, feedback_summary, scenario),
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
        task=_agent_task(scenario, "Data Analyst Agent"),
        context=shared_ctx,
        fallback_fn=lambda: run_data_analyst_agent(metric_summary, feedback_summary, scenario),
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
        task=_agent_task(scenario, "Marketing/Comms Agent"),
        context=shared_ctx,
        fallback_fn=lambda: run_marketing_comms_agent(feedback_summary, scenario),
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
        task=_agent_task(scenario, "Risk/Critic Agent"),
        context=shared_ctx,
        fallback_fn=lambda: run_risk_critic_agent(metric_summary, feedback_summary, scenario),
        logger=logger,
        event_callback=event_callback,
    )
    risk_view = _normalize_agent_output("risk", risk_view, metric_summary, feedback_summary)
    risk_view["risk_register"] = _normalize_risk_register(
        risk_view.get("risk_register"), metric_summary, feedback_summary, scenario
    )
    logger.log("Risk/Critic Agent", "Completed risk challenge and mitigations")
    _emit(event_callback, "Risk/Critic Agent completed challenge phase")
    reliability_view = _run_agent_smart(
        role="Reliability Engineer Agent",
        task=_agent_task(scenario, "Reliability Engineer Agent"),
        context=shared_ctx,
        fallback_fn=lambda: run_reliability_engineer_agent(metric_summary, scenario),
        logger=logger,
        event_callback=event_callback,
    )
    reliability_view = _normalize_agent_output("reliability", reliability_view, metric_summary, feedback_summary)
    logger.log("Reliability Engineer Agent", "Assessed incident severity and guardrails")
    _emit(event_callback, "Reliability Engineer Agent completed reliability assessment")
    business_view = _run_agent_smart(
        role="Business Impact Agent",
        task=_agent_task(scenario, "Business Impact Agent"),
        context=shared_ctx,
        fallback_fn=lambda: run_business_impact_agent(metric_summary, scenario),
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

    action_plan = _build_action_plan(decision)
    communication_plan = _build_communication_plan(decision, feedback_summary, metric_summary)

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
        communication_plan=communication_plan,
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
