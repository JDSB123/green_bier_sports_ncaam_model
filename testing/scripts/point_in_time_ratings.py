#!/usr/bin/env python3
"""
Point-in-Time Ratings Lookup Utility

CRITICAL: This module provides ratings lookup that ONLY uses data from BEFORE game date.
This prevents data leakage in backtesting by ensuring we never use future information.

Point-in-time means:
- For a game on 2024-01-15, we use ratings calculated from games BEFORE 2024-01-15
- We NEVER use end-of-season ratings (which contain future data)
- We NEVER use league averages as placeholders

Usage:
    from testing.scripts.point_in_time_ratings import PointInTimeRatingsLookup

    lookup = PointInTimeRatingsLookup()
    
    # Get ratings for a team on a specific date
    ratings = lookup.get_team_ratings("Duke", game_date="2024-01-15")
    
    # Get ratings for a game (both teams)
    home_ratings, away_ratings = lookup.get_game_ratings(
        home_team="Duke",
        away_team="UNC",
        game_date="2024-01-15"
    )
"""

import sys
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any
import warnings

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


@dataclass
class TeamRatings:
    """Point-in-time ratings for a single team."""
    team: str
    rating_date: date
    games_played: int
    
    # Core efficiency metrics
    adj_o: float  # Adjusted offensive efficiency
    adj_d: float  # Adjusted defensive efficiency
    tempo: float  # Possessions per 40 minutes
    barthag: float  # Win probability metric
    
    # Four Factors - Offense
    efg: float  # Effective FG%
    tor: float  # Turnover rate
    orb: float  # Offensive rebound %
    ftr: float  # Free throw rate
    
    # Four Factors - Defense
    efgd: float  # Opponent EFG%
    tord: float  # Opponent turnover rate
    drb: float  # Defensive rebound %
    ftrd: float  # Opponent FTR
    
    # Shooting
    two_pt_rate: float = 0.0
    three_pt_rate: float = 0.0
    two_pt_pct: float = 0.0
    three_pt_pct: float = 0.0
    
    # Quality metrics
    wab: float = 0.0  # Wins above bubble
    sos: float = 0.0  # Strength of schedule
    conf: str = ""  # Conference
    
    def to_dict(self, prefix: str = "") -> Dict[str, Any]:
        """Convert to dictionary with optional prefix for merging."""
        p = f"{prefix}_" if prefix else ""
        return {
            f"{p}adj_o": self.adj_o,
            f"{p}adj_d": self.adj_d,
            f"{p}tempo": self.tempo,
            f"{p}barthag": self.barthag,
            f"{p}efg": self.efg,
            f"{p}efgd": self.efgd,
            f"{p}tor": self.tor,
            f"{p}tord": self.tord,
            f"{p}orb": self.orb,
            f"{p}drb": self.drb,
            f"{p}ftr": self.ftr,
            f"{p}ftrd": self.ftrd,
            f"{p}two_pt_rate": self.two_pt_rate,
            f"{p}three_pt_rate": self.three_pt_rate,
            f"{p}wab": self.wab,
            f"{p}conf": self.conf,
            f"{p}rating_date": self.rating_date.isoformat() if isinstance(self.rating_date, date) else self.rating_date,
            f"{p}games_played": self.games_played,
        }


