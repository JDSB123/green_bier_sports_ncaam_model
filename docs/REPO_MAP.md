# Repository Map

This document orients the codebase and standardizes how to run, lint, and test each component.

## Services

| Area | Path | Language | Purpose | How to run | Lint/Test |
| --- | --- | --- | --- | --- | --- |
| Prediction API | services/prediction-service-python | Python (FastAPI) | Serve predictions and health endpoints | `make api` (dev) or `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` inside service | `make lint` / `make test` (runs repo-level ruff/pytest) |
| Ratings Sync | services/ratings-sync-go | Go | Fetch Barttorvik ratings and store in Postgres; manual run | `cd services/ratings-sync-go && go run ./...` | `cd services/ratings-sync-go && go test ./...` |
| Odds Ingestion | services/odds-ingestion-rust | Rust | Ingest live odds into Postgres/Redis; manual run | `cd services/odds-ingestion-rust && cargo run` | `cd services/odds-ingestion-rust && cargo test` |
| Web Frontend | services/web-frontend | Static (nginx) | Static landing/status page | `docker build -t web-frontend services/web-frontend` | Static assets only |

## Supporting directories

- database/: migrations and seeds for Postgres
- models/: model artifacts (linear JSON, etc.)
- scripts/: operator scripts (health checks, data exports); prefer service-scoped scripts when adding new ones
- docs/: architecture, setup, governance; see docs/DATA_GOVERNANCE_INDEX.md for data rules

## Environment and configuration

- Standard pattern: `.env.example` → copy to `.env` (root and each service). Service examples added in `services/*/.env.example`.
- Existing `.env.local*` files remain for backward compatibility; prefer `.env` going forward.
- Root `.env` feeds shared settings; service-specific `.env` stays alongside the service.
- Secrets: use environment variables (see README and docs/setup/API_KEY_SETUP.md). Do not commit real secrets.

## Tasks (root)

Use `make` from the repo root:

- `make install` — install Python deps into .venv (base + dev tools)
- `make lint` — ruff check
- `make format` — ruff format
- `make test` — pytest
- `make api` — run FastAPI dev server (uvicorn)

## Conventions

- Manual-only operations: no background cron jobs; operators trigger syncs and predictions.
- Prefer embedding service-specific tooling under each service (README, env sample, scripts/ or cmd/).
- Document new commands in this map and in the relevant service README.
