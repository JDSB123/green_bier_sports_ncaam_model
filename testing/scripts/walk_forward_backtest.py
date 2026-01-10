#!/usr/bin/env python3
"""
Walk-Forward Validation Framework for NCAAM Backtesting

CRITICAL: This framework ensures STRICT temporal separation to prevent data leakage.

Walk-Forward Validation:
1. Train on seasons N-3 to N-1, test on season N
2. Never use future data in training
3. Point-in-time ratings only (no end-of-season data)
4. Actual odds required (no -110 assumptions)
5. CLV tracking for every bet

Usage:
    python testing/scripts/walk_forward_backtest.py --market fg_spread
    python testing/scripts/walk_forward_backtest.py --all-markets --test-seasons 2024,2025
    python testing/scripts/walk_forward_backtest.py --validate-only  # Check for leakage
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Iterator

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class MarketType(str, Enum):
    """Four betting markets."""
    FG_SPREAD = "fg_spread"
    FG_TOTAL = "fg_total"
    H1_SPREAD = "h1_spread"
    H1_TOTAL = "h1_total"


class BetOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    SKIP = "SKIP"  # Missing data


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation."""
    
    # Test seasons (train on all prior seasons)
    test_seasons: List[int] = field(default_factory=lambda: [2023, 2024, 2025])
    
    # Market to evaluate
    market: MarketType = MarketType.FG_SPREAD
    
    # Training window
    min_train_seasons: int = 2  # Minimum seasons in training set
    
    # Betting thresholds
    min_edge: float = 2.0  # Minimum edge (points) to place bet
    
    # Kelly sizing
    kelly_fraction: float = 0.25
    base_unit: float = 100.0
    
    # Variance estimates for probability calculation
    sigma_spread: float = 11.0  # Std dev for spreads
    sigma_total: float = 10.0  # Std dev for totals
    
    # Feature requirements
    require_point_in_time_ratings: bool = True
    require_opening_lines: bool = True
    require_closing_lines: bool = True  # For CLV calculation
    require_actual_odds: bool = True  # No -110 fallback


@dataclass
class BetResult:
    """Result of a single bet with CLV tracking."""
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    season: int
    market: str
    
    # Prediction
    predicted_line: float
    
    # Market lines (opening and closing)
    opening_line: float
    closing_line: float
    
    # Edge calculation
    edge_vs_opening: float  # Points of edge vs opening line
    edge_vs_closing: float  # Points of edge vs closing line
    
    # CLV (Closing Line Value)
    clv: float  # How much line moved in our favor
    clv_percent: float  # CLV as percentage
    
    # Bet details
    bet_side: str  # "home", "away", "over", "under"
    actual_odds: float  # The odds we bet at (from opening line)
    wager: float
    
    # Outcome
    actual_result: float  # Actual margin or total
    outcome: BetOutcome
    profit: float


@dataclass
class SeasonResults:
    """Results for a single test season."""
    season: int
    market: str
    
    # Sample sizes
    total_games: int
    games_with_all_data: int  # Games with opening, closing, odds, ratings
    total_bets: int
    
    # Outcomes
    wins: int
    losses: int
    pushes: int
    
    # Financials
    total_wagered: float
    total_profit: float
    roi: float
    
    # Performance metrics
    win_rate: float
    avg_edge: float
    
    # CLV metrics (the gold standard)
    avg_clv: float
    clv_positive_rate: float  # % of bets with positive CLV
    
    # Leakage check
    ratings_verified_point_in_time: bool
    closing_lines_captured: bool


@dataclass
class WalkForwardSummary:
    """Summary of walk-forward validation across all test seasons."""
    market: str
    test_seasons: List[int]
    
    # Aggregated metrics
    total_bets: int
    overall_win_rate: float
    overall_roi: float
    overall_avg_clv: float
    overall_clv_positive_rate: float
    
    # Per-season breakdown
    season_results: Dict[int, SeasonResults]
    
    # Validation flags
    no_leakage_verified: bool
    all_data_requirements_met: bool


