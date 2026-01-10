"""Centralized data access for canonical historical data.

SINGLE SOURCE OF TRUTH: Azure Blob Storage
- Container: ncaam-historical-data (canonical data)
- Container: ncaam-historical-raw (raw data, ncaahoopR 7GB)
- Storage Account: metricstrackersgbsv

Local fallback: ncaam_historical_data_local/ (for offline development)

Data can be accessed in two modes:
1. AZURE_FIRST (default): Read from Azure, cache locally
2. LOCAL_FIRST: Read locally, fallback to Azure if missing

Usage:
    from testing.data_paths import DATA_PATHS, get_data_reader
    
    # Use hybrid reader (tries local first, then Azure)
    reader = get_data_reader(prefer_azure=True)
    df = reader.read_csv("backtest_datasets/backtest_master.csv")
    
    # Or use paths for local access
    local_path = DATA_PATHS.backtest_datasets / "backtest_master.csv"

IMPORTANT: All team names MUST be resolved through team_aliases_db.json
to ensure consistency between training and inference.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from testing.azure_data_reader import HybridDataReader


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


# Azure configuration - SINGLE SOURCE OF TRUTH
AZURE_STORAGE_ACCOUNT = "metricstrackersgbsv"
AZURE_CANONICAL_CONTAINER = "ncaam-historical-data"
AZURE_RAW_CONTAINER = "ncaam-historical-raw"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATHS = DataPaths.from_env(PROJECT_ROOT)

# Global reader instance
_data_reader: Optional["HybridDataReader"] = None


def get_data_reader(prefer_azure: bool = True) -> "HybridDataReader":
    """
    Get the data reader (hybrid local/Azure).
    
    Args:
        prefer_azure: If True (default), always try Azure first.
                     Azure is the SINGLE SOURCE OF TRUTH.
    
    Returns:
        HybridDataReader that can read from local or Azure
    """
    global _data_reader
    
    # Lazy import to avoid import errors if azure not installed
    from testing.azure_data_reader import HybridDataReader
    
    if _data_reader is None or _data_reader.prefer_azure != prefer_azure:
        _data_reader = HybridDataReader(
            local_root=DATA_PATHS.root,
            azure_container=AZURE_CANONICAL_CONTAINER,
            prefer_azure=prefer_azure
        )
    
    return _data_reader


def verify_azure_data() -> bool:
    """Verify that Azure has the required data files."""
    try:
        from testing.azure_data_reader import AzureDataReader
        reader = AzureDataReader(container_name=AZURE_CANONICAL_CONTAINER)
        
        required_files = [
            "backtest_datasets/backtest_master.csv",
            "backtest_datasets/team_aliases_db.json",
            "scores/fg/games_all.csv",
        ]
        
        missing = []
        for f in required_files:
            if not reader.blob_exists(f):
                missing.append(f)
        
        if missing:
            print(f"WARNING: Azure missing {len(missing)} required files:")
            for f in missing:
                print(f"  - {f}")
            return False
        
        print("[OK] Azure has all required data files")
        return True
        
    except Exception as e:
        print(f"WARNING: Could not verify Azure data: {e}")
        return False


def print_data_status():
    """Print the current data source status."""
    print("=" * 60)
    print("NCAAM Data Source Status")
    print("=" * 60)
    
    # Local status
    print("\nLocal Data:")
    print(f"  Root: {DATA_PATHS.root}")
    print(f"  Exists: {DATA_PATHS.root.exists()}")
    
    if DATA_PATHS.root.exists():
        backtest_master = DATA_PATHS.backtest_datasets / "backtest_master.csv"
        print(f"  backtest_master.csv: {'EXISTS' if backtest_master.exists() else 'MISSING'}")
    
    # Azure status
    print("\nAzure Data:")
    print(f"  Storage Account: {AZURE_STORAGE_ACCOUNT}")
    print(f"  Canonical Container: {AZURE_CANONICAL_CONTAINER}")
    print(f"  Raw Container: {AZURE_RAW_CONTAINER}")
    
    try:
        from testing.azure_data_reader import AzureDataReader
        reader = AzureDataReader(container_name=AZURE_CANONICAL_CONTAINER)
        files = reader.list_files("backtest_datasets/", pattern="*.csv")
        print(f"  Backtest CSVs in Azure: {len(files)}")
        
        # Check ncaahoopR
        reader_raw = AzureDataReader(container_name=AZURE_RAW_CONTAINER)
        ncaahoopR_files = reader_raw.list_files("ncaahoopR_data-master/")
        print(f"  ncaahoopR files in Azure: {len(ncaahoopR_files)}")
        
    except Exception as e:
        print(f"  [ERROR] Could not connect: {e}")
    
    print()


if __name__ == "__main__":
    print_data_status()
