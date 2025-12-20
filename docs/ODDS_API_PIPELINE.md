# NCAAM Odds API Pipeline (Repeatable Path)

This guide defines a clear, configurable, and repeatable path to pull all available NCAAM markets from your Premium The Odds API subscription. It uses the existing Rust ingestion service with environment-driven settings, keeping the pipeline robust and easy to extend.

## Overview
- Service: services/odds-ingestion-rust (Rust)
- Entry points:
  - Full-game odds: /v4/sports/{sport_key}/odds
  - Per-event odds (1H/2H): /v4/sports/{sport_key}/events/{event_id}/odds
- Storage: PostgreSQL/TimescaleDB (`odds_snapshots`), joined to `games` and `teams`
- Streaming: Redis Streams (`odds.live`)
- Orchestration: run via Python `run_today.py` or container start script

## Sport & Markets
- Default `sport_key`: `basketball_ncaab`
- Full-game markets: spreads, totals, h2h
- First half markets (premium): spreads_h1, totals_h1, h2h_h1
- Second half markets: spreads_h2, totals_h2, h2h_h2
- Bookmaker preferences:
  - H1: `bovada,pinnacle,circa,bookmaker`
  - H2: `draftkings,fanduel,pinnacle,bovada`

All of the above are now configurable via environment variables to cover additional/remaining markets as your subscription allows.

## Configuration (Env Vars)
Set these to tailor coverage without code changes:
- `SPORT_KEY`: override sport key (default: `basketball_ncaab`)
- `REGIONS`: odds regions (default: `us`)
- `ODDS_FORMAT`: odds format (default: `american`)
- `MARKETS_FULL`: full-game markets comma list (default: `spreads,totals,h2h`)
- `MARKETS_H1`: first-half markets (default: `spreads_h1,totals_h1,h2h_h1`)
- `MARKETS_H2`: second-half markets (default: `spreads_h2,totals_h2,h2h_h2`)
- `BOOKMAKERS_H1`: preferred books for H1 (default: `bovada,pinnacle,circa,bookmaker`)
- `BOOKMAKERS_H2`: preferred books for H2 (default: `draftkings,fanduel,pinnacle,bovada`)
- `RUN_ONCE`: `true` for one-shot sync (skip per-event half markets), `false` for continuous
- `POLL_INTERVAL_SECONDS`: continuous polling interval (default: `30`)

Secrets are read from Docker secrets by default:
- `/run/secrets/odds_api_key` → The Odds API key
- `/run/secrets/db_password` → database password
- `/run/secrets/redis_password` → redis password

## Repeatable Run Paths

### One-shot (fast CLI run)
- Purpose: Pull full-game markets rapidly for daily predictions.
- Behavior: Skips per-event half markets to avoid long runs/timeouts.
- How to run:
```bash
export RUN_ONCE=true
# Optional overrides
export MARKETS_FULL="spreads,totals,h2h" # add/remove markets as needed
python services/prediction-service-python/run_today.py
```

### Continuous (daemon)
- Purpose: Stream and store full + half markets continuously.
- Behavior: Polls full-game odds; then per-event H1/H2 odds; stores and publishes.
- How to run (in container):
```bash
# Example overrides; adjust to cover remaining markets/books supported by premium plan
export REGIONS="us"
export ODDS_FORMAT="american"
export MARKETS_FULL="spreads,totals,h2h"
export MARKETS_H1="spreads_h1,totals_h1,h2h_h1"
export MARKETS_H2="spreads_h2,totals_h2,h2h_h2"
export BOOKMAKERS_H1="bovada,pinnacle,circa,bookmaker"
export BOOKMAKERS_H2="draftkings,fanduel,pinnacle,bovada"
# Start app per your orchestrator (Compose/K8s/ACA)
```

## Extending Coverage (Remaining Endpoints/Markets)
- To add new markets (e.g., alternates or other period-specific markets), set the corresponding env var lists:
  - Include supported market keys in `MARKETS_FULL`, `MARKETS_H1`, `MARKETS_H2`.
  - Optionally refine `BOOKMAKERS_H1`/`BOOKMAKERS_H2` to target books known to publish those markets.
- If your premium plan includes additional per-event markets beyond 1H/2H, add them to the appropriate env list. The ingestion service will normalize them when keys match the Odds API market naming conventions.
- If props or other specialty markets are enabled for NCAAM on your plan, create a separate run profile with dedicated env vars listing those market keys to avoid exceeding rate limits.

## Rate Limits & Reliability
- Built-in rate limiting: 45 req/min (per The Odds API guidance)
- Retries: Exponential backoff; honors `Retry-After` when provided
- H1/H2 handling: gracefully skips events where half markets are unavailable
- Diagnostics: health server exposes `/health` (port via `HEALTH_PORT`, default 8083)

## Data Flow & Storage
- Normalize teams before writing games and odds; aliases stored from The Odds API names
- Snapshots stored in `odds_snapshots` with unique key on `(time, game_id, bookmaker, market_type, period)` and upsert semantics
- Preferred bookmaker selection happens at query time in `run_today.py` using `latest_odds` CTEs

## Validation & Health
- Run ingestion health check:
```bash
python testing/scripts/ingestion_healthcheck.py --sport-key basketball_ncaab
```
- Inspect health endpoint:
```bash
curl http://localhost:8083/health
```

## Notes
- Avoid hardcoding markets/bookmakers in code; use env vars for flexibility.
- For high coverage of all remaining markets under your premium plan, maintain a documented set of env var profiles (e.g., full-game only, full+1H, full+1H+2H, specialty markets) and schedule runs accordingly.
- Keep an eye on The Odds API rate limits; split runs or stagger per-event requests if expanding market lists significantly.
