# Multi-agent launch war room

- Python pipeline: load mock launch CSVs, run six specialist agents in order, emit one structured go/no-go (Proceed, Pause, Roll Back), rationale, risk register, 24–48h-style action plan, communication plan, confidence score, traces.
- Optional local LLM (Ollama) enriches agent prose; if the model is missing or errors, each agent falls back to small rule functions in src/agents/.
- Interactive UI: Streamlit app.py. No FastAPI or separate SPA in this repo.

## Real-world anchor (Rapido-style transparency)

- The scenario is inspired by a real class of ride-hailing launches: showing riders **rejection-count or matching transparency** (the app surfaces that trips are being declined or retried instead of looking idle). Rapido and peers have shipped variants of this idea; this repo simulates a war-room review of that kind of feature.
- **Feature in plain terms:** while the user waits, the product makes visible that matching is active (e.g. rejections or attempts), so the experience is not a silent spinner.
- **Pros**
  - Transparency: users see activity behind the scenes.
  - Reduces the feeling that the app is stuck or broken when matching is slow.
  - Sets expectations that the system is working, not frozen.
- **Cons**
  - Surfaces **rejection** explicitly, which can feel personal or negative.
  - Can increase perceived friction, stress, and complaints even when underlying supply is the real issue.
  - Risk of higher drop-off or churn if the UI emphasizes bad news without enough offsetting reassurance.

## Metrics (latest row from metrics_timeseries.csv)

Each column is a snapshot at the end of the series; the tools also compute simple trend deltas (first three vs last three rows) for several fields.

- **ride_confirmation_rate_pct** — Share of booking attempts that end in a confirmed ride; core health of the funnel.
- **cancellation_dropoff_rate_pct** — Users abandoning or canceling after seeing friction (including post-rejection visibility); proxy for UX pain.
- **retry_rate_pct** — How often users retry after difficulty; high values suggest struggle or confusion.
- **time_to_ride_confirmation_sec** — Latency until confirmation; operational and reliability pressure.
- **fare_increase_rate_pct** — How much fares have moved in the period; pricing context alongside demand.
- **price_elasticity_of_conversion** — Sensitivity of conversion to price; helps interpret revenue vs volume tradeoffs.
- **driver_acceptance_rate_pct** — Supply-side willingness to take trips; low values stress matching.
- **rejections_per_successful_ride** — Average driver declines before a success; direct lever for the transparency feature’s narrative and pain.
- **support_tickets** — Volume of support contacts; load and sentiment pressure on ops.
- **churn_pct** — User churn signal; long-term product and business risk.

Delta fields in the summary (e.g. delta_ride_confirmation_rate, delta_cancellation_dropoff, delta_support_tickets) are used for narrative and for parts of confidence scoring, not for the main Proceed/Pause/Roll Back gate.

## User feedback (user_feedback.csv)

- Rows carry **sentiment** (positive / neutral / negative), **tags**, and text; tools aggregate **sentiment_counts**, **negative_ratio**, and **top_issue_tags**.
- **release_notes.md** in the baseline pack is for human context only; the coordinator does not parse it.

## Orchestration

- **Coordinator** (linear flow in src/orchestrator/coordinator.py, not a graph engine):
  - Resolve data/<scenario>/metrics_timeseries.csv and user_feedback.csv (fallback feedback file: data/baseline/user_feedback.csv if a scenario file is absent).
  - **Tools:** metrics_tools.load_metrics + summarize_metrics; feedback_tools.load_feedback + summarize_sentiment.
  - Build **shared_ctx:** scenario name, metric_summary, feedback_summary — every agent receives the same dict.
  - Run agents **in order:** PM → Data Analyst → Marketing/Comms → Risk/Critic → Reliability Engineer → Business Impact. Each call is logged to a new traces/trace_<scenario>_<timestamp>.log.
  - **Final decision:** computed only after all agents finish, by coordinator logic **_decide(metric_summary)** (see below). Not chosen by LLM majority vote.
  - **Confidence:** coordinator **_confidence(...)** blends evidence strength vs reference bands, how many agents’ **metric-derived leans** match that final decision, data completeness, and a severity signal. Stored as confidence_score plus confidence_breakdown in the output.
  - Merge agent outputs into rationale, risk_register, templated action_plan and communication_plan from the coordinator, then write_json / write_yaml to outputs/final_decision_<scenario>.json and .yaml.

## Agents — what each does and how it “thinks”

In code, “thinking” is either (1) an LLM prompt with shared_ctx or (2) a deterministic function with the same inputs. Published **decision_lean** per agent is **normalized to a metric-and-feedback vote** (_agent_vote_from_metrics) so narratives cannot override safety-style leans.

