from pathlib import Path
from typing import List, Dict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.orchestrator.coordinator import run_war_room

def _load_metrics(project_root: Path, scenario: str) -> pd.DataFrame:
    return pd.read_csv(project_root / "data" / scenario / "metrics_timeseries.csv")

def _agent_display_name(key: str) -> str:
    names = {
        "pm": "Product Manager Agent",
        "data": "Data Analyst Agent",
        "risk": "Risk/Critic Agent",
        "reliability": "Reliability Engineer Agent",
        "business": "Business Impact Agent",
        "comms": "Marketing/Comms Agent",
    }
    return names.get(key, key.upper())

def _agent_findings(result: Dict[str, object], key: str) -> List[str]:
    if key == "data":
        return list(result.get("rationale", {}).get("key_metric_drivers", []))
    if key == "pm":
        return list(result.get("rationale", {}).get("pm_perspective", []))
    if key == "risk":
        risks = result.get("risk_register", [])
        return [r.get("risk", "") for r in risks[:3]]
    if key == "reliability":
        rel = result.get("rationale", {}).get("reliability_perspective", {})
        rec = rel.get("recommendation")
        return [rec] if rec else []
    if key == "business":
        biz = result.get("rationale", {}).get("business_perspective", {})
        rec = biz.get("recommendation")
        return [rec] if rec else []
    if key == "comms":
        cp = result.get("communication_plan", {})
        return [cp.get("internal", ""), cp.get("external", "")]
    return []

def _load_all_metrics(project_root: Path) -> pd.DataFrame:
    dfs = []
    for s in ["baseline", "optimistic", "critical"]:
        try:
            df = _load_metrics(project_root, s)
            df['Scenario'] = s.capitalize()
            dfs.append(df)
        except Exception:
            pass
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

def _decision_reasoning_text(result: Dict[str, object], scenario: str) -> str:
    rationale = result.get("rationale", {})
    feedback_summary = rationale.get("feedback_summary", {})
    sent = feedback_summary.get("sentiment_counts", {})
    positive = int(sent.get("positive", 0))
    neutral = int(sent.get("neutral", 0))
    negative = int(sent.get("negative", 0))
    decision = str(result.get("decision", "Pause"))
    confidence = float(result.get("confidence_score", 0.0))
    key_drivers = rationale.get("key_metric_drivers", [])
    driver_text = key_drivers[0] if key_drivers else "Core launch metrics and feedback trends were reviewed."

    return (
        f"The final decision is made by the War Room Coordinator Agent after consolidating all agent outputs, "
        f"tool-based metric analysis, and sentiment evidence for the {scenario} scenario. "
        f"Some users are happy with rejection-count visibility because it shows the app is actively searching "
        f"(positive={positive}, neutral={neutral}), while others report friction and frustration (negative={negative}). "
        f"Considering both positives and negatives, the system concludes: {decision} (confidence {confidence:.2f}). "
        f"Primary reason: {driver_text}"
    )

