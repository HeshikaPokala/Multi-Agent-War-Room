# AI/ML Engineer Assessment - Assignment 1

Multi-agent "war room" simulation for launch decision-making.

## What this project does

It analyzes:
- launch metrics (time series)
- user feedback
- release context

Then it outputs a structured decision:
- `Proceed`
- `Pause`
- `Roll Back`

along with rationale, risk register, 24-48h action plan, communication guidance, confidence score, and trace logs.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python run.py --scenario baseline
python run.py --scenario optimistic
python run.py --scenario critical
```

## Live Frontend Dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

The frontend shows:
- metric trends
- live agent activity
- final decision, confidence, risks, action plan
- structured output JSON in one place

## Smart Agents (Free LLM via Ollama)

Agents now support LLM reasoning using a free local model through Ollama.

1. Install Ollama: [https://ollama.com](https://ollama.com)
2. Pull a model:

```bash
ollama pull llama3.2:3b
```

3. Run as usual:

```bash
python run.py --scenario baseline
```

Optional env vars:
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL` (default `llama3.2:3b`)

If Ollama is unavailable, the system automatically falls back to deterministic rules.

## Output Files

- `outputs/final_decision_<scenario>.json`
- `outputs/final_decision_<scenario>.yaml`
- `traces/trace_<scenario>_<timestamp>.log`

## Required Env Variables

None for this baseline deterministic version.

If you later connect an LLM provider, add secrets in `.env` and never hard-code keys.
