# Data Pack for Assessment 1

This folder contains realistic mock launch data for the multi-agent war-room simulation.

## Files

- `baseline/metrics_timeseries.csv`: 14 days of launch metrics.
- `baseline/user_feedback.csv`: 40 short feedback entries (positive, neutral, negative, with repeated issues and outliers).
- `baseline/release_notes.md`: feature change, rollout notes, known issues, and risk flags.

- `optimistic/metrics_timeseries.csv`: mostly healthy trend for "Proceed" style testing.
- `optimistic/user_feedback.csv`: sentiment-skewed positive feedback for optimistic runs.
- `critical/metrics_timeseries.csv`: degrading trend for "Pause/Roll Back" style testing.
- `critical/user_feedback.csv`: sentiment-skewed negative feedback for critical runs.

## Notes

- Dates are consecutive and align across files.
- Metrics are feature-specific for rejection-count visibility:
  - ride confirmation rate
  - cancellation/drop-off rate
  - retry rate
  - time to ride confirmation
  - fare increase rate
  - price elasticity of conversion
  - driver acceptance rate
  - rejections per successful ride
  - support ticket volume
  - churn rate
- Feedback is scenario-specific:
  - baseline: mixed sentiment
  - optimistic: mostly positive
  - critical: mostly negative
