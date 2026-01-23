# Codespaces Setup (Canonical)

This is the **single source of truth** for Codespaces setup and “readiness” in this repo.

## What Runs Automatically

On Codespace start/restart, the devcontainer runs:

- `.devcontainer/post-start.sh`
  - Validates the Python venv exists and is healthy
  - Runs the readiness script
  - Runs the access manager

## Run Readiness Manually

### Option 1 (Recommended): Python readiness script

```bash
python scripts/codespaces/ensure_codespace_ready.py
```

Back-compat shim (still works):

```bash
python ensure_codespace_ready.py
```

### Option 2: Shell script

```bash
bash .devcontainer/ensure-codespace-ready.sh
```

## Start/Stop/Restart the API

### VS Code tasks (recommended)

See `.vscode/tasks.json`:

- `ncaam: api start (uvicorn)`
- `ncaam: api stop (port 8000)`
- `ncaam: api restart`

### Manual start

```bash
cd services/prediction-service-python
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Required Config

- Create/update `.env.local`
- Add `ODDS_API_KEY` (preferred). `THE_ODDS_API_KEY` is accepted for backward compatibility.

See: `docs/setup/API_KEY_SETUP.md`

## Troubleshooting

- If the venv is broken: `rm -rf .venv && python ensure_codespace_ready.py`
- If Redis/Postgres aren’t running locally: that can be OK depending on your mode; check `.env.local` and Docker compose.