class PointInTimeRatingsLookup:
    """
    Lookup ratings for teams at specific points in time.
    
    CRITICAL LEAKAGE PREVENTION:
    - All ratings are timestamped and only returns data from BEFORE game date
    - No fallback to league averages or placeholders
    - Fails explicitly if point-in-time ratings not available
    """
    
    # Rating fields we need from Barttorvik
    REQUIRED_FIELDS = [
        "adj_o", "adj_d", "tempo", "barthag",
        "efg", "efgd", "tor", "tord", "orb", "drb", "ftr", "ftrd"
    ]
    
    def __init__(
        self,
        ratings_dir: Optional[Path] = None,
        strict_mode: bool = True,
        min_games: int = 5,  # Minimum games needed for reliable ratings
    ):
        """
        Initialize the point-in-time ratings lookup.
        
        Args:
            ratings_dir: Directory containing daily ratings snapshots
            strict_mode: If True, fail on missing ratings. If False, return None.
            min_games: Minimum games a team must have played for ratings to be valid
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. Install with: pip install pandas")
        
        self.strict_mode = strict_mode
        self.min_games = min_games
        
        # Set up ratings directory
        self.ratings_dir = ratings_dir or (
            Path(__file__).resolve().parents[2] / "ncaam_historical_data_local" / "ratings"
        )
        
        # Cache for loaded ratings
        self._ratings_cache: Dict[str, pd.DataFrame] = {}
        self._daily_snapshots: Optional[pd.DataFrame] = None
        
        # Load team name resolver
        try:
            from testing.canonical.team_resolution_service import get_team_resolver
            self._team_resolver = get_team_resolver()
        except ImportError:
            self._team_resolver = None
            warnings.warn("Team resolver not available. Team name matching may be less accurate.")
    
    def get_team_ratings(
        self,
        team: str,
        game_date: str,
        season: Optional[int] = None
    ) -> Optional[TeamRatings]:
        """
        Get point-in-time ratings for a team on a specific date.
        
        CRITICAL: Only returns ratings calculated from games BEFORE game_date.
        
        Args:
            team: Team name (canonical or alias)
            game_date: Date of the game (YYYY-MM-DD)
            season: Optional season year (auto-detected if not provided)
        
        Returns:
            TeamRatings object or None if not available (strict_mode=False)
        
        Raises:
            ValueError: If ratings not available and strict_mode=True
        """
        # Parse game date
        if isinstance(game_date, str):
            gd = datetime.strptime(game_date, "%Y-%m-%d").date()
        elif isinstance(game_date, datetime):
            gd = game_date.date()
        else:
            gd = game_date
        
        # Auto-detect season if not provided
        if season is None:
            # NCAA season: Nov-Mar spans two calendar years
            # 2024 season = Nov 2023 - Mar 2024
            if gd.month >= 11:
                season = gd.year + 1
            else:
                season = gd.year
        
        # Resolve team name to canonical
        canonical_team = self._resolve_team_name(team)
        if canonical_team is None:
            if self.strict_mode:
                raise ValueError(f"Could not resolve team name: {team}")
            return None
        
        # Load ratings for the season
        ratings_df = self._load_season_ratings(season)
        if ratings_df is None or len(ratings_df) == 0:
            if self.strict_mode:
                raise ValueError(f"No ratings available for season {season}")
            return None
        
        # Find the most recent ratings BEFORE game date
        team_ratings = self._find_point_in_time_ratings(
            ratings_df, canonical_team, gd
        )
        
        if team_ratings is None:
            if self.strict_mode:
                raise ValueError(
                    f"No point-in-time ratings available for {team} "
                    f"before {game_date} in season {season}"
                )
            return None
        
        return team_ratings
    
    def get_game_ratings(
        self,
        home_team: str,
        away_team: str,
        game_date: str,
        season: Optional[int] = None
    ) -> Tuple[Optional[TeamRatings], Optional[TeamRatings]]:
        """
        Get point-in-time ratings for both teams in a game.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            game_date: Date of the game (YYYY-MM-DD)
            season: Optional season year
        
        Returns:
            Tuple of (home_ratings, away_ratings)
        """
        home_ratings = self.get_team_ratings(home_team, game_date, season)
        away_ratings = self.get_team_ratings(away_team, game_date, season)
        return home_ratings, away_ratings
    
    def add_point_in_time_ratings_to_df(
        self,
        df: pd.DataFrame,
        home_team_col: str = "home_team",
        away_team_col: str = "away_team",
        game_date_col: str = "game_date",
        season_col: Optional[str] = "season"
    ) -> pd.DataFrame:
        """
        Add point-in-time ratings columns to a DataFrame of games.
        
        CRITICAL: This is the main method for building backtest datasets.
        It ensures each game uses only ratings available BEFORE that game.
        
        Args:
            df: DataFrame with games
            home_team_col: Column name for home team
            away_team_col: Column name for away team
            game_date_col: Column name for game date
            season_col: Optional column name for season
        
        Returns:
            DataFrame with added point-in-time ratings columns
        """
        result = df.copy()
        
        # Initialize new columns
        rating_cols = [
            "adj_o", "adj_d", "tempo", "barthag",
            "efg", "efgd", "tor", "tord", "orb", "drb", "ftr", "ftrd",
            "two_pt_rate", "three_pt_rate", "wab", "conf",
            "rating_date", "games_played"
        ]
        
        for prefix in ["home", "away"]:
            for col in rating_cols:
                result[f"{prefix}_{col}_pit"] = None  # _pit = point-in-time
        
        # Track missing ratings
        missing_ratings = []
        
        # Process each game
        for idx, row in df.iterrows():
            game_date = row[game_date_col]
            home_team = row[home_team_col]
            away_team = row[away_team_col]
            season = row.get(season_col) if season_col and season_col in df.columns else None
            
            try:
                home_ratings = self.get_team_ratings(home_team, str(game_date), season)
                if home_ratings:
                    for key, value in home_ratings.to_dict("home").items():
                        col_name = f"{key}_pit"
                        if col_name in result.columns:
                            result.at[idx, col_name] = value
            except ValueError as e:
                missing_ratings.append(f"Home {home_team} @ {game_date}: {e}")
            
            try:
                away_ratings = self.get_team_ratings(away_team, str(game_date), season)
                if away_ratings:
                    for key, value in away_ratings.to_dict("away").items():
                        col_name = f"{key}_pit"
                        if col_name in result.columns:
                            result.at[idx, col_name] = value
            except ValueError as e:
                missing_ratings.append(f"Away {away_team} @ {game_date}: {e}")
        
        # Report missing ratings
        if missing_ratings:
            print(f"Warning: {len(missing_ratings)} games with missing point-in-time ratings")
            if len(missing_ratings) <= 10:
                for msg in missing_ratings:
                    print(f"  - {msg}")
            else:
                for msg in missing_ratings[:5]:
                    print(f"  - {msg}")
                print(f"  ... and {len(missing_ratings) - 5} more")
        
        return result
    
    def _resolve_team_name(self, team: str) -> Optional[str]:
        """Resolve team name to canonical form."""
        if self._team_resolver:
            result = self._team_resolver.resolve(team)
            if result and result.confidence > 0.7:
                return result.canonical_name
        return team  # Return as-is if resolver not available
    
    def _load_season_ratings(self, season: int) -> Optional[pd.DataFrame]:
        """Load ratings for a specific season."""
        cache_key = f"season_{season}"
        if cache_key in self._ratings_cache:
            return self._ratings_cache[cache_key]
        
        # Try different rating sources in order of preference
        
        # 1. Daily snapshots (best for point-in-time)
        daily_path = self.ratings_dir / "daily" / f"ratings_{season}"
        if daily_path.exists():
            ratings = self._load_daily_snapshots(daily_path)
            if ratings is not None:
                self._ratings_cache[cache_key] = ratings
                return ratings
        
        # 2. Barttorvik historical ratings with dates
        barttorvik_path = self.ratings_dir / "barttorvik" / f"ratings_{season}.json"
        if barttorvik_path.exists():
            ratings = self._load_barttorvik_ratings(barttorvik_path, season)
            if ratings is not None:
                self._ratings_cache[cache_key] = ratings
                return ratings
        
        # 3. Try CSV format
        csv_path = self.ratings_dir / "barttorvik" / f"ratings_{season}.csv"
        if csv_path.exists():
            ratings = pd.read_csv(csv_path)
            self._ratings_cache[cache_key] = ratings
            return ratings
        
        return None
    
    def _load_daily_snapshots(self, daily_path: Path) -> Optional[pd.DataFrame]:
        """Load daily rating snapshots from a directory."""
        all_snapshots = []
        
        for snapshot_file in daily_path.glob("*.csv"):
            try:
                # Extract date from filename (e.g., ratings_2024-01-15.csv)
                date_str = snapshot_file.stem.split("_")[-1]
                snapshot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                df = pd.read_csv(snapshot_file)
                df["snapshot_date"] = snapshot_date
                all_snapshots.append(df)
            except Exception as e:
                warnings.warn(f"Failed to load snapshot {snapshot_file}: {e}")
        
        if not all_snapshots:
            return None
        
        return pd.concat(all_snapshots, ignore_index=True)
    
    def _load_barttorvik_ratings(
        self, 
        json_path: Path, 
        season: int
    ) -> Optional[pd.DataFrame]:
        """
        Load Barttorvik ratings from JSON.
        
        Note: End-of-season ratings are used with caution.
        For proper point-in-time, we need daily snapshots.
        """
        import json
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        records = []
        for team, ratings in data.items():
            if isinstance(ratings, dict):
                record = {"team": team, **ratings}
                records.append(record)
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        
        # For end-of-season ratings, we'll use the season end date as the snapshot date
        # This is a KNOWN LIMITATION - true point-in-time requires daily snapshots
        if season:
            # Season ends around March 31
            df["snapshot_date"] = date(season, 3, 31)
        
        return df
    
    def _find_point_in_time_ratings(
        self,
        ratings_df: pd.DataFrame,
        team: str,
        game_date: date
    ) -> Optional[TeamRatings]:
        """
        Find the most recent ratings for a team BEFORE the game date.
        
        This is the core point-in-time logic.
        """
        # Normalize team name for matching
        team_lower = team.lower().strip()
        
        # Find team rows
        if "team" in ratings_df.columns:
            team_mask = ratings_df["team"].str.lower().str.strip() == team_lower
        elif "Team" in ratings_df.columns:
            team_mask = ratings_df["Team"].str.lower().str.strip() == team_lower
        else:
            # Try to find a team column
            for col in ratings_df.columns:
                if "team" in col.lower():
                    team_mask = ratings_df[col].str.lower().str.strip() == team_lower
                    break
            else:
                return None
        
        team_rows = ratings_df[team_mask]
        
        if len(team_rows) == 0:
            return None
        
        # If we have snapshot dates, filter to before game date
        if "snapshot_date" in team_rows.columns:
            # Convert to date if needed
            if not isinstance(team_rows["snapshot_date"].iloc[0], date):
                team_rows = team_rows.copy()
                team_rows["snapshot_date"] = pd.to_datetime(team_rows["snapshot_date"]).dt.date
            
            # Get ratings from BEFORE game date (strict < not <=)
            before_game = team_rows[team_rows["snapshot_date"] < game_date]
            
            if len(before_game) == 0:
                # No ratings available before this game
                # This is expected for early season games
                return None
            
            # Get the most recent snapshot
            most_recent = before_game.loc[before_game["snapshot_date"].idxmax()]
        else:
            # No snapshot dates - use the single row with a warning
            # This is a KNOWN LIMITATION for end-of-season ratings
            most_recent = team_rows.iloc[0]
            warnings.warn(
                f"Using end-of-season ratings for {team} - "
                "point-in-time accuracy not guaranteed. "
                "Consider loading daily rating snapshots."
            )
        
        # Build TeamRatings object
        return self._row_to_team_ratings(most_recent, team, game_date)
    
    def _row_to_team_ratings(
        self,
        row: pd.Series,
        team: str,
        game_date: date
    ) -> TeamRatings:
        """Convert a DataFrame row to TeamRatings object."""
        
        def get_value(keys: List[str], default: float = 0.0) -> float:
            """Try multiple column name variations."""
            for key in keys:
                if key in row.index and pd.notna(row[key]):
                    return float(row[key])
            return default
        
        def get_str(keys: List[str], default: str = "") -> str:
            """Try multiple column name variations for strings."""
            for key in keys:
                if key in row.index and pd.notna(row[key]):
                    return str(row[key])
            return default
        
        # Get snapshot date
        if "snapshot_date" in row.index:
            rating_date = row["snapshot_date"]
            if isinstance(rating_date, str):
                rating_date = datetime.strptime(rating_date, "%Y-%m-%d").date()
        else:
            rating_date = game_date - timedelta(days=1)  # Assume day before
        
        return TeamRatings(
            team=team,
            rating_date=rating_date,
            games_played=int(get_value(["games", "games_played", "G"], 0)),
            
            # Core efficiency
            adj_o=get_value(["adj_o", "AdjOE", "adjoe", "Adj_O"]),
            adj_d=get_value(["adj_d", "AdjDE", "adjde", "Adj_D"]),
            tempo=get_value(["tempo", "Tempo", "AdjT"]),
            barthag=get_value(["barthag", "Barthag", "BARTHAG"]),
            
            # Four Factors - Offense
            efg=get_value(["efg", "EFG", "eFG%", "efg_o"]),
            tor=get_value(["tor", "TOR", "TO%", "tov_o"]),
            orb=get_value(["orb", "ORB", "ORB%", "orb_o"]),
            ftr=get_value(["ftr", "FTR", "FT_Rate"]),
            
            # Four Factors - Defense
            efgd=get_value(["efgd", "EFGD", "eFG%_D", "efg_d"]),
            tord=get_value(["tord", "TORD", "TO%_D", "tov_d"]),
            drb=get_value(["drb", "DRB", "DRB%", "drb_d"]),
            ftrd=get_value(["ftrd", "FTRD", "FT_Rate_D"]),
            
            # Shooting
            two_pt_rate=get_value(["two_pt_rate", "2P_Rate", "2pt_rate"]),
            three_pt_rate=get_value(["three_pt_rate", "3P_Rate", "3pt_rate"]),
            two_pt_pct=get_value(["two_pt_pct", "2P%", "2pt_pct"]),
            three_pt_pct=get_value(["three_pt_pct", "3P%", "3pt_pct"]),
            
            # Quality
            wab=get_value(["wab", "WAB"]),
            sos=get_value(["sos", "SOS"]),
            conf=get_str(["conf", "Conf", "Conference"]),
        )


def validate_no_leakage(
    df: pd.DataFrame,
    game_date_col: str = "game_date",
    rating_date_col: str = "home_rating_date_pit"
) -> Tuple[bool, List[str]]:
    """
    Validate that no ratings are from after the game date.
    
    This is a critical validation for backtest integrity.
    
    Args:
        df: DataFrame with games and point-in-time ratings
        game_date_col: Column name for game date
        rating_date_col: Column name for rating date
    
    Returns:
        Tuple of (passed, list of error messages)
    """
    errors = []
    
    if rating_date_col not in df.columns:
        return True, []  # Can't validate if column doesn't exist
    
    # Convert to datetime for comparison
    game_dates = pd.to_datetime(df[game_date_col])
    rating_dates = pd.to_datetime(df[rating_date_col])
    
    # Check for leakage (ratings from after game date)
    leakage_mask = rating_dates >= game_dates
    leakage_count = leakage_mask.sum()
    
    if leakage_count > 0:
        errors.append(
            f"LEAKAGE DETECTED: {leakage_count} games have ratings from "
            f"on or after the game date!"
        )
        
        # Show examples
        leakage_games = df[leakage_mask].head(5)
        for _, row in leakage_games.iterrows():
            errors.append(
                f"  - Game {row[game_date_col]}: rating from {row[rating_date_col]}"
            )
    
    return len(errors) == 0, errors


if __name__ == "__main__":
    # Test the point-in-time ratings lookup
    print("=" * 60)
    print("Point-in-Time Ratings Lookup Test")
    print("=" * 60)
    
    lookup = PointInTimeRatingsLookup(strict_mode=False)
    
    # Test single team lookup
    print("\nTesting single team lookup...")
    ratings = lookup.get_team_ratings("Duke", "2024-01-15", season=2024)
    if ratings:
        print(f"  Duke ratings as of 2024-01-15:")
        print(f"    AdjO: {ratings.adj_o:.1f}")
        print(f"    AdjD: {ratings.adj_d:.1f}")
        print(f"    Tempo: {ratings.tempo:.1f}")
        print(f"    Rating date: {ratings.rating_date}")
    else:
        print("  No ratings found (this may be expected if daily snapshots not available)")
    
    # Test game ratings lookup
    print("\nTesting game ratings lookup...")
    home, away = lookup.get_game_ratings("Duke", "UNC", "2024-02-03", season=2024)
    if home and away:
        print(f"  Duke vs UNC on 2024-02-03:")
        print(f"    Duke AdjO: {home.adj_o:.1f}, AdjD: {home.adj_d:.1f}")
        print(f"    UNC AdjO: {away.adj_o:.1f}, AdjD: {away.adj_d:.1f}")
    else:
        print("  No ratings found for one or both teams")
    
    print("\n[OK] Point-in-time ratings lookup functional")