- **Product Manager (pm)**  
  - **Intent:** Product tradeoffs, retention, and whether sentiment is toxic enough to stop.  
  - **Rule lean:** Roll Back if churn_pct > 4.8 or negative_ratio > 0.72; Pause if churn_pct > 4.0 or negative_ratio > 0.55; else Proceed.

- **Data Analyst (data)**  
  - **Intent:** Funnel health, confirmation and drop-off, supply acceptance.  
  - **Rule lean:** Roll Back if ride_confirmation_rate_pct < 68 or driver_acceptance_rate_pct < 52; Pause if ride_confirmation_rate_pct < 74 or cancellation_dropoff_rate_pct > 28; else Proceed.

- **Marketing / Comms (comms)**  
  - **Intent:** Internal and external messaging; highly sensitive to feedback tone.  
  - **Rule lean:** Roll Back if negative_ratio > 0.7; Pause if negative_ratio > 0.5; else Proceed.

- **Risk / Critic (risk)**  
  - **Intent:** Counts “high risk” signals: rejections_per_successful_ride > 3.8, cancellation_dropoff_rate_pct > 30, negative_ratio > 0.7.  
  - **Rule lean:** Roll Back if two or more fire; Pause if exactly one; else Proceed.

- **Reliability Engineer (reliability)**  
  - **Intent:** Latency and repeated rejection loops as incident-style risk.  
  - **Rule lean:** Roll Back if time_to_ride_confirmation_sec > 165 or rejections_per_successful_ride > 4.1; Pause if time > 145 or rejections > 3.5; else Proceed.

- **Business Impact (business)**  
  - **Intent:** Conversion and churn as revenue and support exposure.  
  - **Rule lean:** Roll Back if ride_confirmation_rate_pct < 66 or churn_pct > 4.8; Pause if ride_confirmation_rate_pct < 74 or churn_pct > 3.6; else Proceed.

## Who issues the final decision, and on what metrics

- **Owner:** the **coordinator** (War Room decision function **_decide**), not any single persona agent and not the LLM.
- **Inputs:** only **metric_summary** scalars (agents shape narrative and risk text; their leans feed **agreement** inside confidence, not the final label).
- **Roll Back** if **any** severe threshold hits:
  - ride_confirmation_rate_pct < 68, or cancellation_dropoff_rate_pct > 34, or driver_acceptance_rate_pct < 52, or churn_pct > 4.5, or time_to_ride_confirmation_sec > 160, or rejections_per_successful_ride > 4.2.
- **Else Pause** if **any** of:
  - ride_confirmation_rate_pct < 74, or cancellation_dropoff_rate_pct > 28, or time_to_ride_confirmation_sec > 145, or rejections_per_successful_ride > 3.5, or churn_pct > 3.6.
- **Else Proceed.**

Action and communication plans in the JSON are **selected from templates** keyed off that final decision (and feedback/metrics for nuance), then assembled with build_final_output in src/schemas/final_output_schema.py.

## Outputs

- Overwrites outputs/final_decision_<scenario>.json and outputs/final_decision_<scenario>.yaml each run.
- Appends traces/trace_<scenario>_<YYYYMMDD_HHMMSS>.log.
- Result dict includes _meta with paths; also agent_decisions, agent_summaries, confidence_breakdown beyond the core schema fields.

## Setup

From the repository root, using Python 3:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

- requirements.txt: streamlit, pandas, plotly; other imports are standard library.
- Optional Ollama: OLLAMA_BASE_URL (default http://localhost:11434), OLLAMA_MODEL (default llama3.2:3b). Example: ollama pull llama3.2:3b from https://ollama.com

## Run (CLI)

    python3 run.py --scenario baseline
    python3 run.py --scenario optimistic
    python3 run.py --scenario critical

## Run (Streamlit)

    streamlit run app.py

## Tests

    python3 -m unittest tests/test_assignment1_compliance.py

## Repository layout

    README.md
    app.py
    requirements.txt
    run.py
    data/
        README.md
        data_manifest.yaml
        baseline/
            metrics_timeseries.csv
            release_notes.md
            user_feedback.csv
        critical/
            metrics_timeseries.csv
            user_feedback.csv
        optimistic/
            metrics_timeseries.csv
            user_feedback.csv
    outputs/
    src/
        agents/
            business_impact_agent.py
            data_analyst_agent.py
            marketing_comms_agent.py
            pm_agent.py
            reliability_engineer_agent.py
            risk_critic_agent.py
        llm/
            agent_brain.py
            client.py
        orchestrator/
            coordinator.py
        schemas/
            final_output_schema.py
        tools/
            feedback_tools.py
            metrics_tools.py
        utils/
            io_helpers.py
            logger.py
    tests/
        test_assignment1_compliance.py
    traces/
