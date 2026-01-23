# Access & Credentials (Canonical)

This is the **single source of truth** for the access/credentials helpers in this repo.

## What It Does

The access manager checks common “can’t work in Codespaces” failure modes:

- `.env.local` / `.env.staging` / `.env.production` existence (and creates templates if missing)
- Git identity hints
- GitHub CLI auth hints (`gh auth login`)
- Azure CLI auth hints (`az login`)

## Run It Manually

### Python (recommended)

```bash
python scripts/codespaces/ensure_all_access.py --status
```

### Shell wrapper (runs automatically in devcontainer)

```bash
bash .devcontainer/ensure-all-access.sh
```

## Keys / Secrets

- Odds API key: use `ODDS_API_KEY` (preferred). `THE_ODDS_API_KEY` is accepted for compatibility.

See: `docs/setup/API_KEY_SETUP.md`
