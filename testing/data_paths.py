"""
Central configuration for historical data paths.

All backtest and historical data lives in ncaam_historical_data_local/
which is a separate git repo (https://github.com/JDSB123/ncaam-historical-data).

Data Flow:
    RAW → CANONICAL (after team name QA/QC)
    
    odds/raw/archive/       - Original API pulls (pre-canonicalization)
    odds/canonical/         - Post-QA with resolved team names
    ratings/raw/            - Original ratings (pre-canonicalization)
    ratings/canonical/      - Post-QA with resolved team names

Usage:
    from testing.data_paths import DATA_PATHS
    
    # For backtesting (use canonical data)
    spreads = DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv"
    
    # For raw data processing
    raw_files = DATA_PATHS.odds_raw_archive
"""

from pathlib import Path

# Root of the project
PROJECT_ROOT = Path(__file__).parent.parent

# Historical data repo location (git submodule or cloned repo)
HISTORICAL_DATA_ROOT = PROJECT_ROOT / "ncaam_historical_data_local"


class DataPaths:
    """Centralized paths to historical data."""
    
    def __init__(self, root: Path = HISTORICAL_DATA_ROOT):
        self.root = root
    
    # ─────────────────────────────────────────────────────────────
    # SCORES
    # ─────────────────────────────────────────────────────────────
    @property
    def scores_fg(self) -> Path:
        """Full-game scores: games_YYYY.csv, games_all.csv"""
        return self.root / "scores" / "fg"
    
    @property
    def scores_h1(self) -> Path:
        """First-half scores: h1_games_all.csv"""
        return self.root / "scores" / "h1"
    
    # ─────────────────────────────────────────────────────────────
    # ODDS - RAW (pre-canonicalization)
    # ─────────────────────────────────────────────────────────────
    @property
    def odds_raw_archive(self) -> Path:
        """Original API pulls (210+ files, pre-canonicalization)"""
        return self.root / "odds" / "raw" / "archive"
    
    @property
    def odds_raw_spreads_fg(self) -> Path:
        """Raw full-game spreads (pre-canonicalization)"""
        return self.root / "odds" / "raw" / "spreads" / "fg"
    
    @property
    def odds_raw_spreads_h1(self) -> Path:
        """Raw first-half spreads (pre-canonicalization)"""
        return self.root / "odds" / "raw" / "spreads" / "h1"
    
    @property
    def odds_raw_totals_fg(self) -> Path:
        """Raw full-game totals (pre-canonicalization)"""
        return self.root / "odds" / "raw" / "totals" / "fg"
    
    @property
    def odds_raw_totals_h1(self) -> Path:
        """Raw first-half totals (pre-canonicalization)"""
        return self.root / "odds" / "raw" / "totals" / "h1"
    
    # ─────────────────────────────────────────────────────────────
    # ODDS - CANONICAL (post-QA, team names resolved)
    # ─────────────────────────────────────────────────────────────
    @property
    def odds_canonical_spreads_fg(self) -> Path:
        """Canonical full-game spreads (post-QA)"""
        return self.root / "odds" / "canonical" / "spreads" / "fg"
    
    @property
    def odds_canonical_spreads_h1(self) -> Path:
        """Canonical first-half spreads (post-QA)"""
        return self.root / "odds" / "canonical" / "spreads" / "h1"
    
    @property
    def odds_canonical_totals_fg(self) -> Path:
        """Canonical full-game totals (post-QA)"""
        return self.root / "odds" / "canonical" / "totals" / "fg"
    
    @property
    def odds_canonical_totals_h1(self) -> Path:
        """Canonical first-half totals (post-QA)"""
        return self.root / "odds" / "canonical" / "totals" / "h1"
    
    @property
    def odds_normalized(self) -> Path:
        """Legacy: Normalized/consolidated odds files (deprecated)"""
        return self.root / "odds" / "normalized"
    
    # ─────────────────────────────────────────────────────────────
    # RATINGS
    # ─────────────────────────────────────────────────────────────
    @property
    def ratings_raw_barttorvik(self) -> Path:
        """Raw Barttorvik ratings: barttorvik_YYYY.json"""
        return self.root / "ratings" / "raw" / "barttorvik"
    
    @property
    def ratings_canonical(self) -> Path:
        """Canonical ratings (post-QA, team names resolved)"""
        return self.root / "ratings" / "canonical"
    
    @property
    def ratings(self) -> Path:
        """Alias for ratings_raw_barttorvik (backward compat)"""
        return self.ratings_raw_barttorvik
    
    # ─────────────────────────────────────────────────────────────
    # OTHER
    # ─────────────────────────────────────────────────────────────
    @property
    def backtest_datasets(self) -> Path:
        """Pre-built backtest datasets"""
        return self.root / "backtest_datasets"
    
    @property
    def team_resolution(self) -> Path:
        """Team name mapping files"""
        return self.root / "team_resolution"
    
    @property
    def schemas(self) -> Path:
        """Data schema definitions"""
        return self.root / "schemas"
    
    @property
    def ncaahoopr(self) -> Path:
        """ncaahoopR play-by-play data (large, ~7GB)"""
        return self.root / "ncaahoopR_data-master"
    
    def exists(self) -> bool:
        """Check if historical data repo is available."""
        return self.root.exists()
    
    def validate(self) -> dict:
        """Check which data directories exist."""
        return {
            "root": self.root.exists(),
            "scores_fg": self.scores_fg.exists(),
            "scores_h1": self.scores_h1.exists(),
            "odds_normalized": self.odds_normalized.exists(),
            "ratings": self.ratings.exists(),
            "backtest_datasets": self.backtest_datasets.exists(),
        }


# Default instance
DATA_PATHS = DataPaths()


# Legacy compatibility - map old paths to new
LEGACY_PATH_MAP = {
    "testing/data/historical": DATA_PATHS.scores_fg,
    "testing/data/historical_odds": DATA_PATHS.odds_normalized,
    "testing/data/h1_historical": DATA_PATHS.scores_h1,
}


if __name__ == "__main__":
    print("NCAAM Historical Data Paths")
    print("=" * 50)
    print(f"Root: {DATA_PATHS.root}")
    print(f"Exists: {DATA_PATHS.exists()}")
    print()
    print("Validation:")
    for key, exists in DATA_PATHS.validate().items():
        status = "✓" if exists else "✗"
        print(f"  {status} {key}")
