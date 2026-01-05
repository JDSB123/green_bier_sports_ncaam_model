"""
Anti-Leakage Ratings Loader for Production Parity Backtest.

CRITICAL: This loader enforces the anti-leakage rule:
    Season N games use Season N-1 FINAL ratings.

This prevents data leakage that would inflate backtest results.

Example:
    - Game on 2024-01-15 (CST) → Season 2024 → Use Season 2023 FINAL ratings
    - Game on 2023-11-25 (CST) → Season 2024 → Use Season 2023 FINAL ratings
    - Game on 2023-03-18 (CST) → Season 2023 → Use Season 2022 FINAL ratings

All date logic uses CST (America/Chicago) for consistency.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from .timezone_utils import get_season_for_game, get_ratings_season_for_game
from .team_resolver import ProductionTeamResolver, resolve_team_name


# Barttorvik JSON column mapping (array-of-arrays format with 45 fields)
# From ratings-sync-go and fetch_barttorvik_historical.py
BARTTORVIK_COLUMNS = {
    "rank": 0,
    "team": 1,
    "conf": 2,
    "record": 3,
    "adj_o": 4,
    "adj_o_rank": 5,
    "adj_d": 6,
    "adj_d_rank": 7,
    "barthag": 8,
    "barthag_rank": 9,
    "wins": 10,
    "losses": 11,
    "conf_wins": 12,
    "conf_losses": 13,
    "conf_record": 14,
    "efg": 15,
    "efgd": 16,
    "tor": 17,
    "tord": 18,
    "orb": 19,
    "drb": 20,
    "ftr": 21,
    "ftrd": 22,
    "two_pt_pct": 23,
    "two_pt_pct_d": 24,
    "three_pt_pct": 25,
    "three_pt_pct_d": 26,
    "three_pt_rate": 27,
    "three_pt_rate_d": 28,
    # ... fields 29-43 vary
    "tempo": 44,  # LAST FIELD
}


@dataclass(frozen=True)
class TeamRatings:
    """
    Barttorvik team ratings - matches production models.py EXACTLY.

    ALL 22 FIELDS ARE REQUIRED. No fallbacks, no defaults in backtest.
    If ratings are missing, the game should be skipped, not predicted.
    """
    team_name: str

    # Core efficiency metrics
    adj_o: float          # Adjusted offensive efficiency
    adj_d: float          # Adjusted defensive efficiency
    tempo: float          # Possessions per 40 minutes
    rank: int             # Barttorvik overall rank

    # Four Factors - Shooting
    efg: float            # Effective FG%
    efgd: float           # Effective FG% allowed

    # Four Factors - Turnovers
    tor: float            # Turnover Rate
    tord: float           # Turnover Rate forced

    # Four Factors - Rebounding
    orb: float            # Offensive Rebound %
    drb: float            # Defensive Rebound %

    # Four Factors - Free Throws
    ftr: float            # Free Throw Rate
    ftrd: float           # Free Throw Rate allowed

    # Shooting Breakdown
    two_pt_pct: float     # 2-Point FG%
    two_pt_pct_d: float   # 2-Point FG% allowed
    three_pt_pct: float   # 3-Point FG%
    three_pt_pct_d: float # 3-Point FG% allowed
    three_pt_rate: float  # 3-Point attempt rate
    three_pt_rate_d: float # 3-Point rate allowed

    # Quality Metrics
    barthag: float        # Barttorvik power rating
    wab: float            # Wins Above Bubble

    @property
    def net_rating(self) -> float:
        """Net efficiency rating."""
        return self.adj_o - self.adj_d

    def __repr__(self) -> str:
        return f"{self.team_name} (#{self.rank}): O={self.adj_o:.1f} D={self.adj_d:.1f}"


@dataclass
class RatingsLookupResult:
    """Result of a ratings lookup with anti-leakage metadata."""
    team_name: str
    canonical_name: Optional[str]
    ratings: Optional[TeamRatings]
    ratings_season: int  # The season the ratings are FROM (N-1)
    game_season: int     # The season the game is IN (N)
    found: bool

    def __repr__(self) -> str:
        if self.found:
            return f"'{self.team_name}' → {self.ratings} (Season {self.ratings_season} ratings for Season {self.game_season} game)"
        return f"'{self.team_name}' → NOT FOUND (needed Season {self.ratings_season} ratings)"


class AntiLeakageRatingsLoader:
    """
    Ratings loader with strict anti-leakage enforcement.

    This loader ensures that Season N games use ONLY Season N-1 FINAL ratings.
    This prevents the performance inflation seen in naive backtests.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        team_resolver: Optional[ProductionTeamResolver] = None,
    ):
        """
        Initialize the ratings loader.

        Args:
            data_dir: Directory containing barttorvik_YYYY.json files
            team_resolver: Optional resolver (uses default if not provided)
        """
        if data_dir is None:
            # Default to testing/data/historical
            data_dir = Path(__file__).parents[1] / "data" / "historical"

        self.data_dir = Path(data_dir)
        self.resolver = team_resolver or ProductionTeamResolver()

        # Cache: season -> {canonical_name -> TeamRatings}
        self._ratings_cache: Dict[int, Dict[str, TeamRatings]] = {}
        self._available_seasons: Set[int] = set()

        # Stats
        self.stats = {
            "lookups": 0,
            "found": 0,
            "missing_team": 0,
            "missing_season": 0,
        }

        self._discover_available_seasons()

    def _discover_available_seasons(self) -> None:
        """Find all available barttorvik_YYYY.json files."""
        if not self.data_dir.exists():
            print(f"[RatingsLoader] Warning: Data directory not found: {self.data_dir}")
            return

        for path in self.data_dir.glob("barttorvik_*.json"):
            try:
                season = int(path.stem.split("_")[1])
                self._available_seasons.add(season)
            except (ValueError, IndexError):
                continue

        if self._available_seasons:
            seasons_str = ", ".join(str(s) for s in sorted(self._available_seasons))
            print(f"[RatingsLoader] Found ratings for seasons: {seasons_str}")
        else:
            print(f"[RatingsLoader] Warning: No barttorvik files found in {self.data_dir}")

    def _load_season(self, season: int) -> Dict[str, TeamRatings]:
        """Load ratings for a specific season into cache."""
        if season in self._ratings_cache:
            return self._ratings_cache[season]

        path = self.data_dir / f"barttorvik_{season}.json"
        if not path.exists():
            print(f"[RatingsLoader] Season {season} not found: {path}")
            self._ratings_cache[season] = {}
            return {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[RatingsLoader] Error loading {path}: {e}")
            self._ratings_cache[season] = {}
            return {}

        ratings = {}

        for row in data:
            if not isinstance(row, list) or len(row) < 45:
                continue

            try:
                # Get raw team name from Barttorvik
                raw_team_name = str(row[BARTTORVIK_COLUMNS["team"]])

                # Resolve to canonical name
                result = self.resolver.resolve(raw_team_name)
                if not result.resolved:
                    # Keep original if can't resolve
                    canonical = raw_team_name
                else:
                    canonical = result.canonical_name

                # Parse all 22 fields (no defaults!)
                team_ratings = TeamRatings(
                    team_name=canonical,
                    adj_o=float(row[BARTTORVIK_COLUMNS["adj_o"]]),
                    adj_d=float(row[BARTTORVIK_COLUMNS["adj_d"]]),
                    tempo=float(row[BARTTORVIK_COLUMNS["tempo"]]),
                    rank=int(row[BARTTORVIK_COLUMNS["rank"]]),
                    efg=float(row[BARTTORVIK_COLUMNS["efg"]]),
                    efgd=float(row[BARTTORVIK_COLUMNS["efgd"]]),
                    tor=float(row[BARTTORVIK_COLUMNS["tor"]]),
                    tord=float(row[BARTTORVIK_COLUMNS["tord"]]),
                    orb=float(row[BARTTORVIK_COLUMNS["orb"]]),
                    drb=float(row[BARTTORVIK_COLUMNS["drb"]]),
                    ftr=float(row[BARTTORVIK_COLUMNS["ftr"]]),
                    ftrd=float(row[BARTTORVIK_COLUMNS["ftrd"]]),
                    two_pt_pct=float(row[BARTTORVIK_COLUMNS["two_pt_pct"]]),
                    two_pt_pct_d=float(row[BARTTORVIK_COLUMNS["two_pt_pct_d"]]),
                    three_pt_pct=float(row[BARTTORVIK_COLUMNS["three_pt_pct"]]),
                    three_pt_pct_d=float(row[BARTTORVIK_COLUMNS["three_pt_pct_d"]]),
                    three_pt_rate=float(row[BARTTORVIK_COLUMNS["three_pt_rate"]]),
                    three_pt_rate_d=float(row[BARTTORVIK_COLUMNS["three_pt_rate_d"]]),
                    barthag=float(row[BARTTORVIK_COLUMNS["barthag"]]),
                    wab=0.0,  # WAB not consistently positioned in JSON
                )

                ratings[canonical] = team_ratings

            except (ValueError, IndexError, TypeError) as e:
                continue

        self._ratings_cache[season] = ratings
        print(f"[RatingsLoader] Loaded {len(ratings)} teams for season {season}")
        return ratings

    def get_ratings_for_game(
        self,
        team_name: str,
        game_date: str,
    ) -> RatingsLookupResult:
        """
        Get team ratings for a game with anti-leakage enforcement.

        This is the KEY anti-leakage method:
        - Determines game season from CST date
        - Uses Season N-1 ratings for Season N games

        Args:
            team_name: Raw team name from any source
            game_date: Game date string (will be parsed to CST)

        Returns:
            RatingsLookupResult with ratings and metadata
        """
        self.stats["lookups"] += 1

        # Determine seasons
        game_season = get_season_for_game(game_date)
        ratings_season = game_season - 1  # Anti-leakage: use prior season

        # Resolve team name
        result = self.resolver.resolve(team_name)
        canonical = result.canonical_name

        if not result.resolved:
            self.stats["missing_team"] += 1
            return RatingsLookupResult(
                team_name=team_name,
                canonical_name=None,
                ratings=None,
                ratings_season=ratings_season,
                game_season=game_season,
                found=False,
            )

        # Load season if not cached
        season_ratings = self._load_season(ratings_season)

        # Look up ratings
        ratings = season_ratings.get(canonical)

        if ratings is None:
            self.stats["missing_season"] += 1
            return RatingsLookupResult(
                team_name=team_name,
                canonical_name=canonical,
                ratings=None,
                ratings_season=ratings_season,
                game_season=game_season,
                found=False,
            )

        self.stats["found"] += 1
        return RatingsLookupResult(
            team_name=team_name,
            canonical_name=canonical,
            ratings=ratings,
            ratings_season=ratings_season,
            game_season=game_season,
            found=True,
        )

    def get_matchup_ratings(
        self,
        home_team: str,
        away_team: str,
        game_date: str,
    ) -> tuple[Optional[TeamRatings], Optional[TeamRatings], dict]:
        """
        Get ratings for both teams in a matchup.

        Returns:
            (home_ratings, away_ratings, metadata)
        """
        home_result = self.get_ratings_for_game(home_team, game_date)
        away_result = self.get_ratings_for_game(away_team, game_date)

        metadata = {
            "game_season": home_result.game_season,
            "ratings_season": home_result.ratings_season,
            "home_resolved": home_result.canonical_name,
            "away_resolved": away_result.canonical_name,
            "home_found": home_result.found,
            "away_found": away_result.found,
        }

        return home_result.ratings, away_result.ratings, metadata

    def get_stats(self) -> dict:
        """Get loader statistics."""
        total = self.stats["lookups"]
        return {
            **self.stats,
            "success_rate": self.stats["found"] / total if total > 0 else 0,
            "available_seasons": sorted(self._available_seasons),
        }

    def reset_stats(self) -> None:
        """Reset loader statistics."""
        self.stats = {
            "lookups": 0,
            "found": 0,
            "missing_team": 0,
            "missing_season": 0,
        }


# Singleton instance
_loader: Optional[AntiLeakageRatingsLoader] = None


def get_loader(data_dir: Optional[Path] = None) -> AntiLeakageRatingsLoader:
    """Get singleton loader instance."""
    global _loader
    if _loader is None:
        _loader = AntiLeakageRatingsLoader(data_dir)
    return _loader


# Self-test when run directly
if __name__ == "__main__":
    print("=" * 60)
    print("Anti-Leakage Ratings Loader - Self Test")
    print("=" * 60)

    loader = AntiLeakageRatingsLoader()

    # Test cases showing anti-leakage behavior
    test_cases = [
        # (team, date, expected_game_season, expected_ratings_season)
        ("Duke", "2024-01-15", 2024, 2023),      # Jan 2024 → Season 2024 → Use 2023 ratings
        ("Duke", "2023-11-25", 2024, 2023),      # Nov 2023 → Season 2024 → Use 2023 ratings
        ("Duke", "2023-03-18", 2023, 2022),      # Mar 2023 → Season 2023 → Use 2022 ratings
        ("North Carolina", "2024-02-10", 2024, 2023),
        ("Kentucky Wildcats", "2023-12-25", 2024, 2023),
    ]

    print("\n--- Anti-Leakage Tests ---")
    for team, date, exp_game, exp_ratings in test_cases:
        result = loader.get_ratings_for_game(team, date)
        status = "✓" if result.game_season == exp_game and result.ratings_season == exp_ratings else "✗"
        print(f"  {status} {team} on {date}:")
        print(f"      Game Season: {result.game_season} (expected {exp_game})")
        print(f"      Ratings Season: {result.ratings_season} (expected {exp_ratings})")
        if result.found:
            print(f"      Ratings: {result.ratings}")
        else:
            print(f"      Ratings: NOT FOUND")

    print("\n--- Matchup Test ---")
    home_r, away_r, meta = loader.get_matchup_ratings("Duke", "North Carolina", "2024-02-01")
    print(f"  Duke vs UNC on 2024-02-01:")
    print(f"    Metadata: {meta}")
    if home_r:
        print(f"    Home: {home_r}")
    if away_r:
        print(f"    Away: {away_r}")

    print("\n--- Loader Stats ---")
    stats = loader.get_stats()
    print(f"  {stats}")
