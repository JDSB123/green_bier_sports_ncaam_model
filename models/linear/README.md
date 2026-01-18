# Linear/Logistic JSON Models

This folder contains lightweight, JSON-serialized models used by scripts/backtests (and optionally paper-mode tooling).

## What’s in here
- `fg_spread.json`, `h1_spread.json`, etc.: linear or logistic models serialized as JSON.
- These artifacts are intentionally **not** stored under `testing/` to avoid conflating “model artifacts” with “test-only code”.

## How to regenerate
Run the training pipeline:

```bash
python testing/scripts/train_independent_models.py
```

Then run a backtest using the trained artifacts:

```bash
python testing/scripts/run_historical_backtest.py --market fg_spread --seasons 2024,2025 --use-trained-models
```

## Notes
- These models are loaded via the shared loader in `ncaam/linear_json_model.py`.
- Production service model loading is intentionally decoupled from `testing/` and from these artifacts unless explicitly wired in.
