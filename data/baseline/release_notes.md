# Release Notes - Feature Launch: Rejection Count Visibility

## Release Window
- Gradual rollout started: 2026-03-30
- Current rollout coverage: 65% of active users
- Regions enabled: IN, SG, AE, UK

## What Changed
- Riders now see how many driver rejections occurred while searching for a match.
- Added contextual prompts to retry, adjust fare, or change pickup.
- Added telemetry for retry behavior, fare changes, and confirmation delays.
- Added support macros for rejection-count related queries.

## Intended Success Criteria
- Ride confirmation rate >= 76%
- Cancellation/drop-off <= 28%
- Driver acceptance >= 60%
- No material increase in support ticket volume
- Churn <= 4.0%

## Known Risks Before Launch
- Rejection visibility may increase user anxiety and early cancellations.
- Fare increase prompts may be perceived as price pressure.
- Higher transparency without context may reduce trust in low-supply zones.

## Known Issues Observed During Rollout
- Some riders misinterpret rejection count as app failure.
- Retry flow guidance is unclear after multiple rejections.
- Support load spikes in high-demand hours due to confusion around fare suggestion logic.

## Dependencies
- Driver dispatch service (`match-engine`)
- Dynamic pricing service (`fare-signal`)
- Rider messaging service (`in-app-prompts`)

## Temporary Guardrails
- Auto-pause rollout if ride confirmation drops below 72% for 2 consecutive days.
- Trigger incident review if drop-off exceeds 30% in key zones.
- Daily cross-functional review with Product, Data, Engineering, and Support.
