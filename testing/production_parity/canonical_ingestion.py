"""
Canonical Data Ingestion Framework

Standardizes all data sources (Odds API, ESPN, Barttorvik, ncaahoopR) through
a single canonicalization pipeline with:
- Consistent team name resolution (ProductionTeamResolver)
- Season-aware canonicalization (correct season assignment)
- Standardized output format for all sources
- Quick re-canonicalization for backtests

This enables:
1. Quick re-canonicalization during backtests (swap versions, test changes)
2. Game-level feature engineering from ncaahoopR
3. Rolling team stats without data leakage
4. Unified prediction interface across all markets

Usage:
    from testing.production_parity.canonical_ingestion import CanonicalDataIngestionPipeline
    
    pipeline = CanonicalDataIngestionPipeline()
    
    # Canonicalize any source
    canonical_games = pipeline.ingest_odds_api(raw_odds_df)
    canonical_games = pipeline.ingest_espn_scores(raw_scores_df)
    canonical_games = pipeline.ingest_barttorvik_ratings(raw_ratings_df)
    canonical_games = pipeline.ingest_ncaahoopR_games(raw_ncaahoopR_df)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, date
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import pandas as pd

from .team_resolver import ProductionTeamResolver, ResolutionResult
from .timezone_utils import parse_date_to_cst, get_season_for_game


class DataSourceType(str, Enum):
    """Data source identifier."""
    ODDS_API = "odds_api"
    ESPN_SCORES = "espn_scores"
    BARTTORVIK = "barttorvik"
    NCAAHOOPR = "ncaahoopR"
    MANUAL = "manual"


@dataclass(frozen=True)
class CanonicalTeam:
    """Canonical team representation."""
    name: str                          # Canonical name (e.g., "Duke", "North Carolina")
    resolution_step: str               # How it was resolved (CANONICAL, ALIAS, NORMALIZED, MASCOT_STRIPPED)
    source_name: str                   # Original name from source
    source: DataSourceType             # Which source provided this data


@dataclass(frozen=True)
class CanonicalGame:
    """
    Canonical game representation - single source of truth for game data.
    
    All ingestion sources convert to this format.
    """
    # Game identifiers
    game_id: str                       # Unique game ID (external_id from Odds API)
    game_date_cst: str                 # Game date in YYYY-MM-DD (CST converted)
    game_datetime_cst: str             # Game datetime in ISO format (CST)
    season: int                        # NCAA season (championship year)
    
    # Teams (canonical names)
    home_team_canonical: str           # Canonical name (e.g., "Duke")
    away_team_canonical: str           # Canonical name (e.g., "North Carolina")
    home_team_source: str              # Original name from source
    away_team_source: str              # Original name from source
    
    # Team resolution metadata
    home_resolution_step: str          # How home team was resolved
    away_resolution_step: str          # How away team was resolved
    
    # Game metadata
    neutral_site: bool = False         # Whether game at neutral location
    march_madness: bool = False        # Whether this is tournament game
    
    # Source tracking
    data_sources: List[DataSourceType] = field(default_factory=list)  # Which sources provided data for this game
    ingestion_timestamp: str = ""      # When data was ingested
    
    def __hash__(self):
        """Hash based on game identifiers."""
        return hash((
            self.game_id,
            self.game_date_cst,
            self.home_team_canonical,
            self.away_team_canonical,
            self.season,
        ))
    
    def __eq__(self, other):
        """Equality based on game identifiers."""
        if not isinstance(other, CanonicalGame):
            return False
        return (
            self.game_id == other.game_id and
            self.game_date_cst == other.game_date_cst and
            self.home_team_canonical == other.home_team_canonical and
            self.away_team_canonical == other.away_team_canonical and
            self.season == other.season
        )


@dataclass(frozen=True)
class CanonicalOdds:
    """Canonical odds (market line) representation."""
    game_id: str                       # Link to CanonicalGame
    game_date_cst: str
    season: int
    home_team_canonical: str
    away_team_canonical: str
    
    # Bookmaker info
    bookmaker: str                     # "DraftKings", "FanDuel", etc.
    market_type: str                   # "spread", "total", "moneyline"
    
    # Line info
    line_value: Optional[float]        # Spread or total value
    implied_probability: Optional[float]  # Calculated from line
    open_line: Optional[float]         # Opening line if available
    close_line: Optional[float]        # Closing line (most important)
    
    # H1 specific
    is_h1: bool = False                # Whether this is H1 market
    
    # Metadata
    source: DataSourceType = DataSourceType.ODDS_API
    ingestion_timestamp: str = ""


@dataclass(frozen=True)
class CanonicalScores:
    """Canonical game result representation."""
    game_id: str                       # Link to CanonicalGame
    game_date_cst: str
    season: int
    home_team_canonical: str
    away_team_canonical: str
    
    # Full game
    home_score: Optional[int]          # Final score
    away_score: Optional[int]
    
    # Half-time
    home_h1_score: Optional[int]       # H1 score
    away_h1_score: Optional[int]
    
    # Metadata
    source: DataSourceType = DataSourceType.ESPN_SCORES
    ingestion_timestamp: str = ""


@dataclass(frozen=True)
class CanonicalRatings:
    """Canonical team ratings representation."""
    team_canonical: str                # Canonical name
    season: int                        # Ratings for this season
    
    # Barttorvik ratings (efficiency-based)
    adj_o: Optional[float]             # Adjusted offensive efficiency
    adj_d: Optional[float]             # Adjusted defensive efficiency
    tempo: Optional[float]             # Possessions per 40 minutes
    
    # Additional ratings if available
    efg_o: Optional[float]             # Effective FG% offensive
    efg_d: Optional[float]             # Effective FG% defensive
    tor: Optional[float]               # Turnover rate
    orb: Optional[float]               # Offensive rebound %
    drb: Optional[float]               # Defensive rebound %
    
    # Metadata
    source: DataSourceType = DataSourceType.BARTTORVIK
    ingestion_timestamp: str = ""


class SeasonAwareCanonicalizer:
    """
    Converts dates to seasons consistently across all sources.
    
    Season definition:
    - November onwards in year Y → Season Y+1 (e.g., Nov 2023 → Season 2024)
    - May-October in year Y → Season Y (e.g., May 2024 → Season 2024)
    """
    
    @staticmethod
    def get_season_from_date(date_input: Any) -> int:
        """
        Determine NCAA season from date.
        
        Args:
            date_input: datetime, date, string (ISO), or CST string
        
        Returns:
            Season (int) - championship year
        """
        # Parse to CST date
        if isinstance(date_input, str):
            dt = parse_date_to_cst(date_input)
        elif isinstance(date_input, datetime):
            dt = date_input
        elif isinstance(date_input, date):
            dt = datetime.combine(date_input, datetime.min.time())
        else:
            raise ValueError(f"Unsupported date type: {type(date_input)}")
        
        # Determine season
        return get_season_for_game(dt.strftime("%Y-%m-%d"))
    
    @staticmethod
    def normalize_date_to_cst(date_input: Any) -> Tuple[str, str]:
        """
        Normalize any date format to CST date and datetime strings.
        
        Returns:
            (date_cst: str, datetime_cst: str) in ISO format
        """
        if isinstance(date_input, str):
            dt = parse_date_to_cst(date_input)
        elif isinstance(date_input, datetime):
            dt = date_input
        elif isinstance(date_input, date):
            dt = datetime.combine(date_input, datetime.min.time())
        else:
            raise ValueError(f"Unsupported date type: {type(date_input)}")
        
        date_cst = dt.strftime("%Y-%m-%d")
        datetime_cst = dt.isoformat()
        
        return date_cst, datetime_cst


class CanonicalDataIngestionPipeline:
    """
    Master ingestion pipeline that standardizes all data sources.
    
    Flow:
    1. Raw data from source
    2. Resolve team names via ProductionTeamResolver
    3. Determine season from date via SeasonAwareCanonicalizer
    4. Convert to canonical format
    5. Output standardized CanonicalGame/CanonicalOdds/CanonicalScores
    
    This enables:
    - Quick re-canonicalization for backtests
    - Version swaps (test new team aliases, season logic)
    - Unified feature engineering pipeline
    - Point-in-time validation
    """
    
    def __init__(self):
        """Initialize pipeline."""
        self.resolver = ProductionTeamResolver()
        self.canonicalizer = SeasonAwareCanonicalizer()
        self.ingestion_timestamp = datetime.utcnow().isoformat()
        self.stats = {
            "total_processed": 0,
            "successfully_resolved": 0,
            "failed_resolution": 0,
            "season_mismatches": 0,
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # PUBLIC INGESTION METHODS (one per data source)
    # ════════════════════════════════════════════════════════════════════════
    
    def ingest_odds_api(self, df: pd.DataFrame) -> List[CanonicalOdds]:
        """
        Ingest Odds API data and canonicalize.
        
        Expected columns:
        - event_id: Unique event identifier
        - commence_time: ISO datetime (UTC or naive, will convert to CST)
        - home_team: Raw home team name
        - away_team: Raw away team name
        - bookmaker: Sportsbook name
        - market_name: "spread", "total", etc.
        - price: Odds or line value
        
        Returns:
            List of CanonicalOdds objects
        """
        canonical_odds = []
        
        for _, row in df.iterrows():
            try:
                # Resolve teams
                home_resolved = self.resolver.resolve(str(row.get("home_team", "")).strip())
                away_resolved = self.resolver.resolve(str(row.get("away_team", "")).strip())
                
                if not home_resolved.resolved or not away_resolved.resolved:
                    self.stats["failed_resolution"] += 1
                    continue
                
                # Determine season and normalize date
                commence_time = row.get("commence_time", "")
                date_cst, datetime_cst = self.canonicalizer.normalize_date_to_cst(commence_time)
                season = self.canonicalizer.get_season_from_date(commence_time)
                
                # Create canonical game ID (if not provided)
                game_id = str(row.get("event_id", "")).strip() or f"{date_cst}_{home_resolved.canonical_name}_{away_resolved.canonical_name}"
                
                # Extract line value
                line_value = None
                try:
                    if pd.notna(row.get("price")):
                        line_value = float(row.get("price"))
                except (ValueError, TypeError):
                    pass
                
                canonical = CanonicalOdds(
                    game_id=game_id,
                    game_date_cst=date_cst,
                    season=season,
                    home_team_canonical=home_resolved.canonical_name,
                    away_team_canonical=away_resolved.canonical_name,
                    bookmaker=str(row.get("bookmaker", "")).strip() or "unknown",
                    market_type=str(row.get("market_name", "")).strip().lower() or "unknown",
                    line_value=line_value,
                    implied_probability=None,  # Could calculate from line
                    open_line=None,
                    close_line=line_value,  # Assume most recent is close
                    is_h1=("h1" in str(row.get("market_name", "")).lower()),
                    source=DataSourceType.ODDS_API,
                    ingestion_timestamp=self.ingestion_timestamp,
                )
                
                canonical_odds.append(canonical)
                self.stats["successfully_resolved"] += 1
                
            except Exception as e:
                self.stats["failed_resolution"] += 1
                continue
        
        self.stats["total_processed"] += len(df)
        return canonical_odds
    
    def ingest_espn_scores(self, df: pd.DataFrame) -> List[CanonicalScores]:
        """
        Ingest ESPN game scores and canonicalize.
        
        Expected columns:
        - date: Game date (any format, will convert to CST)
        - home_team: Raw home team name
        - away_team: Raw away team name
        - home_score: Final home score
        - away_score: Final away score
        - home_h1: H1 home score (optional)
        - away_h1: H1 away score (optional)
        
        Returns:
            List of CanonicalScores objects
        """
        canonical_scores = []
        
        for _, row in df.iterrows():
            try:
                # Resolve teams
                home_resolved = self.resolver.resolve(str(row.get("home_team", "")).strip())
                away_resolved = self.resolver.resolve(str(row.get("away_team", "")).strip())
                
                if not home_resolved.resolved or not away_resolved.resolved:
                    self.stats["failed_resolution"] += 1
                    continue
                
                # Determine season and normalize date
                date_input = row.get("date", "")
                date_cst, datetime_cst = self.canonicalizer.normalize_date_to_cst(date_input)
                season = self.canonicalizer.get_season_from_date(date_input)
                
                # Create game ID
                game_id = f"{date_cst}_{home_resolved.canonical_name}_{away_resolved.canonical_name}"
                
                # Extract scores
                home_score = None
                away_score = None
                try:
                    if pd.notna(row.get("home_score")):
                        home_score = int(row.get("home_score"))
                    if pd.notna(row.get("away_score")):
                        away_score = int(row.get("away_score"))
                except (ValueError, TypeError):
                    pass
                
                home_h1 = None
                away_h1 = None
                try:
                    if pd.notna(row.get("home_h1")):
                        home_h1 = int(row.get("home_h1"))
                    if pd.notna(row.get("away_h1")):
                        away_h1 = int(row.get("away_h1"))
                except (ValueError, TypeError):
                    pass
                
                canonical = CanonicalScores(
                    game_id=game_id,
                    game_date_cst=date_cst,
                    season=season,
                    home_team_canonical=home_resolved.canonical_name,
                    away_team_canonical=away_resolved.canonical_name,
                    home_score=home_score,
                    away_score=away_score,
                    home_h1_score=home_h1,
                    away_h1_score=away_h1,
                    source=DataSourceType.ESPN_SCORES,
                    ingestion_timestamp=self.ingestion_timestamp,
                )
                
                canonical_scores.append(canonical)
                self.stats["successfully_resolved"] += 1
                
            except Exception as e:
                self.stats["failed_resolution"] += 1
                continue
        
        self.stats["total_processed"] += len(df)
        return canonical_scores
    
    def ingest_barttorvik_ratings(self, ratings_dict: Dict[str, Dict[str, float]], season: int) -> List[CanonicalRatings]:
        """
        Ingest Barttorvik ratings and canonicalize.
        
        Expected format:
        {
            "Team Name": {
                "adj_o": 106.5,
                "adj_d": 92.3,
                "tempo": 68.2,
                ...
            }
        }
        
        Args:
            ratings_dict: Dictionary of team name → ratings
            season: Season for these ratings
        
        Returns:
            List of CanonicalRatings objects
        """
        canonical_ratings = []
        
        for team_name, rating_dict in ratings_dict.items():
            try:
                # Resolve team name
                resolved = self.resolver.resolve(str(team_name).strip())
                
                if not resolved.resolved:
                    self.stats["failed_resolution"] += 1
                    continue
                
                canonical = CanonicalRatings(
                    team_canonical=resolved.canonical_name,
                    season=season,
                    adj_o=self._safe_float(rating_dict.get("adj_o")),
                    adj_d=self._safe_float(rating_dict.get("adj_d")),
                    tempo=self._safe_float(rating_dict.get("tempo")),
                    efg_o=self._safe_float(rating_dict.get("efg_o")),
                    efg_d=self._safe_float(rating_dict.get("efg_d")),
                    tor=self._safe_float(rating_dict.get("tor")),
                    orb=self._safe_float(rating_dict.get("orb")),
                    drb=self._safe_float(rating_dict.get("drb")),
                    source=DataSourceType.BARTTORVIK,
                    ingestion_timestamp=self.ingestion_timestamp,
                )
                
                canonical_ratings.append(canonical)
                self.stats["successfully_resolved"] += 1
                
            except Exception as e:
                self.stats["failed_resolution"] += 1
                continue
        
        self.stats["total_processed"] += len(ratings_dict)
        return canonical_ratings
    
    def ingest_ncaahoopR_games(self, df: pd.DataFrame) -> List[CanonicalGame]:
        """
        Ingest ncaahoopR play-by-play/box score data and canonicalize.
        
        Expected columns:
        - date: Game date
        - home_team: Raw home team name
        - away_team: Raw away team name
        - h_points: Home points (from box score)
        - a_points: Away points (from box score)
        
        Returns:
            List of CanonicalGame objects
        """
        canonical_games = []
        
        for _, row in df.iterrows():
            try:
                # Resolve teams
                home_resolved = self.resolver.resolve(str(row.get("home_team", "")).strip())
                away_resolved = self.resolver.resolve(str(row.get("away_team", "")).strip())
                
                if not home_resolved.resolved or not away_resolved.resolved:
                    self.stats["failed_resolution"] += 1
                    continue
                
                # Determine season and normalize date
                date_input = row.get("date", "")
                date_cst, datetime_cst = self.canonicalizer.normalize_date_to_cst(date_input)
                season = self.canonicalizer.get_season_from_date(date_input)
                
                # Create game ID
                game_id = f"{date_cst}_{home_resolved.canonical_name}_{away_resolved.canonical_name}"
                
                canonical = CanonicalGame(
                    game_id=game_id,
                    game_date_cst=date_cst,
                    game_datetime_cst=datetime_cst,
                    season=season,
                    home_team_canonical=home_resolved.canonical_name,
                    away_team_canonical=away_resolved.canonical_name,
                    home_team_source=str(row.get("home_team", "")).strip(),
                    away_team_source=str(row.get("away_team", "")).strip(),
                    home_resolution_step=home_resolved.step_used.value,
                    away_resolution_step=away_resolved.step_used.value,
                    neutral_site=False,  # ncaahoopR doesn't specify, assume home advantage
                    march_madness=self._is_march_madness(date_cst, season),
                    data_sources=[DataSourceType.NCAAHOOPR],
                    ingestion_timestamp=self.ingestion_timestamp,
                )
                
                canonical_games.append(canonical)
                self.stats["successfully_resolved"] += 1
                
            except Exception as e:
                self.stats["failed_resolution"] += 1
                continue
        
        self.stats["total_processed"] += len(df)
        return canonical_games
    
    # ════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """Safely convert value to float, return None if not possible."""
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _is_march_madness(date_cst: str, season: int) -> bool:
        """Check if date falls in tournament window (March-April)."""
        try:
            dt = datetime.strptime(date_cst, "%Y-%m-%d")
            return dt.month in (3, 4)
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics."""
        return {
            **self.stats,
            "success_rate": self.stats["successfully_resolved"] / max(1, self.stats["total_processed"]),
        }


