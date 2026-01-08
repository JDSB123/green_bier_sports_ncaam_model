"""
Central configuration for historical data paths.

All backtest and historical data lives in ncaam_historical_data_local/
which is a separate git repo (https://github.com/JDSB123/ncaam-historical-data).

Usage:
    from testing.data_paths import DATA_PATHS
    
    scores_file = DATA_PATHS.scores_fg / "games_all.csv"
    odds_file = DATA_PATHS.odds_normalized / "odds_consolidated_canonical.csv"
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
        
    @property
    def scores_fg(self) -> Path:
        """Full-game scores: games_YYYY.csv, games_all.csv"""
        return self.root / "scores" / "fg"
    
    @property
    def scores_h1(self) -> Path:
        """First-half scores: h1_games_all.csv"""
        return self.root / "scores" / "h1"
    
    @property
    def odds_raw(self) -> Path:
        """Raw odds files from The Odds API"""
        return self.root / "odds"
    
    @property
    def odds_normalized(self) -> Path:
        """Normalized/consolidated odds files"""
        return self.root / "odds" / "normalized"
    
    @property
    def ratings(self) -> Path:
        """Barttorvik ratings: barttorvik_YYYY.json"""
        return self.root / "ratings" / "barttorvik"
    
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
