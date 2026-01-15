#!/usr/bin/env python3
"""
Deprecated wrapper for augmenting the canonical backtest master.

Use testing/scripts/augment_backtest_master.py instead.
"""
from __future__ import annotations

import warnings
from pathlib import Path
import sys

# Ensure project root is on sys.path so `testing` imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.scripts.augment_backtest_master import main


if __name__ == "__main__":
    warnings.warn(
        "build_consolidated_master.py is deprecated; use augment_backtest_master.py",
        RuntimeWarning,
    )
    main()
