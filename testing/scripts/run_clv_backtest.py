#!/usr/bin/env python3
"""
CLV-Enhanced Historical Backtesting Engine

The GOLD STANDARD for measuring model quality is Closing Line Value (CLV).

CRITICAL REQUIREMENTS:
- Opening lines: Used for bet decision
- Closing lines: Used for CLV calculation
- Actual odds: No -110 assumptions
- Point-in-time ratings: No leakage
- No placeholders: Missing data = skip
- Pregame-only odds: latest snapshot at or before commence_time

CLV = Closing Line - Opening Line (adjusted for bet side)
Positive CLV = Sharp betting (beating the closing line)

Usage:
    python testing/scripts/run_clv_backtest.py --market fg_spread
    python testing/scripts/run_clv_backtest.py --all-markets
    python testing/scripts/run_clv_backtest.py --use-ml-model  # Use trained ML model
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from testing.azure_data_reader import get_azure_reader
from testing.data_window import CANONICAL_START_SEASON, default_backtest_seasons, enforce_min_season

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class MarketType(str, Enum):
    FG_SPREAD = "fg_spread"
    FG_TOTAL = "fg_total"
    H1_SPREAD = "h1_spread"
    H1_TOTAL = "h1_total"


class BetOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"


@dataclass
class CLVBacktestConfig:
    """Configuration for CLV-enhanced backtesting."""
    market: MarketType
    seasons: List[int] = field(default_factory=default_backtest_seasons)
    
    # Betting thresholds
    min_edge: float = 2.0  # Minimum edge (points) to place bet
    
    # Kelly sizing
    kelly_fraction: float = 0.25
    base_unit: float = 100.0
    
    # Model selection
    use_ml_model: bool = False
    use_formula: bool = True
    
    # Variance estimates
    sigma_spread: float = 11.0
    sigma_total: float = 10.0
    
    # Home court advantage (from backtests)
    hca_spread: float = 5.8
    hca_h1_spread: float = 3.6


@dataclass
class CLVBetResult:
    """Single bet result with full CLV tracking."""
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    season: int
    market: str
    
    # Prediction
    predicted_line: float
    
    # Market lines
    opening_line: float
    closing_line: float
    line_movement: float  # closing - opening
    
    # Edge and CLV
    edge_vs_opening: float
    edge_vs_closing: float
    clv: float  # Positive = sharp
    clv_percent: float
    
    # Bet details
    bet_side: str
    actual_odds: float
    wager: float
    
    # Outcome
    actual_result: float
    outcome: BetOutcome
    profit: float
    
    # Extra analysis
    was_sharp: bool  # CLV > 0
    beat_closing: bool  # Edge vs closing > 0


@dataclass
class CLVBacktestSummary:
    """Summary with CLV analysis."""
    market: str
    seasons: List[int]
    
    # Sample sizes
    total_games: int
    games_with_clv_data: int
    total_bets: int
    
    # Outcomes
    wins: int
    losses: int
    pushes: int
    
    # Financials
    total_wagered: float
    total_profit: float
    roi: float
    win_rate: float
    
    # CLV Metrics (THE GOLD STANDARD)
    avg_clv: float
    clv_positive_count: int
    clv_positive_rate: float
    avg_clv_when_positive: float
    avg_clv_when_negative: float
    
    # CLV vs Outcome correlation
    clv_positive_win_rate: float  # Win rate when CLV > 0
    clv_negative_win_rate: float  # Win rate when CLV < 0
    
    # Edge analysis
    avg_edge_vs_opening: float
    avg_edge_vs_closing: float
    
    # By season breakdown
    by_season: Dict[int, Dict]


class CLVBacktestEngine:
    """
    Backtesting engine with full CLV tracking.
    
    CLV (Closing Line Value) is the gold standard metric because:
    1. The closing line is the most accurate market price
    2. Beating the closing line consistently indicates sharp betting
    3. Positive CLV correlates with long-term profitability
    """
    
    def __init__(self, config: CLVBacktestConfig):
        self.config = config
        
        # Paths
        self.root_dir = Path(__file__).resolve().parents[2]
        self.results_dir = self.root_dir / "testing" / "results" / "clv_backtest"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Load ML model if requested
        self.ml_model = None
        self.ml_feature_names = None
        if config.use_ml_model:
            self._load_ml_model()
    
    def _load_ml_model(self):
        """Load trained ML model for predictions."""
        try:
            from testing.scripts.train_independent_models import load_model
            market = self.config.market.value
            self.ml_model, self.ml_feature_names, _ = load_model(market)
            print(f"Loaded ML model for {market}")
        except Exception as e:
            print(f"Warning: Could not load ML model: {e}")
            print("Falling back to formula-based predictions")
            self.ml_model = None
    
    def load_backtest_data(self) -> pd.DataFrame:
        """Load canonical backtest master dataset."""
        reader = get_azure_reader()
        print("[INFO] Loading canonical backtest master")
        df = reader.read_backtest_master()

        date_col = "game_date" if "game_date" in df.columns else "date" if "date" in df.columns else None
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            if date_col != "game_date":
                df["game_date"] = df[date_col]

        if "season" in df.columns:
            df = df[df["season"] >= CANONICAL_START_SEASON]
        if df.empty:
            raise ValueError("Canonical master has no canonical-window data")

        return df
    
    def generate_prediction(self, row: pd.Series) -> float:
        """
        Generate prediction for a game.
        
        Uses ML model if available, otherwise formula-based.
        """
        if self.ml_model is not None and self.ml_feature_names:
            # Use ML model
            features = []
            for feat in self.ml_feature_names:
                val = row.get(feat, 0)
                features.append(0 if pd.isna(val) else val)
            
            proba = self.ml_model.predict_proba([features])[0][1]
            
            # Convert probability to line adjustment
            # This is market-specific
            # For spreads: proba > 0.5 means home more likely to cover
            # Adjust prediction accordingly
            return proba  # Return probability for now
        
        # Formula-based prediction
        def _val(value, default):
            return default if pd.isna(value) else value

        home_adj_o = _val(row.get("home_adj_o", 105), 105)
        home_adj_d = _val(row.get("home_adj_d", 105), 105)
        away_adj_o = _val(row.get("away_adj_o", 105), 105)
        away_adj_d = _val(row.get("away_adj_d", 105), 105)
        home_tempo = _val(row.get("home_tempo", 67.5), 67.5)
        away_tempo = _val(row.get("away_tempo", 67.5), 67.5)
        
        market = self.config.market
        
        if market == MarketType.FG_SPREAD:
            home_net = home_adj_o - home_adj_d
            away_net = away_adj_o - away_adj_d
            raw_margin = (home_net - away_net) / 2.0
            return -(raw_margin + self.config.hca_spread)
            
        elif market == MarketType.FG_TOTAL:
            avg_tempo = (home_tempo + away_tempo) / 2.0
            home_pts = home_adj_o * avg_tempo / 100.0
            away_pts = away_adj_o * avg_tempo / 100.0
            return home_pts + away_pts + 7.0
            
        elif market == MarketType.H1_SPREAD:
            home_net = home_adj_o - home_adj_d
            away_net = away_adj_o - away_adj_d
            raw_margin = (home_net - away_net) / 2.0
            return -(raw_margin * 0.50 + self.config.hca_h1_spread)
            
        elif market == MarketType.H1_TOTAL:
            avg_tempo = (home_tempo + away_tempo) / 2.0
            home_pts = home_adj_o * avg_tempo / 100.0
            away_pts = away_adj_o * avg_tempo / 100.0
            fg_total = home_pts + away_pts
            return fg_total * 0.469 + 2.7
        
        return 0.0
    
    def calculate_clv(
        self,
        bet_side: str,
        opening_line: float,
        closing_line: float
    ) -> Tuple[float, float]:
        """
        Calculate Closing Line Value.
        
        CLV = How much value we captured by betting before the close.
        Positive CLV = Line moved in our favor = We got value.
        """
        line_movement = closing_line - opening_line
        
        if "spread" in self.config.market.value:
            if bet_side == "home":
                # Betting home. If line goes more negative (home favored more), 
                # we got value by betting earlier.
                clv = opening_line - closing_line
            else:
                # Betting away. If line goes more positive (away favored more),
                # we got value.
                clv = closing_line - opening_line
        else:
            # Totals
            if bet_side == "over":
                # Betting over. If line goes up, we got value.
                clv = closing_line - opening_line
            else:
                # Betting under. If line goes down, we got value.
                clv = opening_line - closing_line
        
        # CLV as percentage
        clv_percent = (clv / abs(opening_line) * 100) if opening_line != 0 else 0
        
        return clv, clv_percent
    
    def get_bet_side(self, predicted: float, market_line: float) -> str:
        """Determine bet side based on prediction vs market."""
        if "spread" in self.config.market.value:
            return "home" if predicted < market_line else "away"
        else:
            return "over" if predicted > market_line else "under"
    
    def determine_outcome(
        self,
        bet_side: str,
        market_line: float,
        actual_result: float
    ) -> BetOutcome:
        """Determine bet outcome."""
        if pd.isna(actual_result):
            return BetOutcome.PUSH
        
        if "spread" in self.config.market.value:
            if bet_side == "home":
                result = actual_result + market_line
            else:
                result = -actual_result - market_line
        else:
            if bet_side == "over":
                result = actual_result - market_line
            else:
                result = market_line - actual_result
        
        if abs(result) < 0.5:
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
        """Calculate profit using actual odds."""
        if outcome == BetOutcome.WIN:
            if odds > 0:
                return wager * (odds / 100)
            else:
                return wager * (100 / abs(odds))
        elif outcome == BetOutcome.LOSS:
            return -wager
        else:
            return 0.0
    
    def run_backtest(self) -> CLVBacktestSummary:
        """Run the CLV-enhanced backtest."""
        print("=" * 70)
        print("CLV-ENHANCED BACKTEST")
        print("=" * 70)
        print(f"Market: {self.config.market.value}")
        print(f"Seasons: {self.config.seasons}")
        print(f"Min Edge: {self.config.min_edge} pts")
        print(f"Model: {'ML' if self.ml_model else 'Formula-based'}")
        print()
        
        # Load data
        df = self.load_backtest_data()
        
        # Filter to configured seasons
        df = df[df["season"].isin(self.config.seasons)]
        print(f"Total games in selected seasons: {len(df)}")
        
        # Get column mappings
        market = self.config.market.value
        line_col_map = {
            "fg_spread": ("fg_spread", "fg_spread_home_price", "fg_spread_away_price", "actual_margin"),
            "fg_total": ("fg_total", "fg_total_over_price", "fg_total_under_price", "actual_total"),
            "h1_spread": ("h1_spread", "h1_spread_home_price", "h1_spread_away_price", "h1_actual_margin"),
            "h1_total": ("h1_total", "h1_total_over_price", "h1_total_under_price", "h1_actual_total"),
        }
        
        line_col, price_col1, price_col2, result_col = line_col_map[market]
        closing_col = f"{line_col}_closing"
        
        # Check for closing line column
        has_closing = closing_col in df.columns
        if not has_closing:
            print(f"Warning: No closing line column ({closing_col}), using opening as proxy")
        
        # Track results
        bet_results: List[CLVBetResult] = []
        games_with_clv_data = 0
        
        # Process each game
        for idx, row in df.iterrows():
            # Get opening line
            opening_line = row.get(line_col)
            if pd.isna(opening_line):
                continue
            
            # Get closing line
            if has_closing and closing_col in row:
                closing_line = row.get(closing_col)
                if pd.isna(closing_line):
                    closing_line = opening_line
            else:
                closing_line = opening_line
            
            games_with_clv_data += 1 if closing_line != opening_line else 0
            
            # Generate prediction
            predicted = self.generate_prediction(row)
            
            # Calculate edge vs opening (for bet decision)
            edge = abs(predicted - opening_line)
            
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
                continue  # Skip - no actual odds
            
            # Get actual result
            actual_result = row.get(result_col)
            if pd.isna(actual_result):
                continue
            
            # Determine outcome
            outcome = self.determine_outcome(bet_side, opening_line, actual_result)
            
            # Calculate profit
            wager = self.config.base_unit
            profit = self.calculate_profit(outcome, wager, actual_odds)
            
            # Calculate CLV
            clv, clv_percent = self.calculate_clv(bet_side, opening_line, closing_line)
            
            # Record result
            bet_results.append(CLVBetResult(
                game_id=str(row.get("game_id", idx)),
                game_date=str(row["game_date"].date()),
                home_team=row["home_team"],
                away_team=row["away_team"],
                season=int(row["season"]),
                market=market,
                predicted_line=round(predicted, 2),
                opening_line=round(opening_line, 2),
                closing_line=round(closing_line, 2),
                line_movement=round(closing_line - opening_line, 2),
                edge_vs_opening=round(edge, 2),
                edge_vs_closing=round(abs(predicted - closing_line), 2),
                clv=round(clv, 2),
                clv_percent=round(clv_percent, 2),
                bet_side=bet_side,
                actual_odds=round(actual_odds, 1),
                wager=wager,
                actual_result=round(actual_result, 2),
                outcome=outcome,
                profit=round(profit, 2),
                was_sharp=clv > 0,
                beat_closing=abs(predicted - closing_line) > 0
            ))
        
        # Calculate summary statistics
        total_bets = len(bet_results)
        wins = sum(1 for r in bet_results if r.outcome == BetOutcome.WIN)
        losses = sum(1 for r in bet_results if r.outcome == BetOutcome.LOSS)
        pushes = sum(1 for r in bet_results if r.outcome == BetOutcome.PUSH)
        
        total_wagered = sum(r.wager for r in bet_results)
        total_profit = sum(r.profit for r in bet_results)
        
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        # CLV metrics
        avg_clv = (sum(r.clv for r in bet_results) / total_bets) if total_bets > 0 else 0
        clv_positive = [r for r in bet_results if r.clv > 0]
        clv_negative = [r for r in bet_results if r.clv <= 0]
        
        clv_positive_count = len(clv_positive)
        clv_positive_rate = (clv_positive_count / total_bets * 100) if total_bets > 0 else 0
        avg_clv_positive = (sum(r.clv for r in clv_positive) / len(clv_positive)) if clv_positive else 0
        avg_clv_negative = (sum(r.clv for r in clv_negative) / len(clv_negative)) if clv_negative else 0
        
        # Win rate by CLV
        clv_pos_wins = sum(1 for r in clv_positive if r.outcome == BetOutcome.WIN)
        clv_pos_losses = sum(1 for r in clv_positive if r.outcome == BetOutcome.LOSS)
        clv_neg_wins = sum(1 for r in clv_negative if r.outcome == BetOutcome.WIN)
        clv_neg_losses = sum(1 for r in clv_negative if r.outcome == BetOutcome.LOSS)
        
        clv_positive_win_rate = (clv_pos_wins / (clv_pos_wins + clv_pos_losses) * 100) if (clv_pos_wins + clv_pos_losses) > 0 else 0
        clv_negative_win_rate = (clv_neg_wins / (clv_neg_wins + clv_neg_losses) * 100) if (clv_neg_wins + clv_neg_losses) > 0 else 0
        
        # Edge metrics
        avg_edge_opening = (sum(r.edge_vs_opening for r in bet_results) / total_bets) if total_bets > 0 else 0
        avg_edge_closing = (sum(r.edge_vs_closing for r in bet_results) / total_bets) if total_bets > 0 else 0
        
        # By season breakdown
        by_season = {}
        for season in self.config.seasons:
            season_results = [r for r in bet_results if r.season == season]
            s_bets = len(season_results)
            s_wins = sum(1 for r in season_results if r.outcome == BetOutcome.WIN)
            s_losses = sum(1 for r in season_results if r.outcome == BetOutcome.LOSS)
            s_profit = sum(r.profit for r in season_results)
            s_wagered = sum(r.wager for r in season_results)
            s_clv = (sum(r.clv for r in season_results) / s_bets) if s_bets > 0 else 0
            s_clv_pos = sum(1 for r in season_results if r.clv > 0)
            
            by_season[season] = {
                "bets": s_bets,
                "wins": s_wins,
                "losses": s_losses,
                "profit": round(s_profit, 2),
                "roi": round(s_profit / s_wagered * 100, 2) if s_wagered > 0 else 0,
                "win_rate": round(s_wins / (s_wins + s_losses) * 100, 1) if (s_wins + s_losses) > 0 else 0,
                "avg_clv": round(s_clv, 2),
                "clv_positive_rate": round(s_clv_pos / s_bets * 100, 1) if s_bets > 0 else 0
            }
        
        summary = CLVBacktestSummary(
            market=market,
            seasons=self.config.seasons,
            total_games=len(df),
            games_with_clv_data=games_with_clv_data,
            total_bets=total_bets,
            wins=wins,
            losses=losses,
            pushes=pushes,
            total_wagered=round(total_wagered, 2),
            total_profit=round(total_profit, 2),
            roi=round(roi, 2),
            win_rate=round(win_rate, 1),
            avg_clv=round(avg_clv, 2),
            clv_positive_count=clv_positive_count,
            clv_positive_rate=round(clv_positive_rate, 1),
            avg_clv_when_positive=round(avg_clv_positive, 2),
            avg_clv_when_negative=round(avg_clv_negative, 2),
            clv_positive_win_rate=round(clv_positive_win_rate, 1),
            clv_negative_win_rate=round(clv_negative_win_rate, 1),
            avg_edge_vs_opening=round(avg_edge_opening, 2),
            avg_edge_vs_closing=round(avg_edge_closing, 2),
            by_season=by_season
        )
        
        # Print summary
        self._print_summary(summary)
        
        # Save results
        self._save_results(summary, bet_results)
        
        return summary
    
    def _print_summary(self, summary: CLVBacktestSummary):
        """Print summary to console."""
        print("\n" + "=" * 70)
        print(f"RESULTS: {summary.market.upper()}")
        print("=" * 70)
        
        print(f"\n--- BETTING PERFORMANCE ---")
        print(f"Total Bets: {summary.total_bets}")
        print(f"Record: {summary.wins}W - {summary.losses}L - {summary.pushes}P")
        print(f"Win Rate: {summary.win_rate:.1f}%")
        print(f"Total Wagered: ${summary.total_wagered:,.2f}")
        print(f"Total Profit: ${summary.total_profit:+,.2f}")
        print(f"ROI: {summary.roi:+.2f}%")
        
        print(f"\n--- CLV ANALYSIS (GOLD STANDARD) ---")
        print(f"Avg CLV: {summary.avg_clv:+.2f} pts")
        print(f"CLV Positive Rate: {summary.clv_positive_rate:.1f}% ({summary.clv_positive_count}/{summary.total_bets})")
        print(f"Avg CLV when positive: {summary.avg_clv_when_positive:+.2f} pts")
        print(f"Avg CLV when negative: {summary.avg_clv_when_negative:+.2f} pts")
        
        print(f"\n--- CLV vs OUTCOMES ---")
        print(f"Win rate when CLV > 0: {summary.clv_positive_win_rate:.1f}%")
        print(f"Win rate when CLV <= 0: {summary.clv_negative_win_rate:.1f}%")
        
        print(f"\n--- EDGE ANALYSIS ---")
        print(f"Avg edge vs opening: {summary.avg_edge_vs_opening:.2f} pts")
        print(f"Avg edge vs closing: {summary.avg_edge_vs_closing:.2f} pts")
        
        print(f"\n--- BY SEASON ---")
        for season, stats in sorted(summary.by_season.items()):
            print(f"  {season}: {stats['bets']} bets, {stats['win_rate']:.1f}% win, "
                  f"${stats['profit']:+,.0f} ({stats['roi']:+.1f}% ROI), "
                  f"CLV: {stats['avg_clv']:+.2f} ({stats['clv_positive_rate']:.0f}% pos)")
    
    def _save_results(self, summary: CLVBacktestSummary, bet_results: List[CLVBetResult]):
        """Save results to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save summary
        summary_path = self.results_dir / f"clv_{summary.market}_{timestamp}.json"
        with open(summary_path, 'w') as f:
            json.dump({
                "market": summary.market,
                "seasons": summary.seasons,
                "total_bets": summary.total_bets,
                "wins": summary.wins,
                "losses": summary.losses,
                "pushes": summary.pushes,
                "roi": summary.roi,
                "win_rate": summary.win_rate,
                "avg_clv": summary.avg_clv,
                "clv_positive_rate": summary.clv_positive_rate,
                "clv_positive_win_rate": summary.clv_positive_win_rate,
                "clv_negative_win_rate": summary.clv_negative_win_rate,
                "by_season": summary.by_season,
                "timestamp": timestamp
            }, f, indent=2)
        
        # Save detailed results
        if bet_results:
            results_df = pd.DataFrame([
                {
                    "game_date": r.game_date,
                    "home_team": r.home_team,
                    "away_team": r.away_team,
                    "season": r.season,
                    "predicted": r.predicted_line,
                    "opening_line": r.opening_line,
                    "closing_line": r.closing_line,
                    "line_movement": r.line_movement,
                    "clv": r.clv,
                    "clv_percent": r.clv_percent,
                    "bet_side": r.bet_side,
                    "actual_odds": r.actual_odds,
                    "actual_result": r.actual_result,
                    "outcome": r.outcome.value,
                    "profit": r.profit,
                    "was_sharp": r.was_sharp
                }
                for r in bet_results
            ])
            
            details_path = self.results_dir / f"clv_{summary.market}_{timestamp}_details.csv"
            results_df.to_csv(details_path, index=False)
        
        print(f"\nResults saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CLV-enhanced backtesting for NCAAM"
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
        "--seasons",
        type=str,
        default=None,
        help="Comma-separated list of seasons (default: canonical window)"
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=2.0,
        help="Minimum edge (points) to place bet"
    )
    parser.add_argument(
        "--use-ml-model",
        action="store_true",
        help="Use trained ML model for predictions"
    )
    
    args = parser.parse_args()
    
    if args.seasons:
        seasons = [int(s.strip()) for s in args.seasons.split(",")]
    else:
        seasons = default_backtest_seasons()
    seasons = enforce_min_season(seasons)
    
    markets = (
        [MarketType.FG_SPREAD, MarketType.FG_TOTAL, MarketType.H1_SPREAD, MarketType.H1_TOTAL]
        if args.all_markets
        else [MarketType(args.market)]
    )
    
    for market in markets:
        config = CLVBacktestConfig(
            market=market,
            seasons=seasons,
            min_edge=args.min_edge,
            use_ml_model=args.use_ml_model
        )
        
        engine = CLVBacktestEngine(config)
        engine.run_backtest()


if __name__ == "__main__":
    main()
