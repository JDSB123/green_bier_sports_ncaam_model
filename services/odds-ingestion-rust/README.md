# Odds Ingestion (Rust)

Manual-only odds ingestion service. Pulls live odds and writes to Postgres/Redis; exposes a health endpoint.

## Run

```bash
cd services/odds-ingestion-rust
cargo run
```

## Test

```bash
cd services/odds-ingestion-rust
cargo test
```

## Configuration

The service reads configuration from environment variables (loaded via `dotenvy`), including database/Redis connection strings and API keys. Create a `.env` here or export variables before running.

## Notes

- Keep runs operator-triggered; no background schedulers.
- Use `RUN_ONCE=true` (or equivalent flag if present) when running in batch mode to align with manual-only policy.
