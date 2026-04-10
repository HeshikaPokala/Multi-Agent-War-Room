# Multi-Agent Launch War Room (Decision Engine)

This project simulates a **real-world product launch war room**, where multiple specialized roles evaluate a feature and arrive at a structured go/no-go decision.

The system ingests mock launch data (metrics + user feedback), runs it through six domain-specific agents, and produces a single outcome:

**Proceed · Pause · Roll Back**

Along with the decision, it generates:
- A clear rationale grounded in data  
- A structured risk register  
- A 24–48 hour action plan  
- A communication plan  
- A confidence score (with breakdown)  
- Full execution traces for transparency  

---

## What makes this different

- Decisions are **not LLM-driven opinions** — they are **strictly metric-based**
- Agents contribute **perspective and reasoning**, not authority over the outcome  
- The system is designed to feel like a **real cross-functional war room**, not just a pipeline  

---

## Real-world Use Case (User-visible Rejection Feedback)

Inspired by ride-hailing platforms like Rapido, this project explores a feature where users are shown **real-time matching activity**, including failed attempts or rejections.

### Feature idea

Instead of a silent loading state, the app surfaces activity such as:
- Drivers being contacted  
- Matching retries  
- Declined requests  

> The goal is to make waiting feel active, not broken.

---

### Why this is useful

- Builds **trust through transparency**  
- Reduces the perception of system failure  
- Sets realistic expectations during delays  

---

### Where it can fail

- Visible **rejections can feel personal**  
- Can increase frustration during slow matching  
- Risks higher churn if negative signals are overemphasized  

---

### Core trade-off

This feature sits between:
- **Clarity** (show what's happening)  
- **Experience** (avoid discouraging the user)  

The challenge is not visibility — it’s **how that visibility is framed**.

---

## Scenarios 

The system evaluates the feature across three simulated environments:

- **Baseline**  
  Represents a normal launch state and acts as the reference point  

- **Optimistic**  
  Improved conditions (higher acceptance, better sentiment, smoother funnel)  

- **Critical**  
  Degraded conditions (high rejection rates, poor conversion, negative sentiment)  

---

### Why this matters

- Enables **relative comparison**, not just absolute judgment  
- Shows how the same feature behaves under **different real-world pressures**  
- Prevents overfitting decisions to a single scenario  

> The baseline anchors interpretation — optimistic and critical scenarios provide contrast.

---

## Data Inputs

### Metrics

Each scenario includes a time series of key product and operational signals:

- **Ride confirmation rate** — Percentage of booking attempts that successfully result in a confirmed ride.  
- **Cancellation/drop-off rate** — Share of users who abandon or cancel the process after encountering friction.  
- **Retry rate** — Frequency at which users attempt booking again after a failed or delayed match.  
- **Time to confirmation** — Average time taken from request initiation to ride confirmation.  
- **Driver acceptance rate** — Percentage of ride requests accepted by drivers, indicating supply willingness.  
- **Rejections per successful ride** — Average number of driver declines before a ride is successfully matched.  
- **Churn** — Proportion of users who stop using the platform over a given period.  
- **Support tickets** — Number of user complaints or help requests raised, reflecting operational strain.  
- **Pricing and elasticity signals** — Indicators of how price changes impact user conversion and demand.   

The system also computes **trend deltas** to capture directional changes.

---

### User Feedback

Synthetic feedback includes:
- Sentiment (positive / neutral / negative)  
- Tags (top issues)  
- Free-text comments  

Aggregated into:
- `sentiment_counts`  
- `negative_ratio`  
- `top_issue_tags`

### User Feedback - Summary

**Baseline (40 responses)**  
- Positive: 8 (20.0%)  
- Neutral: 7 (17.5%)  
- Negative: 25 (62.5%)  

**Optimistic (30 responses)**  
- Positive: 23 (76.7%)  
- Neutral: 3 (10.0%)  
- Negative: 4 (13.3%)  

**Critical (30 responses)**  
- Positive: 3 (10.0%)  
- Neutral: 1 (3.3%)  
- Negative: 26 (86.7%)  

---

## Orchestration

### Coordinator

The **Coordinator** (`src/orchestrator/coordinator.py`) controls the entire pipeline using a **deterministic, linear flow**.

It is intentionally **not a graph engine** — execution order is fixed and predictable.

---

### Data Resolution

- Loads:
  - `data/<scenario>/metrics_timeseries.csv`
  - `data/<scenario>/user_feedback.csv`  
- Falls back to baseline feedback if missing  

---

### Shared Context

All agents receive the same structured input:

- `scenario_name`  
- `metric_summary`  
- `feedback_summary`  

This ensures consistent reasoning across roles.

---

### Agent Flow

Agents run sequentially:

1. Product Manager  
2. Data Analyst  
3. Marketing / Communications  
4. Risk / Critic  
5. Reliability Engineer  
6. Business Impact  

Each run is logged:

```
traces/trace_<scenario>_<timestamp>.log
```

---

## Agents (Role-driven reasoning)

Each agent evaluates the launch from a specific lens.

Their outputs include:
- Narrative reasoning  
- A normalized **decision lean** (metric-driven, not opinion-based)  

### Roles

- **Product Manager** → retention, sentiment toxicity  
- **Data Analyst** → funnel + supply health  
- **Marketing / Comms** → user perception and messaging risk  
- **Risk / Critic** → counts high-risk signals  
- **Reliability Engineer** → latency and system stress  
- **Business Impact** → conversion and revenue implications  

> Important: Agent outputs influence reasoning and confidence — **not the final decision**.

---

## Final Decision Logic

The final outcome is computed by the coordinator:

```
_decide(metric_summary)
```

### Rules

**Roll Back** if any severe condition is met:
- Very low confirmation rate  
- High drop-off  
- Low driver acceptance  
- High churn  
- High latency  
- Excessive rejections  

**Pause** if moderate issues are detected  

**Proceed** only if all signals are healthy  

---

## Confidence Scoring

Confidence is calculated using:

```
_confidence(...)
```

It blends:
- Strength of metric signals  
- Agreement between agent leans and final decision  
- Data completeness  
- Severity of issues  

Output includes:
- `confidence_score`  
- `confidence_breakdown`  

---

## Output

Each run generates:

```
outputs/final_decision_<scenario>.json
outputs/final_decision_<scenario>.yaml
```

Includes:
- Decision  
- Rationale  
- Risk register  
- Action plan  
- Communication plan  
- Agent summaries  
- Confidence details  

---

## Execution

### CLI

```
python3 run.py --scenario baseline
python3 run.py --scenario optimistic
python3 run.py --scenario critical
```

---

### Streamlit UI

```
streamlit run app.py
```

---

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional (LLM enrichment via Ollama):
- Default: `llama3.2:3b`
- Falls back to rule-based logic if unavailable  

---

## Repository Structure

```
src/
  agents/
  orchestrator/
  tools/
  schemas/
  llm/
  utils/

data/
  baseline/
  optimistic/
  critical/

outputs/
traces/
tests/
```

---

## Key Idea

This project is not just about running agents.

It’s about modeling how **real product decisions are made under uncertainty**:
- balancing data vs perception  
- separating signal from narrative  
- and making calls that are **defensible, not just explainable**
