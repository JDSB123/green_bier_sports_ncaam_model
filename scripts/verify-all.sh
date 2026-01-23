#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$PROJECT_ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "[ERROR] Missing venv python at $VENV_PY"
  echo "Run: python scripts/codespaces/ensure_codespace_ready.py"
  exit 1
fi

cd "$PROJECT_ROOT"

echo "[INFO] Python: $($VENV_PY --version)"

echo "[INFO] Ruff check"
"$VENV_PY" -m ruff check .

echo "[INFO] Pytest"
"$VENV_PY" -m pytest

echo "[OK] All checks passed"
