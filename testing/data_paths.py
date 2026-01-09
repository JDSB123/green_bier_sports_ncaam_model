"""Centralized filesystem paths for canonical historical data.

This project treats `ncaam_historical_data_local/` as the single source of
truth for historical scores/odds/ratings used by backtesting and validation
scripts.

Data Repository: https://github.com/JDSB123/ncaam-historical-data
Current Tag: v2026.01.09-canonical
Azure Backup: metricstrackersgbsv/ncaam-historical-raw

Most scripts also accept environment overrides; this module provides a stable
Python API for paths used throughout `testing/scripts/`.

IMPORTANT: All team names MUST be resolved through team_aliases_db.json
to ensure consistency between training and inference.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataPaths:
    """Canonical data locations (all Paths are absolute)."""

    project_root: Path
    root: Path

    @staticmethod
    def from_env(project_root: Path) -> "DataPaths":
        default_root = project_root / "ncaam_historical_data_local"
        historical_root = Path(
            os.environ.get(
                "HISTORICAL_DATA_ROOT",
                default_root,
            )
        ).resolve()
        return DataPaths(
            project_root=project_root.resolve(),
            root=historical_root,
        )

    # ---- Scores ----
    @property
    def scores_fg(self) -> Path:
        return (self.root / "scores" / "fg").resolve()

    @property
    def scores_h1(self) -> Path:
        return (self.root / "scores" / "h1").resolve()

    # ---- Canonicalized scores ----
    @property
    def scores_fg_canonical(self) -> Path:
        return (self.root / "canonicalized" / "scores" / "fg").resolve()

    @property
    def scores_h1_canonical(self) -> Path:
        return (self.root / "canonicalized" / "scores" / "h1").resolve()

    # ---- Odds ----
    @property
    def odds_root(self) -> Path:
        return (self.root / "odds").resolve()

    @property
    def odds_normalized(self) -> Path:
        return (self.root / "odds" / "normalized").resolve()

    # ---- Canonicalized odds ----
    @property
    def odds_canonical_spreads_fg(self) -> Path:
        return (self.root / "canonicalized" / "odds" / "spreads").resolve()

    @property
    def odds_canonical_spreads_h1(self) -> Path:
        return (self.root / "canonicalized" / "odds" / "spreads").resolve()

    @property
    def odds_canonical_totals_fg(self) -> Path:
        return (self.root / "canonicalized" / "odds" / "totals").resolve()

    @property
    def odds_canonical_totals_h1(self) -> Path:
        return (self.root / "canonicalized" / "odds" / "totals").resolve()

    # ---- Ratings ----
    @property
    def ratings_raw_barttorvik(self) -> Path:
        return (self.root / "ratings" / "raw" / "barttorvik").resolve()

    # ---- Backtest datasets ----
    @property
    def backtest_datasets(self) -> Path:
        return (self.root / "backtest_datasets").resolve()

    # ---- Team aliases (CRITICAL for canonicalization) ----
    @property
    def team_aliases_db(self) -> Path:
        return (self.root / "backtest_datasets" / "team_aliases_db.json").resolve()

    # ---- Data manifest (checksums for integrity) ----
    @property
    def data_manifest(self) -> Path:
        return (self.root / "DATA_MANIFEST.json").resolve()

    # ---- Master odds file ----
    @property
    def odds_consolidated(self) -> Path:
        return (self.root / "odds" / "normalized" / "odds_consolidated_canonical.csv").resolve()

    # ---- Barttorvik ratings ----
    @property
    def barttorvik_ratings(self) -> Path:
        return (self.root / "backtest_datasets" / "barttorvik_ratings.csv").resolve()


# Expected data repo tag for reproducibility
EXPECTED_DATA_TAG = "v2026.01.09-canonical"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATHS = DataPaths.from_env(PROJECT_ROOT)


def verify_data_integrity() -> bool:
    """Verify that the data repo is at the expected tag."""
    import subprocess
    data_root = DATA_PATHS.root
    try:
        result = subprocess.run(
            ["git", "-C", str(data_root), "describe", "--tags", "--exact-match"],
            capture_output=True, text=True
        )
        current_tag = result.stdout.strip()
        if current_tag == EXPECTED_DATA_TAG:
            return True
        print(f"WARNING: Data repo at {current_tag}, expected {EXPECTED_DATA_TAG}")
        return False
    except Exception:
        return False
