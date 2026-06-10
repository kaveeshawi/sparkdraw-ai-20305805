# Models

Place trained Scikit-learn model files here.

## Upsell Engine (C2)

| File | Purpose |
|------|---------|
| `upsell_model_v2.pkl` | Calibrated ensemble classifier — upsell readiness probability |
| `feature_names.pkl` | Ordered feature column names for inference |

Loaded by `routes/upsell.py` at first request. If files are missing, `POST /upsell` returns HTTP 503.

### Feature vector (9 inputs)

1. `completion_pct` — 0.0–1.0
2. `health_score` — 0–100
3. `revision_count` — integer
4. `approval_lag_hrs` — average hours
5. `budget_used_pct` — 0.0–1.0
6. `sentiment_avg` — −1 to +1
7. `project_age_days` — integer
8. `invoice_count` — integer (default 1)
9. `days_since_last_revision` — float (default 14.0)

### Output tiers

| Confidence | Tier | `upsell_ready` |
|------------|------|----------------|
| ≥ 0.75 | high | true |
| ≥ 0.55 | medium | true |
| < 0.55 | low | false |
