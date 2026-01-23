# Ratings Sync (Go)

Manual-only job to pull Barttorvik ratings into Postgres. Runs once per invocation; no scheduler.

## Run

```bash
cd services/ratings-sync-go
go run ./...
```

## Test

```bash
cd services/ratings-sync-go
go test ./...
```

## Configuration

- `DATABASE_URL` — Postgres connection string
- `SEASON` — season year (e.g., 2025)
- `RUN_ONCE` — set to `true` to enforce single run (default)
- `STRICT_TEAM_MATCHING` — keep `true` in production to avoid creating unresolved teams
- `ALLOW_TEAM_CREATION` — set to `true` only for controlled data backfills

Provide these as environment variables before running (e.g., export in your shell or use a local `.env` with a loader like direnv).

## Notes

- Mirrors manual-only policy: operators trigger runs when fresh ratings are needed.
- Logs are structured (zap) and print to stdout.
