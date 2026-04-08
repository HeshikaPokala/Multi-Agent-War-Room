from pathlib import Path
from typing import List, Dict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.orchestrator.coordinator import run_war_room

def _load_metrics(project_root: Path, scenario: str) -> pd.DataFrame:
    return pd.read_csv(project_root / "data" / scenario / "metrics_timeseries.csv")

def _decision_badge(vote: str) -> str:
    if vote == "Proceed":
        return "tag-proceed"
    if vote == "Roll Back":
        return "tag-rollback"
    return "tag-pause"

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
                    {agent.upper()} AGENT &mdash; {vote.upper()}
                </div>
                <div class="chat-body">{summary}</div>
                <ul>{bullets}</ul>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        # ===== ACTION PLAN =====
        st.subheader("⚡ Action Plan")
        st.dataframe(pd.DataFrame(result["action_plan_24_48h"]))

        # ===== COMMUNICATION =====
        st.subheader("📢 Communication")
        comm_plan = result.get("communication_plan", {})
        if isinstance(comm_plan, dict):
            st.markdown(f"**Internal:** {comm_plan.get('internal', 'None')}")
            st.markdown(f"**External:** {comm_plan.get('external', 'None')}")
        else:
            st.write(comm_plan)

        # ===== DEBUG =====
        if st.button("Show Raw Output"):
            st.json(result)

if __name__ == "__main__":
    main()