def main() -> None:
    st.set_page_config(page_title="War Room Command Center", layout="wide")

    # ===== WAR ROOM UI =====
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800;900&display=swap');

    /* Streamlit structure overrides */
    [data-testid="stAppViewContainer"] { 
        background: #f8fafc;
        color: #0f172a; 
        font-family: 'Inter', sans-serif; 
    }
    
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    [data-testid="stHeader"] {
        background-color: transparent;
    }

    .war-title { 
        font-size: 2.8rem; 
        font-weight: 900; 
        background: linear-gradient(to right, #2563eb, #7c3aed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .war-sub { 
        color: #64748b; 
        font-size: 1.1rem;
        margin-bottom: 1.5rem; 
        font-weight: 300;
    }

    .decision-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease-in-out;
    }
    .decision-box:hover {
        transform: translateY(-2px);
    }
    .decision-box.proceed { border-top: 4px solid #10b981; }
    .decision-box.pause { border-top: 4px solid #f59e0b; }
    .decision-box.rollback { border-top: 4px solid #ef4444; }

    .decision-box h2 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: 1px;
    }

    .decision-box p {
        margin-top: 0.5rem;
        color: #64748b;
        font-size: 1rem;
    }

    .chat {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
    }
    .chat:hover {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-color: #cbd5e1;
    }

    .chat-header { 
        font-weight: 800; 
        font-size: 0.85rem;
        letter-spacing: 0.5px;
        color: #1e293b; 
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .chat-body { 
        color: #475569; 
        font-size: 0.95rem;
        line-height: 1.5;
        margin-bottom: 0.75rem;
    }

    .war-feed {
        background: #1e293b;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 16px;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        font-size: 0.85rem;
        color: #34d399;
        height: 220px;
        overflow-y: auto;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
    }
    .war-feed::-webkit-scrollbar {
        width: 8px;
    }
    .war-feed::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.1);
    }
    .war-feed::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.3);
        border-radius: 4px;
    }

    .chat ul {
        margin: 0;
        padding-left: 1.2rem;
        color: #334155;
        font-size: 0.9rem;
    }
    .chat li {
        margin-bottom: 0.3rem;
    }

    .confidence-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }
    .confidence-label {
        font-size: 0.82rem;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .confidence-value {
        font-size: 1.9rem;
        color: #0f172a;
        font-weight: 800;
        line-height: 1.1;
    }

    hr {
        border-color: #e2e8f0;
    }
    </style>
    """, unsafe_allow_html=True)

    # ===== HEADER =====
    st.markdown('<div class="war-title">WAR ROOM CENTER</div>', unsafe_allow_html=True)
    st.markdown('<div class="war-sub">Live multi-agent orchestration engine</div>', unsafe_allow_html=True)

    project_root = Path(__file__).resolve().parent

    # ===== SIDEBAR =====
    with st.sidebar:
        st.header("Controls")
        scenario = st.selectbox("Scenario", ["baseline", "optimistic", "critical"])
        run_clicked = st.button("🚀 Run War Room", use_container_width=True)

    metrics_df = _load_metrics(project_root, scenario)

    # ===== METRICS =====
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Reject/Success", f"{metrics_df['rejections_per_successful_ride'].iloc[-1]:.1f}")
    c2.metric("Retry Rate", f"{metrics_df['retry_rate_pct'].iloc[-1]:.1f}%")
    c3.metric("Price Elst", f"{metrics_df['price_elasticity_of_conversion'].iloc[-1]:.2f}")
    c4.metric("Churn", f"{metrics_df['churn_pct'].iloc[-1]:.1f}%")
    c5.metric("Drop-off", f"{metrics_df['cancellation_dropoff_rate_pct'].iloc[-1]:.1f}%")

    # ===== TREND VISUALIZATIONS =====
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("📊 Scenario Trajectories")
    all_df = _load_all_metrics(project_root)
    if not all_df.empty:
        t1, t2, t3, t4, t5 = st.tabs(["Retry Rate", "Price Elasticity", "Reject/Success", "Churn", "Drop-Off"])
        color_map = {"Baseline": "#64748b", "Optimistic": "#10b981", "Critical": "#ef4444"}
        
        with t1:
            fig1 = px.line(all_df, x="date", y="retry_rate_pct", color="Scenario", color_discrete_map=color_map)
            fig1.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig1)
        with t2:
            fig2 = px.line(all_df, x="date", y="price_elasticity_of_conversion", color="Scenario", color_discrete_map=color_map)
            fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig2)
        with t3:
            fig3 = px.line(all_df, x="date", y="rejections_per_successful_ride", color="Scenario", color_discrete_map=color_map)
            fig3.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig3)
        with t4:
            fig4 = px.line(all_df, x="date", y="churn_pct", color="Scenario", color_discrete_map=color_map)
            fig4.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig4)
        with t5:
            fig5 = px.line(all_df, x="date", y="cancellation_dropoff_rate_pct", color="Scenario", color_discrete_map=color_map)
            fig5.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig5)

    st.markdown("<hr>", unsafe_allow_html=True)
    # ===== LIVE FEED =====
    st.subheader("⚡ Live War Feed")
    feed_box = st.empty()
    feed_lines = []

    def event_cb(msg: str):
        feed_lines.append(f"⚡ {msg}")
        feed_box.markdown(f'<div class="war-feed">{"<br>".join(feed_lines[-15:])}</div>', unsafe_allow_html=True)

    # ===== RUN =====
    if run_clicked:
        result = run_war_room(project_root, scenario, event_callback=event_cb)
        st.session_state["result"] = result

    result = st.session_state.get("result")

    if result:
        # ===== DECISION =====
        decision_val = result['decision'].upper()
        decision_class = "proceed" if "PROCEED" in decision_val else ("rollback" if "ROLL BACK" in decision_val else "pause")
        
        st.markdown(f"""
        <div class="decision-box {decision_class}">
            <h2>🛡️ {decision_val}</h2>
            <p>Confidence: <strong>{result['confidence_score']:.2f}</strong> &nbsp;|&nbsp; <em>Target: {scenario.title()}</em></p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== RATIONALE =====
        st.subheader("📌 Rationale: Key Drivers")
        rationale = result.get("rationale", {})
        key_drivers = rationale.get("key_metric_drivers", [])
        if key_drivers:
            for item in key_drivers:
                st.markdown(f"- {item}")
        else:
            st.info("No key drivers were generated.")

        st.markdown("#### Metric References")
        latest_metrics = metrics_df.iloc[-1]
        metric_refs = pd.DataFrame(
            [
                {"Metric": "Ride Confirmation Rate %", "Value": float(latest_metrics["ride_confirmation_rate_pct"])},
                {"Metric": "Cancellation Drop-off Rate %", "Value": float(latest_metrics["cancellation_dropoff_rate_pct"])},
                {"Metric": "Retry Rate %", "Value": float(latest_metrics["retry_rate_pct"])},
                {"Metric": "Time to Ride Confirmation (sec)", "Value": float(latest_metrics["time_to_ride_confirmation_sec"])},
                {"Metric": "Driver Acceptance Rate %", "Value": float(latest_metrics["driver_acceptance_rate_pct"])},
                {"Metric": "Rejections per Successful Ride", "Value": float(latest_metrics["rejections_per_successful_ride"])},
                {"Metric": "Support Tickets", "Value": float(latest_metrics["support_tickets"])},
                {"Metric": "Churn %", "Value": float(latest_metrics["churn_pct"])},
            ]
        )
        st.dataframe(metric_refs, use_container_width=True, hide_index=True)

        st.markdown("#### Feedback Summary")
        feedback_summary = rationale.get("feedback_summary", {})
        sentiment_counts = feedback_summary.get("sentiment_counts", {})
        fb1, fb2, fb3 = st.columns(3)
        fb1.metric("Positive", sentiment_counts.get("positive", 0))
        fb2.metric("Neutral", sentiment_counts.get("neutral", 0))
        fb3.metric("Negative", sentiment_counts.get("negative", 0))
        st.markdown(f"**Negative Ratio:** {feedback_summary.get('negative_ratio', 0.0):.3f}")
        top_tags = feedback_summary.get("top_issue_tags", [])
        if top_tags:
            st.markdown(f"**Top Issues:** {', '.join(top_tags)}")

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== RISK REGISTER =====
        st.subheader("⚠️ Risk Register")
        risk_register = result.get("risk_register", [])
        if risk_register:
            st.dataframe(pd.DataFrame(risk_register), use_container_width=True, hide_index=True)
        else:
            st.info("No risks were generated.")

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== AGENTS =====
        st.subheader("🧠 Agent Intelligence")

        votes = result.get("agent_decisions", {})
        summaries = result.get("agent_summaries", {})

        agent_order = ["pm", "data", "risk", "reliability", "business", "comms"]

        for agent in agent_order:
            vote = votes.get(agent, "Pause")
            summary = summaries.get(agent, "")

            color = {
                "Proceed": "#22c55e",
                "Pause": "#eab308",
                "Roll Back": "#ef4444"
            }.get(vote, "#3b82f6")

            findings = _agent_findings(result, agent)
            bullets = "".join([f"<li>{f}</li>" for f in findings[:3]])

            st.markdown(f"""
            <div class="chat" style="border-left: 5px solid {color}">
                <div class="chat-header">
                    <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{color};"></span>
                    {_agent_display_name(agent)} &mdash; {vote.upper()}
                </div>
                <div class="chat-body">{summary}</div>
                <ul>{bullets}</ul>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== ACTION PLAN =====
        st.subheader("⚡ Action Plan")
        st.dataframe(pd.DataFrame(result["action_plan_24_48h"]), use_container_width=True, hide_index=True)

        # ===== COMMUNICATION =====
        st.subheader("📢 Communication")
        comm_plan = result.get("communication_plan", {})
        if isinstance(comm_plan, dict):
            st.markdown(f"**Internal:** {comm_plan.get('internal', 'None')}")
            st.markdown(f"**External:** {comm_plan.get('external', 'None')}")
        else:
            st.write(comm_plan)

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== TOOLS USED =====
        st.subheader("🧰 Tools Used by Agents")
        st.markdown(
            "- **Metric aggregation + trend comparison:** computes latest KPI values and short-window trend deltas to detect "
            "improvement or deterioration before agent reasoning starts."
        )
        st.markdown(
            "- **Sentiment summary:** analyzes user feedback to produce sentiment counts, top recurring issue themes, "
            "and negative ratio so agents can weigh user impact."
        )
        st.markdown(
            "- **How they are used in flow:** the coordinator first builds a shared evidence snapshot from metrics and feedback; "
            "then each agent evaluates that same snapshot from its function, and the coordinator synthesizes the final decision."
        )

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== FINAL DECISION AUTHORITY =====
        st.subheader("🏛️ Final Decision Authority")
        st.info(
            "Final decision owner: **War Room Coordinator Agent**. "
            "Individual agents provide recommendations, but the coordinator applies final guardrails and confidence scoring."
        )
        st.write(_decision_reasoning_text(result, scenario))

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== CONFIDENCE =====
        st.subheader("🎯 Confidence")
        breakdown = result.get("confidence_breakdown", {})
        components = breakdown.get("components", {})
        confidence_cols = st.columns(4)
        score = float(result.get("confidence_score", 0.0))
        confidence_cols[0].markdown(
            f"""
            <div class="confidence-card">
                <div class="confidence-label">Confidence Score</div>
                <div class="confidence-value">{score:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if components:
            cc1, cc2, cc3 = confidence_cols[1], confidence_cols[2], confidence_cols[3]
            cc1.markdown(
                f"""
                <div class="confidence-card">
                    <div class="confidence-label">Evidence Quality</div>
                    <div class="confidence-value">{components.get('evidence_quality', 0.0):.3f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            cc2.markdown(
                f"""
                <div class="confidence-card">
                    <div class="confidence-label">Agent Agreement</div>
                    <div class="confidence-value">{components.get('agent_agreement', 0.0):.3f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            cc3.markdown(
                f"""
                <div class="confidence-card">
                    <div class="confidence-label">Data Completeness</div>
                    <div class="confidence-value">{components.get('data_completeness', 0.0):.3f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            severity_signal = components.get("severity_signal")
            if severity_signal is not None:
                st.caption(f"Severity Signal: {float(severity_signal):.3f}")
            st.caption(
                "Confidence is lower when agent recommendations diverge. "
                "For baseline, the strongest penalty is cross-agent disagreement."
            )

        st.markdown("#### What Would Increase Confidence")
        for item in result.get("what_would_increase_confidence", []):
            st.markdown(f"- {item}")

if __name__ == "__main__":
    main()
