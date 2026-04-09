# Multi-agent launch war room

Python pipeline that ingests mock launch metrics and user feedback, runs six specialist agents in sequence (with optional local LLM assistance), and writes a single structured go/no-go record: Proceed, Pause, or Roll Back, plus rationale, risk register, a short action plan, communication guidance, and a numeric confidence score. Traces append to timestamped log files under traces/.

The orchestrator is a linear Python coordinator, not a graph framework. It loads CSVs, builds metric and sentiment summaries, passes the same shared context dict into each agent call, then merges agent output into one final object. The published decision and confidence score are computed with fixed threshold rules on the metric summary (and related vote alignment), not by taking a free-form vote from the LLM. When Ollama is up, agents may produce richer narrative; on failure the code falls back to small deterministic functions in src/agents/. Outputs are normalized so decision_lean values and risk rows stay consistent with those rules.

Agent order: Product Manager, Data Analyst, Marketing/Comms, Risk/Critic, Reliability Engineer, Business Impact. Each step logs to the trace file. Shared state is the scenario name plus metric_summary and feedback_summary; each agent returns a dict that the coordinator may normalize (findings, recommendation, risk_register, communication_plan fields, etc.).

The Product Manager agent frames tradeoffs and churn or sentiment pressure. The Data Analyst agent emphasizes metric thresholds and trend deltas. The Marketing/Comms agent focuses on internal and external messaging angles. The Risk/Critic agent lists challenged assumptions and mitigations. The Reliability Engineer agent stresses confirmation latency, rejections, and operational guardrails. The Business Impact agent summarizes conversion, churn, and support exposure.

Tools are plain CSV helpers: src/tools/metrics_tools.py loads the time series and summarizes the latest row plus simple window deltas; src/tools/feedback_tools.py loads feedback and aggregates sentiment counts, tag frequency, and negative ratio. The coordinator does not read release_notes.md; that file is human context in the data pack only.

Sample data lives under data/baseline, data/optimistic, and data/critical. Each runnable scenario folder includes metrics_timeseries.csv and user_feedback.csv. Baseline also includes release_notes.md. If a scenario is missing user_feedback.csv, the coordinator falls back to data/baseline/user_feedback.csv. data/data_manifest.yaml inventories paths.

Each run overwrites outputs/final_decision_<scenario>.json and outputs/final_decision_<scenario>.yaml (for example outputs/final_decision_baseline.json). It also creates traces/trace_<scenario>_<YYYYMMDD_HHMMSS>.log. The returned dict includes _meta with absolute paths to those artifacts.

There is no FastAPI app or separate SPA in this repo. The browser UI is Streamlit in app.py (charts, agent activity, and the same JSON fields the CLI writes).

## Setup

From the repository root, using Python 3:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

requirements.txt lists streamlit, pandas, and plotly; the rest uses the standard library.

No environment variables are required for the default deterministic path. For optional Ollama integration, set OLLAMA_BASE_URL (default http://localhost:11434) and OLLAMA_MODEL (default llama3.2:3b). Install Ollama from https://ollama.com and pull a model, for example:

    ollama pull llama3.2:3b

If the LLM client errors or is unreachable, agents use their rule-based fallbacks automatically.

## Run (CLI)

    python3 run.py --scenario baseline
    python3 run.py --scenario optimistic
    python3 run.py --scenario critical

The CLI prints decision, confidence, and paths from _meta.

## Run (Streamlit)

    streamlit run app.py

## Tests

    python3 -m unittest tests/test_assignment1_compliance.py

The suite runs all three scenarios and checks expected decisions plus required top-level keys in the result dict.

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
