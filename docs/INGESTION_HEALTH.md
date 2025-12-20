# Ingestion Healthcheck

This guide helps quickly validate external API ingestion is operational and resilient.

## What it checks
- Barttorvik ratings JSON endpoint responds and decodes
- The Odds API odds endpoint responds with valid JSON (using configured API key)
- Retries on transient failures (429/5xx, network errors) with exponential backoff and jitter

## Prerequisites
- Odds API key available via environment `THE_ODDS_API_KEY` or Docker secret `/run/secrets/odds_api_key`
- Python with dependencies installed (see below)

## Install dependencies
Use the testing requirements:

```bash
pip install -r testing/requirements.txt
```

## Run the healthcheck
Default options match service configuration (season auto-calculated, sport key `basketball_ncaab`).

```bash
python testing/scripts/ingestion_healthcheck.py
```

Override options if needed:
```bash
python testing/scripts/ingestion_healthcheck.py --season 2025 --sport-key basketball_ncaab
```

Exit codes: `0` when all checks pass, `1` otherwise.

## Interpreting results
- PASS: Endpoint reachable and payload decoded as expected.
- FAIL: Includes the reason (rate limited, server error, JSON parse error, missing key).

If Odds API reports `429` frequently, consider:
- Reducing poll interval
- Ensuring per-minute quotas are observed (see Rust rate limiter)
- Honoring `Retry-After` headers (already implemented in services)

## Related resilience changes
- Go ratings sync: robust HTTP retries/backoff and `Retry-After` support.
- Rust odds ingestion: retries for `429/5xx`, `Retry-After` honored.
- Python orchestrator: one-shot retry when a sync step fails.