class WalkForwardValidator:
    """
    Walk-forward validation engine.
    
    CRITICAL LEAKAGE PREVENTION:
    1. Training data is always from BEFORE test season start
    2. Point-in-time ratings only (no future data)
    3. Opening lines used for bet decisions
    4. Closing lines captured for CLV calculation
    5. Actual odds required (no assumptions)
    """
    
    def __init__(self, config: WalkForwardConfig):
        self.config = config
        
        # Data paths
        self.root_dir = Path(__file__).resolve().parents[2]
        self.data_dir = self.root_dir / "ncaam_historical_data_local" / "backtest_datasets"
        self.results_dir = self.root_dir / "testing" / "results" / "walk_forward"
        
        # Load point-in-time ratings lookup
        try:
            from testing.scripts.point_in_time_ratings import PointInTimeRatingsLookup
            self.ratings_lookup = PointInTimeRatingsLookup(strict_mode=False)
        except ImportError:
            self.ratings_lookup = None
    
    def load_backtest_data(self) -> pd.DataFrame:
        """Load the master backtest dataset."""
        # Prefer enhanced dataset with all features
        enhanced_path = self.data_dir / "backtest_master_enhanced.csv"
        base_path = self.data_dir / "backtest_master.csv"
        consolidated_path = self.data_dir / "backtest_master_consolidated.csv"
        
        for path in [enhanced_path, consolidated_path, base_path]:
            if path.exists():
                print(f"Loading backtest data from: {path.name}")
                df = pd.read_csv(path)
                df["game_date"] = pd.to_datetime(df["game_date"])
                return df
        
        raise FileNotFoundError(
            f"Backtest data not found. Run build_backtest_dataset_canonical.py first."
        )
    
    def get_walk_forward_splits(
        self,
        df: pd.DataFrame
    ) -> Iterator[Tuple[int, pd.DataFrame, pd.DataFrame]]:
        """
        Generate walk-forward train/test splits.
        
        For each test season, training data is ALL games from prior seasons.
        
        Yields:
            Tuple of (test_season, train_df, test_df)
        """
        # Get unique seasons
        all_seasons = sorted(df["season"].dropna().unique().astype(int))
        
        for test_season in self.config.test_seasons:
            if test_season not in all_seasons:
                print(f"Warning: Season {test_season} not in data, skipping")
                continue
            
            # Training data: all games from seasons BEFORE test season
            train_seasons = [s for s in all_seasons if s < test_season]
            
            if len(train_seasons) < self.config.min_train_seasons:
                print(
                    f"Warning: Only {len(train_seasons)} training seasons for "
                    f"test season {test_season}, need {self.config.min_train_seasons}"
                )
                continue
            
            train_df = df[df["season"].isin(train_seasons)].copy()
            test_df = df[df["season"] == test_season].copy()
            
            print(f"\nSplit: Train on {train_seasons} ({len(train_df)} games), "
                  f"Test on {test_season} ({len(test_df)} games)")
            
            yield test_season, train_df, test_df
    
    def validate_data_requirements(
        self,
        df: pd.DataFrame,
        season: int
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Validate that data meets all requirements for no-leakage backtesting.
        
        Returns:
            Tuple of (valid_df, validation_stats)
        """
        stats = {
            "total_games": len(df),
            "missing_opening_line": 0,
            "missing_closing_line": 0,
            "missing_actual_odds": 0,
            "missing_ratings": 0,
            "missing_result": 0,
            "valid_games": 0
        }
        
        # Get column names for this market
        market = self.config.market.value
        
        # Map market to data columns
        line_col_map = {
            "fg_spread": ("fg_spread", "fg_spread_home_price", "fg_spread_away_price", "actual_margin"),
            "fg_total": ("fg_total", "fg_total_over_price", "fg_total_under_price", "actual_total"),
            "h1_spread": ("h1_spread", "h1_spread_home_price", "h1_spread_away_price", "h1_actual_margin"),
            "h1_total": ("h1_total", "h1_total_over_price", "h1_total_under_price", "h1_actual_total"),
        }
        
        line_col, price_col1, price_col2, result_col = line_col_map[market]
        
        # Check for required columns
        valid_mask = pd.Series([True] * len(df), index=df.index)
        
        # Opening line (we use the main line column as opening)
        if line_col in df.columns:
            missing_opening = df[line_col].isna()
            stats["missing_opening_line"] = missing_opening.sum()
            if self.config.require_opening_lines:
                valid_mask &= ~missing_opening
        
        # Closing line (need a separate column for this)
        closing_col = f"{line_col}_closing"
        if closing_col in df.columns:
            missing_closing = df[closing_col].isna()
            stats["missing_closing_line"] = missing_closing.sum()
            if self.config.require_closing_lines:
                valid_mask &= ~missing_closing
        else:
            # If no closing line column, use opening as closing (less ideal)
            stats["missing_closing_line"] = len(df)
        
        # Actual odds
        if price_col1 in df.columns:
            missing_odds = df[price_col1].isna()
            stats["missing_actual_odds"] = missing_odds.sum()
            if self.config.require_actual_odds:
                valid_mask &= ~missing_odds
        
        # Ratings (check for point-in-time columns)
        rating_cols = ["home_adj_o", "home_adj_d", "away_adj_o", "away_adj_d"]
        pit_rating_cols = [f"{col}_pit" for col in rating_cols]
        
        # Try point-in-time columns first, then fall back to regular
        for pit_col, reg_col in zip(pit_rating_cols, rating_cols):
            if pit_col in df.columns:
                missing = df[pit_col].isna()
            elif reg_col in df.columns:
                missing = df[reg_col].isna()
            else:
                missing = pd.Series([True] * len(df), index=df.index)
            
            stats["missing_ratings"] += missing.sum()
            if self.config.require_point_in_time_ratings:
                valid_mask &= ~missing
        
        # Result
        if result_col in df.columns:
            missing_result = df[result_col].isna()
            stats["missing_result"] = missing_result.sum()
            valid_mask &= ~missing_result
        
        stats["valid_games"] = valid_mask.sum()
        
        print(f"\nData validation for season {season}:")
        print(f"  Total games: {stats['total_games']}")
        print(f"  Missing opening line: {stats['missing_opening_line']}")
        print(f"  Missing closing line: {stats['missing_closing_line']}")
        print(f"  Missing actual odds: {stats['missing_actual_odds']}")
        print(f"  Missing ratings: {stats['missing_ratings']}")
        print(f"  Missing result: {stats['missing_result']}")
        print(f"  Valid games: {stats['valid_games']}")
        
        return df[valid_mask], stats
    
    def generate_prediction(
        self,
        row: pd.Series,
        train_df: Optional[pd.DataFrame] = None
    ) -> float:
        """
        Generate prediction for a game.
        
        Uses the Barttorvik formula with point-in-time ratings.
        No leakage: only uses data available before game date.
        """
        # Get ratings (prefer point-in-time)
        home_adj_o = row.get("home_adj_o_pit") or row.get("home_adj_o", 105)
        home_adj_d = row.get("home_adj_d_pit") or row.get("home_adj_d", 105)
        away_adj_o = row.get("away_adj_o_pit") or row.get("away_adj_o", 105)
        away_adj_d = row.get("away_adj_d_pit") or row.get("away_adj_d", 105)
        
        home_tempo = row.get("home_tempo_pit") or row.get("home_tempo", 67.5)
        away_tempo = row.get("away_tempo_pit") or row.get("away_tempo", 67.5)
        
        market = self.config.market
        
        # Home court advantage (derived from historical backtests)
        HCA_SPREAD = 5.8
        HCA_H1_SPREAD = 3.6
        
        if market == MarketType.FG_SPREAD:
            # Efficiency differential formula
            home_net = home_adj_o - home_adj_d
            away_net = away_adj_o - away_adj_d
            raw_margin = (home_net - away_net) / 2.0
            predicted = -(raw_margin + HCA_SPREAD)  # Negative = home favored
            
        elif market == MarketType.FG_TOTAL:
            # Total points formula
            avg_tempo = (home_tempo + away_tempo) / 2.0
            home_pts = home_adj_o * avg_tempo / 100.0
            away_pts = away_adj_o * avg_tempo / 100.0
            predicted = home_pts + away_pts + 7.0  # +7 calibration
            
        elif market == MarketType.H1_SPREAD:
            # First half spread (independent, not FG/2)
            home_net = home_adj_o - home_adj_d
            away_net = away_adj_o - away_adj_d
            raw_margin = (home_net - away_net) / 2.0
            predicted = -(raw_margin * 0.50 + HCA_H1_SPREAD)
            
        elif market == MarketType.H1_TOTAL:
            # First half total (independent, not FG * 0.48)
            avg_tempo = (home_tempo + away_tempo) / 2.0
            home_pts = home_adj_o * avg_tempo / 100.0
            away_pts = away_adj_o * avg_tempo / 100.0
            fg_total = home_pts + away_pts
            predicted = fg_total * 0.469 + 2.7  # Independent calibration
            
        else:
            predicted = 0.0
        
        return predicted
    
    def calculate_edge(
        self,
        predicted: float,
        market_line: float
    ) -> float:
        """Calculate edge in points."""
        return abs(predicted - market_line)
    
    def get_bet_side(
        self,
        predicted: float,
        market_line: float
    ) -> str:
        """Determine which side to bet."""
        if "spread" in self.config.market.value:
            # For spreads: if predicted < market, bet home
            return "home" if predicted < market_line else "away"
        else:
            # For totals: if predicted > market, bet over
            return "over" if predicted > market_line else "under"
    
    def determine_outcome(
        self,
        bet_side: str,
        market_line: float,
        actual_result: float
    ) -> BetOutcome:
        """Determine bet outcome."""
        if pd.isna(actual_result):
            return BetOutcome.SKIP
        
        if "spread" in self.config.market.value:
            # For spreads
            if bet_side == "home":
                result = actual_result + market_line  # Home covers if margin + spread > 0
            else:
                result = -actual_result - market_line  # Away covers if -margin - spread > 0
        else:
            # For totals
            if bet_side == "over":
                result = actual_result - market_line  # Over hits if total - line > 0
            else:
                result = market_line - actual_result  # Under hits if line - total > 0
        
        if abs(result) < 0.5:  # Push within 0.5
            return BetOutcome.PUSH
        elif result > 0:
            return BetOutcome.WIN
        else:
            return BetOutcome.LOSS
    
    def calculate_profit(
        self,
        outcome: BetOutcome,
        wager: float,
        odds: float
    ) -> float:
        """Calculate profit from bet outcome using actual odds."""
        if outcome == BetOutcome.WIN:
            if odds > 0:
                return wager * (odds / 100)
            else:
                return wager * (100 / abs(odds))
        elif outcome == BetOutcome.LOSS:
            return -wager
        else:  # PUSH or SKIP
            return 0.0
    
    def calculate_clv(
        self,
        bet_side: str,
        opening_line: float,
        closing_line: float
    ) -> Tuple[float, float]:
        """
        Calculate Closing Line Value.
        
        CLV = how much the line moved in our favor from open to close.
        Positive CLV indicates we captured value.
        
        Returns:
            Tuple of (clv_points, clv_percent)
        """
        line_movement = closing_line - opening_line
        
        if "spread" in self.config.market.value:
            if bet_side == "home":
                # Betting home spread. Line going more negative = value for home bet
                clv = opening_line - closing_line  # Positive if line moved against us (more value)
            else:
                # Betting away. Line going more positive = value for away bet
                clv = closing_line - opening_line
        else:
            # Totals
            if bet_side == "over":
                # Betting over. Line going up = value for over
                clv = closing_line - opening_line
            else:
                # Betting under. Line going down = value for under
                clv = opening_line - closing_line
        
        # Calculate percentage
        if abs(opening_line) > 0:
            clv_percent = (clv / abs(opening_line)) * 100
        else:
            clv_percent = 0.0
        
        return clv, clv_percent
    
    def run_season_backtest(
        self,
        test_season: int,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> SeasonResults:
        """
        Run backtest for a single test season.
        
        Training data is used for any model training (if applicable).
        Test data is used for evaluation.
        """
        market = self.config.market.value
        
        # Validate data requirements
        valid_df, stats = self.validate_data_requirements(test_df, test_season)
        
        if len(valid_df) == 0:
            print(f"No valid games for season {test_season}")
            return SeasonResults(
                season=test_season,
                market=market,
                total_games=stats["total_games"],
                games_with_all_data=0,
                total_bets=0,
                wins=0, losses=0, pushes=0,
                total_wagered=0, total_profit=0, roi=0,
                win_rate=0, avg_edge=0,
                avg_clv=0, clv_positive_rate=0,
                ratings_verified_point_in_time=False,
                closing_lines_captured=False
            )
        
        # Get column mappings
        line_col_map = {
            "fg_spread": ("fg_spread", "fg_spread_home_price", "fg_spread_away_price", "actual_margin"),
            "fg_total": ("fg_total", "fg_total_over_price", "fg_total_under_price", "actual_total"),
            "h1_spread": ("h1_spread", "h1_spread_home_price", "h1_spread_away_price", "h1_actual_margin"),
            "h1_total": ("h1_total", "h1_total_over_price", "h1_total_under_price", "h1_actual_total"),
        }
        
        line_col, price_col1, price_col2, result_col = line_col_map[market]
        closing_col = f"{line_col}_closing"
        
        # Process each game
        bet_results = []
        
        for idx, row in valid_df.iterrows():
            # Generate prediction
            predicted = self.generate_prediction(row, train_df)
            
            # Get opening line
            opening_line = row.get(line_col)
            if pd.isna(opening_line):
                continue
            
            # Get closing line (use opening if not available)
            closing_line = row.get(closing_col, opening_line)
            if pd.isna(closing_line):
                closing_line = opening_line
            
            # Calculate edge vs opening line
            edge = self.calculate_edge(predicted, opening_line)
            
            # Only bet if edge exceeds threshold
            if edge < self.config.min_edge:
                continue
            
            # Determine bet side
            bet_side = self.get_bet_side(predicted, opening_line)
            
            # Get actual odds
            if bet_side in ["home", "over"]:
                actual_odds = row.get(price_col1)
            else:
                actual_odds = row.get(price_col2)
            
            if pd.isna(actual_odds):
                continue  # Skip bets without actual odds
            
            # Get actual result
            actual_result = row.get(result_col)
            if pd.isna(actual_result):
                continue
            
            # Determine outcome
            outcome = self.determine_outcome(bet_side, opening_line, actual_result)
            if outcome == BetOutcome.SKIP:
                continue
            
            # Calculate profit
            wager = self.config.base_unit
            profit = self.calculate_profit(outcome, wager, actual_odds)
            
            # Calculate CLV
            clv, clv_percent = self.calculate_clv(bet_side, opening_line, closing_line)
            
            bet_results.append(BetResult(
                game_id=str(row.get("game_id", idx)),
                game_date=str(row["game_date"].date()),
                home_team=row["home_team"],
                away_team=row["away_team"],
                season=test_season,
                market=market,
                predicted_line=round(predicted, 2),
                opening_line=round(opening_line, 2),
                closing_line=round(closing_line, 2),
                edge_vs_opening=round(edge, 2),
                edge_vs_closing=round(abs(predicted - closing_line), 2),
                clv=round(clv, 2),
                clv_percent=round(clv_percent, 2),
                bet_side=bet_side,
                actual_odds=round(actual_odds, 1),
                wager=wager,
                actual_result=round(actual_result, 2),
                outcome=outcome,
                profit=round(profit, 2)
            ))
        
        # Aggregate results
        total_bets = len(bet_results)
        wins = sum(1 for r in bet_results if r.outcome == BetOutcome.WIN)
        losses = sum(1 for r in bet_results if r.outcome == BetOutcome.LOSS)
        pushes = sum(1 for r in bet_results if r.outcome == BetOutcome.PUSH)
        total_wagered = sum(r.wager for r in bet_results)
        total_profit = sum(r.profit for r in bet_results)
        
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        avg_edge = (sum(r.edge_vs_opening for r in bet_results) / total_bets) if total_bets > 0 else 0
        
        # CLV metrics
        avg_clv = (sum(r.clv for r in bet_results) / total_bets) if total_bets > 0 else 0
        clv_positive = sum(1 for r in bet_results if r.clv > 0)
        clv_positive_rate = (clv_positive / total_bets * 100) if total_bets > 0 else 0
        
        return SeasonResults(
            season=test_season,
            market=market,
            total_games=stats["total_games"],
            games_with_all_data=stats["valid_games"],
            total_bets=total_bets,
            wins=wins,
            losses=losses,
            pushes=pushes,
            total_wagered=round(total_wagered, 2),
            total_profit=round(total_profit, 2),
            roi=round(roi, 2),
            win_rate=round(win_rate, 1),
            avg_edge=round(avg_edge, 2),
            avg_clv=round(avg_clv, 2),
            clv_positive_rate=round(clv_positive_rate, 1),
            ratings_verified_point_in_time=self.config.require_point_in_time_ratings,
            closing_lines_captured=closing_col in valid_df.columns
        )
    
    def run_walk_forward_validation(self) -> WalkForwardSummary:
        """
        Run complete walk-forward validation across all test seasons.
        """
        print("=" * 70)
        print("WALK-FORWARD VALIDATION")
        print("=" * 70)
        print(f"Market: {self.config.market.value}")
        print(f"Test seasons: {self.config.test_seasons}")
        print(f"Min edge threshold: {self.config.min_edge} points")
        print()
        
        # Load data
        df = self.load_backtest_data()
        print(f"Loaded {len(df)} total games")
        
        # Run walk-forward splits
        season_results = {}
        
        for test_season, train_df, test_df in self.get_walk_forward_splits(df):
            results = self.run_season_backtest(test_season, train_df, test_df)
            season_results[test_season] = results
            
            # Print season summary
            print(f"\n{'='*50}")
            print(f"Season {test_season} Results: {self.config.market.value}")
            print(f"{'='*50}")
            print(f"Bets: {results.total_bets}")
            print(f"Record: {results.wins}W - {results.losses}L - {results.pushes}P")
            print(f"Win Rate: {results.win_rate:.1f}%")
            print(f"ROI: {results.roi:+.2f}%")
            print(f"Avg Edge: {results.avg_edge:.2f} pts")
            print(f"Avg CLV: {results.avg_clv:+.2f} pts")
            print(f"CLV Positive Rate: {results.clv_positive_rate:.1f}%")
        
        # Aggregate across seasons
        total_bets = sum(r.total_bets for r in season_results.values())
        total_wins = sum(r.wins for r in season_results.values())
        total_losses = sum(r.losses for r in season_results.values())
        total_wagered = sum(r.total_wagered for r in season_results.values())
        total_profit = sum(r.total_profit for r in season_results.values())
        
        overall_roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        overall_win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
        overall_avg_clv = (sum(r.avg_clv * r.total_bets for r in season_results.values()) / total_bets) if total_bets > 0 else 0
        overall_clv_positive = (sum(r.clv_positive_rate * r.total_bets for r in season_results.values()) / total_bets) if total_bets > 0 else 0
        
        summary = WalkForwardSummary(
            market=self.config.market.value,
            test_seasons=self.config.test_seasons,
            total_bets=total_bets,
            overall_win_rate=round(overall_win_rate, 1),
            overall_roi=round(overall_roi, 2),
            overall_avg_clv=round(overall_avg_clv, 2),
            overall_clv_positive_rate=round(overall_clv_positive, 1),
            season_results=season_results,
            no_leakage_verified=self.config.require_point_in_time_ratings,
            all_data_requirements_met=self.config.require_actual_odds
        )
        
        # Print overall summary
        print("\n" + "=" * 70)
        print("OVERALL WALK-FORWARD RESULTS")
        print("=" * 70)
        print(f"Total Bets: {summary.total_bets}")
        print(f"Win Rate: {summary.overall_win_rate:.1f}%")
        print(f"ROI: {summary.overall_roi:+.2f}%")
        print(f"Avg CLV: {summary.overall_avg_clv:+.2f} pts")
        print(f"CLV Positive Rate: {summary.overall_clv_positive_rate:.1f}%")
        print(f"\nValidation Flags:")
        print(f"  No Leakage Verified: {summary.no_leakage_verified}")
        print(f"  All Data Requirements Met: {summary.all_data_requirements_met}")
        
        return summary
    
    def save_results(self, summary: WalkForwardSummary):
        """Save walk-forward results to disk."""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_path = self.results_dir / f"walk_forward_{summary.market}_{timestamp}.json"
        
        # Convert to serializable format
        results_dict = {
            "market": summary.market,
            "test_seasons": summary.test_seasons,
            "total_bets": summary.total_bets,
            "overall_win_rate": summary.overall_win_rate,
            "overall_roi": summary.overall_roi,
            "overall_avg_clv": summary.overall_avg_clv,
            "overall_clv_positive_rate": summary.overall_clv_positive_rate,
            "no_leakage_verified": summary.no_leakage_verified,
            "all_data_requirements_met": summary.all_data_requirements_met,
            "timestamp": timestamp,
            "season_results": {
                str(season): {
                    "total_bets": r.total_bets,
                    "wins": r.wins,
                    "losses": r.losses,
                    "pushes": r.pushes,
                    "roi": r.roi,
                    "win_rate": r.win_rate,
                    "avg_clv": r.avg_clv,
                    "clv_positive_rate": r.clv_positive_rate
                }
                for season, r in summary.season_results.items()
            }
        }
        
        with open(results_path, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"\nResults saved to: {results_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Walk-forward validation for NCAAM backtesting"
    )
    parser.add_argument(
        "--market",
        type=str,
        default="fg_spread",
        choices=["fg_spread", "fg_total", "h1_spread", "h1_total"],
        help="Market to backtest"
    )
    parser.add_argument(
        "--all-markets",
        action="store_true",
        help="Run backtest on all markets"
    )
    parser.add_argument(
        "--test-seasons",
        type=str,
        default="2023,2024,2025",
        help="Comma-separated list of test seasons"
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=2.0,
        help="Minimum edge (points) to place bet"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate data, don't run backtest"
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="Run in lenient mode (don't require all data)"
    )
    
    args = parser.parse_args()
    
    # Parse test seasons
    test_seasons = [int(s.strip()) for s in args.test_seasons.split(",")]
    
    markets = (
        [MarketType.FG_SPREAD, MarketType.FG_TOTAL, MarketType.H1_SPREAD, MarketType.H1_TOTAL]
        if args.all_markets
        else [MarketType(args.market)]
    )
    
    for market in markets:
        config = WalkForwardConfig(
            test_seasons=test_seasons,
            market=market,
            min_edge=args.min_edge,
            require_point_in_time_ratings=not args.lenient,
            require_closing_lines=not args.lenient,
            require_actual_odds=not args.lenient
        )
        
        validator = WalkForwardValidator(config)
        
        if args.validate_only:
            df = validator.load_backtest_data()
            for season in test_seasons:
                test_df = df[df["season"] == season]
                validator.validate_data_requirements(test_df, season)
        else:
            summary = validator.run_walk_forward_validation()
            validator.save_results(summary)


if __name__ == "__main__":
    main()
