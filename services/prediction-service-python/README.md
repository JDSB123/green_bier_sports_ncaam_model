# NCAAM Prediction Service

This directory hosts the self-contained prediction service. For users who cannot start
the full Docker/Postgres stack, there is a lightweight helper CLI:

```bash
python scripts/manual_matchup.py --home "Utah" --away "Washington"
```

You can override the spread/total or the implied American prices via
`--spread`, `--total`, `--spread-home-price`, `--over-price`, etc. The helper only
covers the Utah/Washington presets right now, but the fixture dictionary at the top
of `scripts/manual_matchup.py` can be extended with additional teams as needed.

## Prediction backend

The service supports an explicit backend switch:

- `PREDICTION_BACKEND=v33` (default): uses the built-in `prediction_engine_v33` logic.
- `PREDICTION_BACKEND=linear_json`: uses the repo's lightweight JSON linear/logistic artifacts.

When using `linear_json`:

- Set `LINEAR_JSON_MODEL_DIR` (default inside container: `/app/models/linear`).
- The `/predict` request must include `market_odds` with: `spread`, `total`, `spread_1h`, `total_1h`.

## Smoke checks

- `GET /health` validates DB connectivity/migrations (may show `degraded`/`error` if DB not configured).
- `GET /health/predict` runs an in-memory sample prediction using the configured backend.
