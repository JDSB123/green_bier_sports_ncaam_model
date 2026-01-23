#!/usr/bin/env python3
"""Backward-compatible shim.

The canonical script lives at `scripts/codespaces/ensure_codespace_ready.py`.
This wrapper keeps old docs/commands working.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    script_path = Path(__file__).resolve().parent / "scripts" / "codespaces" / "ensure_codespace_ready.py"
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