# Self-test
if __name__ == "__main__":
    print("="*70)
    print("Canonical Data Ingestion Pipeline - Self Test")
    print("="*70)
    print()
    
    pipeline = CanonicalDataIngestionPipeline()
    
    # Test 1: Season canonicalization
    print("Test 1: Season-Aware Canonicalization")
    print("-"*70)
    test_dates = [
        "2024-01-15",  # Should be Season 2024
        "2023-11-20",  # Should be Season 2024
        "2023-03-18",  # Should be Season 2023
    ]
    for date_str in test_dates:
        season = pipeline.canonicalizer.get_season_from_date(date_str)
        print(f"  {date_str} → Season {season}")
    print()
    
    # Test 2: Team resolution via ingestion
    print("Test 2: Team Resolution During Ingestion")
    print("-"*70)
    test_df = pd.DataFrame({
        "home_team": ["Duke", "Alabama Crimson Tide", "Tennessee Volunteers"],
        "away_team": ["North Carolina", "Auburn", "Tennesseeee"],  # Last one has typo
        "date": ["2024-01-15", "2024-01-16", "2024-01-17"],
    })
    
    canonical_games = pipeline.ingest_ncaahoopR_games(test_df)
    for game in canonical_games:
        print(f"  {game.game_date_cst}: {game.home_team_canonical} vs {game.away_team_canonical} "
              f"(Season {game.season})")
    
    print()
    print(f"Stats: {pipeline.get_stats()}")
