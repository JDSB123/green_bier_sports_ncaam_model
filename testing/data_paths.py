"""Centralized data access for canonical historical data.

SINGLE SOURCE OF TRUTH: Azure Blob Storage
- Container: ncaam-historical-data (canonical data)
- Container: ncaam-historical-raw (raw data, ncaahoopR 7GB)
- Storage Account: metricstrackersgbsv

Data is accessed directly from Azure Blob Storage. No local cache or
git repo storage is permitted for canonical datasets.

Usage:
    from testing.data_paths import DATA_PATHS, get_data_reader

    # Use Azure reader (single source of truth)
    reader = get_data_reader()
    df = reader.read_csv("backtest_datasets/backtest_master.csv")

    # Blob paths for convenience
    blob_path = DATA_PATHS.backtest_datasets / "backtest_master.csv"

IMPORTANT: All team names MUST be resolved through team_aliases_db.json
to ensure consistency between training and inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testing.azure_data_reader import AzureDataReader


@dataclass(frozen=True)
class DataPaths:
    """Canonical data blob locations (all paths are Azure blob paths)."""

    root: PurePosixPath = PurePosixPath("")

    # ---- Scores ----
    @property
    def scores_fg(self) -> PurePosixPath:
        return self.root / "scores" / "fg"

    @property
    def scores_h1(self) -> PurePosixPath:
        return self.root / "scores" / "h1"

    # ---- Legacy canonicalized scores (deprecated; alias to canonical) ----
    @property
    def scores_fg_canonical(self) -> PurePosixPath:
        return self.scores_fg

    @property
    def scores_h1_canonical(self) -> PurePosixPath:
        return self.scores_h1

    # ---- Odds ----
    @property
    def odds_root(self) -> PurePosixPath:
        return self.root / "odds"

    @property
    def odds_normalized(self) -> PurePosixPath:
        return self.root / "odds" / "normalized"

    # ---- Legacy canonicalized odds (deprecated; alias to canonical) ----
    @property
    def odds_canonical_spreads_fg(self) -> PurePosixPath:
        return self.odds_normalized

    @property
    def odds_canonical_spreads_h1(self) -> PurePosixPath:
        return self.odds_normalized

    @property
    def odds_canonical_totals_fg(self) -> PurePosixPath:
        return self.odds_normalized

    @property
    def odds_canonical_totals_h1(self) -> PurePosixPath:
        return self.odds_normalized

    # ---- Ratings ----
    @property
    def ratings_raw_barttorvik(self) -> PurePosixPath:
        return self.root / "ratings" / "raw" / "barttorvik"

    # ---- Backtest datasets ----
    @property
    def backtest_datasets(self) -> PurePosixPath:
        return self.root / "backtest_datasets"

    # ---- Team aliases (CRITICAL for canonicalization) ----
    @property
    def team_aliases_db(self) -> PurePosixPath:
        return self.root / "backtest_datasets" / "team_aliases_db.json"

    # ---- Data manifest (checksums for integrity) ----
    @property
    def data_manifest(self) -> PurePosixPath:
        return self.root / "DATA_MANIFEST.json"

    # ---- Master odds file ----
    @property
    def odds_consolidated(self) -> PurePosixPath:
        return self.root / "odds" / "normalized" / "odds_consolidated_canonical.csv"

    # ---- Barttorvik ratings ----
    @property
    def barttorvik_ratings(self) -> PurePosixPath:
        return self.root / "backtest_datasets" / "barttorvik_ratings.csv"


# Azure configuration - SINGLE SOURCE OF TRUTH
AZURE_STORAGE_ACCOUNT = "metricstrackersgbsv"
AZURE_CANONICAL_CONTAINER = "ncaam-historical-data"
AZURE_RAW_CONTAINER = "ncaam-historical-raw"

DATA_PATHS = DataPaths()

# Global reader instance
_data_reader: AzureDataReader | None = None


def get_data_reader() -> AzureDataReader:
    """Get the Azure data reader (single source of truth)."""
    global _data_reader

    # Lazy import to avoid import errors if azure not installed
    from testing.azure_data_reader import AzureDataReader

    if _data_reader is None:
        _data_reader = AzureDataReader(container_name=AZURE_CANONICAL_CONTAINER)

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
