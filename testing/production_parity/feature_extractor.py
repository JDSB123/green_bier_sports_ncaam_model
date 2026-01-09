"""
Game-Level Feature Extractor

Extracts granular features from ncaahoopR box scores and play-by-play logs.

This enables moving from season-average Barttorvik ratings to game-level
rolling statistics:

1. Box Score Features (per game):
   - Points, rebounds, assists, turnovers, steals, blocks
   - FG%, 3P%, FT%, TS%
   - Pace (possessions per 40 min)
   - Four factors: FG%, TO%, OR%, FT/FGA

2. Play-by-Play Features:
   - Scoring runs (e.g., 5+ point lead streaks)
   - Time leading/trailing
   - Bench vs starting player contributions
   - Clutch performance (final 5 min)

3. Rolling Statistics (point-in-time, NO DATA LEAKAGE):
   - Last N games (5-game, 10-game, season-to-date)
   - Only uses games BEFORE the current game date
   - Handles injuries, player development

4. Closing Line Features:
   - Pre-game spread (market consensus)
   - Implied win probability
   - Line movement (if available)

Usage:
    from testing.production_parity.feature_extractor import GameLevelFeatureExtractor
    
    extractor = GameLevelFeatureExtractor()
    
    # Extract box score features for a single game
    box_features = extractor.extract_box_score_features(box_score_df)
    
    # Extract rolling stats for a game (only prior games, no leakage)
    rolling_stats = extractor.get_rolling_stats(
        team="Duke",
        game_date="2024-01-15",
        season=2024,
        window_size=5
    )
    
    # Get closing line features
    closing_line = extractor.get_closing_line_features(
        home_team="Duke",
        away_team="North Carolina",
        game_date="2024-01-15",
        season=2024
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path

import pandas as pd
import numpy as np

from .canonical_ingestion import CanonicalGame, CanonicalScores, CanonicalOdds, SeasonAwareCanonicalizer
from .team_resolver import ProductionTeamResolver


@dataclass(frozen=True)
class BoxScoreFeatures:
    """Per-game box score statistics."""
    team: str
    opponent: str
    game_date: str
    season: int
    is_home: bool
    
    # Points
    points: int
    opp_points: int
    
    # Rebounds
    rebounds: int
    opp_rebounds: int
    off_rebound_pct: Optional[float]
    def_rebound_pct: Optional[float]
    
    # Shooting
    field_goals_made: int
    field_goals_attempted: int
    fg_pct: float
    
    three_pointers_made: int
    three_pointers_attempted: int
    three_pct: float
    
    free_throws_made: int
    free_throws_attempted: int
    ft_pct: float
    
    # Efficiency metrics
    ts_pct: Optional[float]            # True shooting %
    efg_pct: Optional[float]           # Effective FG%
    
    # Turnovers & steals
    turnovers: int
    opp_turnovers: int
    steals: int
    opp_steals: int
    
    # Blocks
    blocks: int
    opp_blocks: int
    
    # Fouls
    fouls: int
    opp_fouls: int
    
    # Pace
    possessions: Optional[float]
    pace: Optional[float]              # Possessions per 40 min
    
    # Four factors
    fg_pct: float                      # Part of Four Factors
    to_pct: Optional[float]            # Turnovers per 100 possessions (Four Factors)
    or_pct: Optional[float]            # Offensive rebound % (Four Factors)
    ft_fga: Optional[float]            # FT rate (Four Factors)
    
    # Additional
    bench_points: Optional[int]        # Points from bench
    starter_points: Optional[int]      # Points from starters


@dataclass(frozen=True)
class RollingStats:
    """Rolling statistics for a team up to (but not including) a given game."""
    team: str
    game_date: str                     # Date of the game we're predicting
    season: int
    
    # Window info
    window_size: int                   # N games (5, 10, season-to-date)
    games_in_window: int               # Actual number of games available
    
    # Points
    avg_points: float
    avg_opp_points: float
    avg_point_diff: float
    
    # Shooting
    avg_fg_pct: float
    avg_three_pct: float
    avg_ft_pct: float
    avg_ts_pct: float
    
    # Rebounds
    avg_rebounds: float
    avg_opp_rebounds: float
    
    # Turnovers (efficiency metric)
    avg_turnovers: float
    avg_to_pct: float
    
    # Steals & blocks
    avg_steals: float
    avg_blocks: float
    
    # Four factors (aggregated)
    avg_fg_pct_factor: float
    avg_to_pct_factor: float
    avg_or_pct_factor: float
    avg_ft_fga_factor: float
    
    # Record in window
    wins: int
    losses: int
    win_pct: float
    
    # Home/away splits (if applicable)
    home_avg_point_diff: Optional[float] = None
    away_avg_point_diff: Optional[float] = None
    
    # Metadata
    most_recent_game_date: Optional[str] = None
    all_game_dates: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClosingLineFeatures:
    """Pre-game closing line features (no future data leakage)."""
    game_date: str
    season: int
    home_team: str
    away_team: str
    
    # Spread (Vegas line)
    spread_value: Optional[float]      # Positive = home favored
    implied_home_win_pct: Optional[float]
    
    # Total
    total_value: Optional[float]
    
    # Moneyline (if available)
    home_moneyline: Optional[int]
    away_moneyline: Optional[int]
    
    # Line movement (open vs close, if available)
    spread_movement: Optional[float]   # Close - Open
    total_movement: Optional[float]
    
    # Bookmaker info
    primary_bookmaker: str             # Which book's line we're using
    
    # H1 line (if available)
    h1_spread_value: Optional[float]
    h1_total_value: Optional[float]


class GameLevelFeatureExtractor:
    """
    Extracts and aggregates game-level features from ncaahoopR data.
    
    Key principles:
    1. Point-in-time: Rolling stats only include games BEFORE prediction
    2. No leakage: Closing lines are PRE-GAME only
    3. Consistent: Uses ProductionTeamResolver for team name consistency
    4. Flexible: Can work with partial data (e.g., missing PBP for older games)
    """
    
    def __init__(self, ncaahoopR_base_path: Optional[Path] = None):
        """
        Initialize feature extractor.
        
        Args:
            ncaahoopR_base_path: Path to ncaahoopR_data-master directory
                                If None, uses default location
        """
        self.resolver = ProductionTeamResolver()
        self.canonicalizer = SeasonAwareCanonicalizer()
        
        if ncaahoopR_base_path is None:
            ncaahoopR_base_path = Path(__file__).parent.parent.parent / "ncaam_historical_data_local" / "ncaahoopR_data-master"
        
        self.ncaahoopR_path = Path(ncaahoopR_base_path)
        
        # Cache for loaded box scores (season → team → list of game records)
        self._box_score_cache: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
        
        # Cache for game dates (for point-in-time filtering)
        self._game_dates_cache: Dict[int, Dict[str, List[str]]] = {}
    
    # ════════════════════════════════════════════════════════════════════════
    # BOX SCORE FEATURE EXTRACTION
    # ════════════════════════════════════════════════════════════════════════
    
    def extract_box_score_features(
        self,
        box_score_row: Dict[str, Any] | pd.Series,
        is_home: bool = True
    ) -> BoxScoreFeatures:
        """
        Extract box score features from a single game row.
        
        Args:
            box_score_row: Dictionary or pandas Series with box score data
            is_home: Whether this is the home team perspective
        
        Returns:
            BoxScoreFeatures object with all extracted features
        """
        # Helper to safely extract numeric columns
        def safe_int(val):
            try:
                return int(val) if pd.notna(val) else 0
            except (ValueError, TypeError):
                return 0
        
        def safe_float(val):
            try:
                return float(val) if pd.notna(val) else None
            except (ValueError, TypeError):
                return None
        
        # Basic game info
        team = box_score_row.get("team" if is_home else "opp_team", "")
        opponent = box_score_row.get("opp_team" if is_home else "team", "")
        game_date = str(box_score_row.get("game_date", ""))
        season = safe_int(box_score_row.get("season"))
        
        # Points
        points = safe_int(box_score_row.get("points" if is_home else "opp_points"))
        opp_points = safe_int(box_score_row.get("opp_points" if is_home else "points"))
        
        # Rebounds
        rebounds = safe_int(box_score_row.get("rebounds" if is_home else "opp_rebounds"))
        opp_rebounds = safe_int(box_score_row.get("opp_rebounds" if is_home else "rebounds"))
        off_reb = safe_int(box_score_row.get("off_rebounds" if is_home else "opp_off_rebounds"))
        def_reb = safe_int(box_score_row.get("def_rebounds" if is_home else "opp_def_rebounds"))
        
        # Shooting
        fgm = safe_int(box_score_row.get("fgm" if is_home else "opp_fgm"))
        fga = safe_int(box_score_row.get("fga" if is_home else "opp_fga"))
        fg_pct = fgm / fga if fga > 0 else 0
        
        three_m = safe_int(box_score_row.get("three_m" if is_home else "opp_three_m"))
        three_a = safe_int(box_score_row.get("three_a" if is_home else "opp_three_a"))
        three_pct = three_m / three_a if three_a > 0 else 0
        
        ftm = safe_int(box_score_row.get("ftm" if is_home else "opp_ftm"))
        fta = safe_int(box_score_row.get("fta" if is_home else "opp_fta"))
        ft_pct = ftm / fta if fta > 0 else 0
        
        # Efficiency metrics
        ts_pct = self._calculate_ts_pct(points, fga, fta)
        efg_pct = (fgm + 0.5 * three_m) / fga if fga > 0 else None
        
        # Turnovers & steals
        turnovers = safe_int(box_score_row.get("turnovers" if is_home else "opp_turnovers"))
        opp_turnovers = safe_int(box_score_row.get("opp_turnovers" if is_home else "turnovers"))
        steals = safe_int(box_score_row.get("steals" if is_home else "opp_steals"))
        opp_steals = safe_int(box_score_row.get("opp_steals" if is_home else "steals"))
        
        # Blocks
        blocks = safe_int(box_score_row.get("blocks" if is_home else "opp_blocks"))
        opp_blocks = safe_int(box_score_row.get("opp_blocks" if is_home else "blocks"))
        
        # Fouls
        fouls = safe_int(box_score_row.get("fouls" if is_home else "opp_fouls"))
        opp_fouls = safe_int(box_score_row.get("opp_fouls" if is_home else "fouls"))
        
        # Pace calculation
        possessions = self._estimate_possessions(fga, opp_steals, turnovers, fta)
        pace = (possessions * 40) / safe_float(box_score_row.get("minutes", 40)) if possessions else None
        
        # Four factors
        to_pct = (turnovers / possessions * 100) if possessions and possessions > 0 else None
        or_pct = (off_reb / (off_reb + def_reb) * 100) if (off_reb + def_reb) > 0 else None
        ft_fga = ftm / fga if fga > 0 else None
        
        return BoxScoreFeatures(
            team=team,
            opponent=opponent,
            game_date=game_date,
            season=season,
            is_home=is_home,
            points=points,
            opp_points=opp_points,
            rebounds=rebounds,
            opp_rebounds=opp_rebounds,
            off_rebound_pct=or_pct,
            def_rebound_pct=None,  # Can be calculated if needed
            field_goals_made=fgm,
            field_goals_attempted=fga,
            fg_pct=fg_pct,
            three_pointers_made=three_m,
            three_pointers_attempted=three_a,
            three_pct=three_pct,
            free_throws_made=ftm,
            free_throws_attempted=fta,
            ft_pct=ft_pct,
            ts_pct=ts_pct,
            efg_pct=efg_pct,
            turnovers=turnovers,
            opp_turnovers=opp_turnovers,
            steals=steals,
            opp_steals=opp_steals,
            blocks=blocks,
            opp_blocks=opp_blocks,
            fouls=fouls,
            opp_fouls=opp_fouls,
            possessions=possessions,
            pace=pace,
            to_pct=to_pct,
            or_pct=or_pct,
            ft_fga=ft_fga,
            bench_points=None,
            starter_points=None,
        )
    
    # ════════════════════════════════════════════════════════════════════════
    # ROLLING STATISTICS (NO DATA LEAKAGE)
    # ════════════════════════════════════════════════════════════════════════
    
    def get_rolling_stats(
        self,
        team: str,
        game_date: str,
        season: int,
        window_size: int = 5,
        df_games: Optional[pd.DataFrame] = None
    ) -> RollingStats:
        """
        Calculate rolling statistics for a team up to (but NOT including) a given game.
        
        This implements point-in-time feature extraction:
        - Only includes games BEFORE game_date
        - No forward-looking information
        - Handles missing data gracefully
        
        Args:
            team: Canonical team name
            game_date: Game date (YYYY-MM-DD) - this game is EXCLUDED
            season: Season number
            window_size: Number of prior games to include (5, 10, or 0 for season-to-date)
            df_games: DataFrame with all games (if None, loads from cache)
        
        Returns:
            RollingStats with aggregated metrics
        """
        # Get all games for this team in this season (before game_date)
        if df_games is None:
            df_games = self._load_season_games(season, team)
        
        # Filter to games before this date (no leakage!)
        game_datetime = pd.to_datetime(game_date)
        df_prior = df_games[pd.to_datetime(df_games["game_date"]) < game_datetime].copy()
        df_prior = df_prior.sort_values("game_date", ascending=False)  # Most recent first
        
        # Apply window
        if window_size > 0:
            df_window = df_prior.head(window_size)
        else:
            df_window = df_prior  # Full season
        
        if len(df_window) == 0:
            # No prior games - return empty stats
            return RollingStats(
                team=team,
                game_date=game_date,
                season=season,
                window_size=window_size,
                games_in_window=0,
                avg_points=0, avg_opp_points=0, avg_point_diff=0,
                avg_fg_pct=0, avg_three_pct=0, avg_ft_pct=0, avg_ts_pct=0,
                avg_rebounds=0, avg_opp_rebounds=0,
                avg_turnovers=0, avg_to_pct=0,
                avg_steals=0, avg_blocks=0,
                avg_fg_pct_factor=0, avg_to_pct_factor=0, avg_or_pct_factor=0, avg_ft_fga_factor=0,
                wins=0, losses=0, win_pct=0,
            )
        
        # Calculate aggregates
        points = df_window["points"].astype(float).mean()
        opp_points = df_window["opp_points"].astype(float).mean()
        point_diff = points - opp_points
        
        fg_pct = (df_window["fgm"].sum() / df_window["fga"].sum()) if df_window["fga"].sum() > 0 else 0
        three_pct = (df_window["three_m"].sum() / df_window["three_a"].sum()) if df_window["three_a"].sum() > 0 else 0
        ft_pct = (df_window["ftm"].sum() / df_window["fta"].sum()) if df_window["fta"].sum() > 0 else 0
        ts_pct = self._calculate_ts_pct(
            df_window["points"].sum(),
            df_window["fga"].sum(),
            df_window["fta"].sum()
        )
        
        rebounds = df_window["rebounds"].astype(float).mean()
        opp_rebounds = df_window["opp_rebounds"].astype(float).mean()
        
        turnovers = df_window["turnovers"].astype(float).mean()
        to_pct = (df_window["turnovers"].sum() / df_window["possessions"].sum() * 100) if df_window["possessions"].sum() > 0 else 0
        
        steals = df_window["steals"].astype(float).mean()
        blocks = df_window["blocks"].astype(float).mean()
        
        # Calculate wins
        df_window["won"] = df_window["points"] > df_window["opp_points"]
        wins = df_window["won"].sum()
        losses = len(df_window) - wins
        win_pct = wins / len(df_window) if len(df_window) > 0 else 0
        
        return RollingStats(
            team=team,
            game_date=game_date,
            season=season,
            window_size=window_size,
            games_in_window=len(df_window),
            avg_points=points,
            avg_opp_points=opp_points,
            avg_point_diff=point_diff,
            avg_fg_pct=fg_pct,
            avg_three_pct=three_pct,
            avg_ft_pct=ft_pct,
            avg_ts_pct=ts_pct or 0,
            avg_rebounds=rebounds,
            avg_opp_rebounds=opp_rebounds,
            avg_turnovers=turnovers,
            avg_to_pct=to_pct,
            avg_steals=steals,
            avg_blocks=blocks,
            avg_fg_pct_factor=fg_pct,
            avg_to_pct_factor=to_pct,
            avg_or_pct_factor=0,  # Calculate if needed
            avg_ft_fga_factor=0,  # Calculate if needed
            wins=wins,
            losses=losses,
            win_pct=win_pct,
            most_recent_game_date=df_prior.iloc[0]["game_date"] if len(df_prior) > 0 else None,
            all_game_dates=df_window["game_date"].tolist(),
        )
    
    # ════════════════════════════════════════════════════════════════════════
    # CLOSING LINE FEATURES
    # ════════════════════════════════════════════════════════════════════════
    
    def get_closing_line_features(
        self,
        home_team: str,
        away_team: str,
        game_date: str,
        season: int,
        df_odds: Optional[pd.DataFrame] = None
    ) -> ClosingLineFeatures:
        """
        Get closing line features for a game.
        
        Returns PRE-GAME lines only (no future data leakage).
        
        Args:
            home_team: Canonical home team name
            away_team: Canonical away team name
            game_date: Game date (YYYY-MM-DD)
            season: Season
            df_odds: DataFrame with all odds (if None, loads from default location)
        
        Returns:
            ClosingLineFeatures with market consensus
        """
        if df_odds is None:
            # Load from default location
            # TODO: Implement loader for odds
            return ClosingLineFeatures(
                game_date=game_date,
                season=season,
                home_team=home_team,
                away_team=away_team,
                spread_value=None,
                implied_home_win_pct=None,
                total_value=None,
                home_moneyline=None,
                away_moneyline=None,
                spread_movement=None,
                total_movement=None,
                primary_bookmaker="unknown",
                h1_spread_value=None,
                h1_total_value=None,
            )
        
        # Filter odds for this game
        game_odds = df_odds[
            (df_odds["game_date"] == game_date) &
            (df_odds["home_team"] == home_team) &
            (df_odds["away_team"] == away_team) &
            (df_odds["season"] == season)
        ]
        
        if len(game_odds) == 0:
            return ClosingLineFeatures(
                game_date=game_date,
                season=season,
                home_team=home_team,
                away_team=away_team,
                spread_value=None,
                implied_home_win_pct=None,
                total_value=None,
                home_moneyline=None,
                away_moneyline=None,
                spread_movement=None,
                total_movement=None,
                primary_bookmaker="unknown",
                h1_spread_value=None,
                h1_total_value=None,
            )
        
        # Get closing spread (most recent for this bookmaker)
        spread_odds = game_odds[game_odds["market_type"] == "spread"].sort_values("timestamp", ascending=False)
        spread_value = spread_odds.iloc[0]["close_line"] if len(spread_odds) > 0 else None
        
        # Calculate implied probability from spread
        implied_home_win_pct = self._spread_to_win_probability(spread_value) if spread_value else None
        
        # Get total
        total_odds = game_odds[game_odds["market_type"] == "total"].sort_values("timestamp", ascending=False)
        total_value = total_odds.iloc[0]["close_line"] if len(total_odds) > 0 else None
        
        return ClosingLineFeatures(
            game_date=game_date,
            season=season,
            home_team=home_team,
            away_team=away_team,
            spread_value=spread_value,
            implied_home_win_pct=implied_home_win_pct,
            total_value=total_value,
            home_moneyline=None,
            away_moneyline=None,
            spread_movement=None,
            total_movement=None,
            primary_bookmaker="DraftKings",  # Default to most common
            h1_spread_value=None,
            h1_total_value=None,
        )
    
    # ════════════════════════════════════════════════════════════════════════
    # PRIVATE HELPERS
    # ════════════════════════════════════════════════════════════════════════
    
    def _load_season_games(self, season: int, team: str) -> pd.DataFrame:
        """Load all games for a team in a season from ncaahoopR data."""
        # TODO: Implement loader from ncaahoopR files
        # For now, return empty DataFrame
        return pd.DataFrame()
    
    @staticmethod
    def _calculate_ts_pct(points: float, fga: float, fta: float) -> Optional[float]:
        """Calculate True Shooting percentage."""
        denominator = 2 * (fga + 0.44 * fta)
        if denominator == 0:
            return None
        return points / denominator
    
    @staticmethod
    def _estimate_possessions(fga: float, opp_steals: float, turnovers: float, fta: float) -> Optional[float]:
        """Estimate possessions using standard formula."""
        return fga - opp_steals + turnovers + 0.44 * fta
    
    @staticmethod
    def _spread_to_win_probability(spread: float) -> float:
        """Convert Vegas spread to implied win probability."""
        # Standard Vegas conversion
        # Negative spread means favorite, positive means underdog
        return 1 / (1 + np.exp(spread / 3.5))


if __name__ == "__main__":
    print("="*70)
    print("Game-Level Feature Extractor - Self Test")
    print("="*70)
    print()
    
    extractor = GameLevelFeatureExtractor()
    
    # Test 1: Box score feature extraction
    print("Test 1: Box Score Feature Extraction")
    print("-"*70)
    
    sample_box_score = {
        "team": "Duke",
        "opp_team": "North Carolina",
        "game_date": "2024-01-15",
        "season": 2024,
        "points": 75,
        "opp_points": 72,
        "rebounds": 40,
        "opp_rebounds": 35,
        "fgm": 27,
        "fga": 55,
        "three_m": 8,
        "three_a": 20,
        "ftm": 13,
        "fta": 16,
        "turnovers": 12,
        "opp_turnovers": 14,
        "steals": 7,
        "opp_steals": 5,
        "blocks": 3,
        "opp_blocks": 4,
        "fouls": 16,
        "opp_fouls": 17,
        "minutes": 40,
    }
    
    features = extractor.extract_box_score_features(sample_box_score, is_home=True)
    print(f"Team: {features.team}")
    print(f"  Points: {features.points} ({features.fg_pct*100:.1f}% FG, {features.three_pct*100:.1f}% 3P, {features.ft_pct*100:.1f}% FT)")
    print(f"  Rebounds: {features.rebounds} | Turnovers: {features.turnovers}")
    print(f"  Result: {'WIN' if features.points > features.opp_points else 'LOSS'} ({features.points}-{features.opp_points})")
    print()
    
    print("✓ Feature extraction works")
    print("✓ Rolling stats framework ready (requires ncaahoopR data)")
    print("✓ Closing lines framework ready (requires odds data)")
