# Production Runbook (NCAAM)

## Goals

- **CST is canonical**: all “today” logic uses `America/Chicago`.
- **No picks without integrity**: 100% “today” team matching + odds freshness gate must pass.
- **Deterministic deploys**: schema migrations and image versions are controlled and repeatable.

## Deploy checklist

- **Build + push images** (ACR)
  - `ncaam-prediction`
  - `ncaam-odds-ingestion`
  - `ncaam-ratings-sync`
- **Run DB migrations** (mandatory)
  - The container runs `/app/run_migrations.py` on start; for external DBs you can run it as a one-shot job.
- **Health check**
  - `GET /health` on prediction-service
  - Confirm DB connectivity and redis connectivity.

## Daily operation (manual-only mode)

- Run `predict.bat`
  - Sync ratings (Go) + odds (Rust; falls back to Python if needed)
  - Enforce today’s 100% matching gate
  - Enforce odds freshness gate
  - Generate picks + optional Teams webhook health summary

## Failure modes + fixes

### 1) Today team matching gate fails

Symptom:
- `100% team matching gate FAILED`
- Blockers show exact team names.

Fix:
- Add/update `team_aliases` for the exact incoming string (`source='the_odds_api'`).
- If the alias exists but points at an **unrated** team, repoint it to the rated canonical team.
- Re-run `predict.bat`.

### 2) Odds freshness gate fails

Symptom:
- “stale odds … > MAX_ODDS_AGE_MINUTES”

Fix:
- Re-run odds sync (full + 1H). Ensure The Odds API key is valid.
- If Rust sync times out, confirm Python fallback ran; adjust `RUST_ODDS_SYNC_TIMEOUT_SECONDS`.

### 3) Rust odds sync timeouts

Fix:
- Increase `RUST_ODDS_SYNC_TIMEOUT_SECONDS` (default 240s).
- Confirm API connectivity / rate limiting.

### 4) Migration drift on existing DB volumes

Fix:
- Recreate prediction-service (it runs migrations on start), or run `/app/run_migrations.py` as a one-shot job.
- Verify `public.schema_migrations` has new migration filenames.

## Backup/restore (local)

- Backup:
  - `powershell -File scripts/backup_db.ps1`
- Restore:
  - `powershell -File scripts/restore_db.ps1 -Path backups/ncaam_YYYYMMDD_HHMMSS.sql`

## Notes

- Historical resolution audit can be <100% without blocking production (monitoring only). The “today gate” is the blocker.

