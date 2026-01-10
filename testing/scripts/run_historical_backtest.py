#!/usr/bin/env python3
"""
NCAAM Historical Backtesting Engine

Runs backtests using ACTUAL historical game outcomes from backtest_master.csv.
Unlike run_backtest.py which simulates games, this uses real results.

Usage:
    python testing/scripts/run_historical_backtest.py --market fg_spread
    python testing/scripts/run_historical_backtest.py --market h1_total --seasons 2022,2023,2024
    python testing/scripts/run_historical_backtest.py --all-markets
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# Paths
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "ncaam_historical_data_local" / "backtest_datasets"
RESULTS_DIR = ROOT_DIR / "testing" / "results" / "historical"


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


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""
    market: MarketType
    seasons: List[int]
    min_edge: float = 1.5  # Minimum edge (%) to place bet
    kelly_fraction: float = 0.25  # Fractional Kelly
    base_unit: float = 100.0  # Base bet size
    max_kelly: float = 0.10  # Max Kelly fraction
    sigma_spread: float = 11.0  # Std dev for spreads
    sigma_total: float = 8.0  # Std dev for totals
    hca_spread: float = 3.0  # Home court advantage for spread
    hca_total: float = 0.0  # HCA for total (zero-sum)


@dataclass
class BetResult:
    """Result of a single bet."""
    game_date: str
    home_team: str
    away_team: str
    season: int
    market: str
    predicted_line: float
    market_line: float
    edge: float
    bet_side: str
    actual_result: float
    outcome: BetOutcome
    wager: float
    profit: float


@dataclass
class BacktestSummary:
    """Summary statistics for a backtest run."""
    market: str
    seasons: List[int]
    total_games: int
    games_with_odds: int
    games_with_ratings: int
    total_bets: int
    wins: int
    losses: int
    pushes: int
    total_wagered: float
    total_profit: float
    roi: float
    win_rate: float
    avg_edge: float
    by_season: Dict[int, Dict] = field(default_factory=dict)


class NCAAMPredictor:
    """
    Generates predictions using Barttorvik ratings.
    Replicates v6.1 prediction formulas.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config

    def predict_spread(
        self,
        home_adj_o: float,
        home_adj_d: float,
        away_adj_o: float,
        away_adj_d: float,
        is_neutral: bool = False
    ) -> float:
        """Predict spread (home perspective, negative = home favored)."""
        home_net = home_adj_o - home_adj_d
        away_net = away_adj_o - away_adj_d
        raw_margin = (home_net - away_net) / 2.0
        
        hca = 0.0 if is_neutral else self.config.hca_spread
        return -(raw_margin + hca)  # Negative = home favored

    def predict_total(
        self,
        home_adj_o: float,
        home_adj_d: float,
        home_tempo: float,
        away_adj_o: float,
        away_adj_d: float,
        away_tempo: float,
        is_neutral: bool = False
    ) -> float:
        """Predict total points."""
        avg_tempo = (home_tempo + away_tempo) / 2.0
        home_score = home_adj_o * avg_tempo / 100.0
        away_score = away_adj_o * avg_tempo / 100.0
        
        hca = 0.0 if is_neutral else self.config.hca_total
        return home_score + away_score + hca

    def predict_h1_spread(
        self,
        home_adj_o: float,
        home_adj_d: float,
        away_adj_o: float,
        away_adj_d: float,
        is_neutral: bool = False
    ) -> float:
        """Predict 1H spread (50% of FG)."""
        fg_spread = self.predict_spread(
            home_adj_o, home_adj_d, away_adj_o, away_adj_d, is_neutral
        )
        # H1 is approximately 50% of FG spread
        return fg_spread * 0.5

    def predict_h1_total(
        self,
        home_adj_o: float,
        home_adj_d: float,
        home_tempo: float,
        away_adj_o: float,
        away_adj_d: float,
        away_tempo: float,
        is_neutral: bool = False
    ) -> float:
        """Predict 1H total (48% of FG)."""
        fg_total = self.predict_total(
            home_adj_o, home_adj_d, home_tempo,
            away_adj_o, away_adj_d, away_tempo, is_neutral
        )
        return fg_total * 0.48

    def calculate_edge(self, predicted: float, market: float, market_type: MarketType) -> float:
        """
        Calculate edge as percentage.
        
        For spreads: Edge = |predicted - market| as % of sigma
        For totals: Similar calculation
        """
        sigma = self.config.sigma_spread if "spread" in market_type.value else self.config.sigma_total
        edge_points = abs(predicted - market)
        return (edge_points / sigma) * 100

    def get_bet_side(self, predicted: float, market: float, market_type: MarketType) -> str:
        """Determine which side to bet."""
        if "spread" in market_type.value:
            # For spreads: if predicted < market, bet home (cover more)
            return "home" if predicted < market else "away"
        else:
            # For totals: if predicted > market, bet over
            return "over" if predicted > market else "under"


def load_backtest_data() -> pd.DataFrame:
    """Load the master backtest dataset."""
    path = DATA_DIR / "backtest_master.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Backtest data not found at {path}\n"
            "Run: python testing/scripts/build_backtest_dataset.py"
        )
    
    df = pd.read_csv(path)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def determine_outcome(
    bet_side: str,
    market_line: float,
    actual_result: float,
    market_type: MarketType
) -> BetOutcome:
    """Determine if a bet won, lost, or pushed."""
    if "spread" in market_type.value:
        # For spreads: actual_result is actual_margin (home - away)
        if bet_side == "home":
            # Bet on home to cover: need actual_margin > -market_line
            # If market_line = -5 (home favored by 5), need margin > 5
            diff = actual_result - (-market_line)
        else:
            # Bet on away to cover: need -actual_margin > market_line
            diff = -actual_result - market_line
    else:
        # For totals: actual_result is actual_total
        if bet_side == "over":
            diff = actual_result - market_line
        else:
            diff = market_line - actual_result
    
    if abs(diff) < 0.001:  # Push
        return BetOutcome.PUSH
    elif diff > 0:
        return BetOutcome.WIN
    else:
        return BetOutcome.LOSS


def calculate_profit(outcome: BetOutcome, wager: float) -> float:
    """Calculate profit from bet outcome (assuming -110 juice)."""
    if outcome == BetOutcome.WIN:
        return wager * 0.909  # Win pays ~0.91x (at -110)
    elif outcome == BetOutcome.LOSS:
        return -wager
    else:
        return 0.0  # Push


def run_backtest(config: BacktestConfig) -> BacktestSummary:
    """Run backtest for a single market."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING: {config.market.value.upper()}")
    print(f"Seasons: {config.seasons}")
    print(f"Min Edge: {config.min_edge}%")
    print(f"{'='*60}")
    
    # Load data
    df = load_backtest_data()
    
    # Filter to requested seasons
    df = df[df["season"].isin(config.seasons)]
    total_games = len(df)
    
    # Determine which columns we need
    if config.market == MarketType.FG_SPREAD:
        line_col = "fg_spread"
        result_col = "actual_margin"
    elif config.market == MarketType.FG_TOTAL:
        line_col = "fg_total"
        result_col = "actual_total"
    elif config.market == MarketType.H1_SPREAD:
        line_col = "h1_spread"
        # For H1, we'd need H1 scores - using FG margin * 0.5 as proxy
        result_col = "actual_margin"  # Will scale in outcome
    else:  # H1_TOTAL
        line_col = "h1_total"
        result_col = "actual_total"  # Will scale in outcome
    
    # Filter to games with required data
    has_odds = df[line_col].notna()
    has_ratings = df["home_adj_o"].notna() & df["away_adj_o"].notna()
    
    games_with_odds = has_odds.sum()
    games_with_ratings = has_ratings.sum()
    
    # Need both odds and ratings
    valid = has_odds & has_ratings
    df_valid = df[valid].copy()
    
    print(f"\nData Summary:")
    print(f"  Total games in seasons: {total_games:,}")
    print(f"  Games with {line_col}: {games_with_odds:,}")
    print(f"  Games with ratings: {games_with_ratings:,}")
    print(f"  Games with both: {len(df_valid):,}")
    
    # Run predictions
    predictor = NCAAMPredictor(config)
    results: List[BetResult] = []
    
    for _, row in df_valid.iterrows():
        # Generate prediction
        if config.market == MarketType.FG_SPREAD:
            predicted = predictor.predict_spread(
                row["home_adj_o"], row["home_adj_d"],
                row["away_adj_o"], row["away_adj_d"]
            )
        elif config.market == MarketType.FG_TOTAL:
            predicted = predictor.predict_total(
                row["home_adj_o"], row["home_adj_d"], row.get("home_tempo", 68),
                row["away_adj_o"], row["away_adj_d"], row.get("away_tempo", 68)
            )
        elif config.market == MarketType.H1_SPREAD:
            predicted = predictor.predict_h1_spread(
                row["home_adj_o"], row["home_adj_d"],
                row["away_adj_o"], row["away_adj_d"]
            )
        else:  # H1_TOTAL
            predicted = predictor.predict_h1_total(
                row["home_adj_o"], row["home_adj_d"], row.get("home_tempo", 68),
                row["away_adj_o"], row["away_adj_d"], row.get("away_tempo", 68)
            )
        
        market_line = row[line_col]
        edge = predictor.calculate_edge(predicted, market_line, config.market)
        
        # Only bet if edge exceeds minimum
        if edge < config.min_edge:
            continue
        
        bet_side = predictor.get_bet_side(predicted, market_line, config.market)
        
        # Get actual result
        actual = row[result_col]
        if pd.isna(actual):
            continue
        
        # For H1 markets, scale the actual result
        if config.market == MarketType.H1_SPREAD:
            actual = actual * 0.5  # Approximate H1 margin
        elif config.market == MarketType.H1_TOTAL:
            actual = actual * 0.5  # Approximate H1 total
        
        outcome = determine_outcome(bet_side, market_line, actual, config.market)
        
        # Simple flat betting for now
        wager = config.base_unit
        profit = calculate_profit(outcome, wager)
        
        results.append(BetResult(
            game_date=str(row["game_date"].date()),
            home_team=row["home_team"],
            away_team=row["away_team"],
            season=row["season"],
            market=config.market.value,
            predicted_line=round(predicted, 2),
            market_line=round(market_line, 2),
            edge=round(edge, 2),
            bet_side=bet_side,
            actual_result=round(actual, 2),
            outcome=outcome,
            wager=wager,
            profit=round(profit, 2)
        ))
    
    # Calculate summary stats
    total_bets = len(results)
    wins = sum(1 for r in results if r.outcome == BetOutcome.WIN)
    losses = sum(1 for r in results if r.outcome == BetOutcome.LOSS)
    pushes = sum(1 for r in results if r.outcome == BetOutcome.PUSH)
    total_wagered = sum(r.wager for r in results)
    total_profit = sum(r.profit for r in results)
    
    roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    avg_edge = sum(r.edge for r in results) / total_bets if total_bets > 0 else 0
    
    # By-season breakdown
    by_season = {}
    for season in config.seasons:
        season_results = [r for r in results if r.season == season]
        s_bets = len(season_results)
        s_wins = sum(1 for r in season_results if r.outcome == BetOutcome.WIN)
        s_losses = sum(1 for r in season_results if r.outcome == BetOutcome.LOSS)
        s_profit = sum(r.profit for r in season_results)
        s_wagered = sum(r.wager for r in season_results)
        
        by_season[season] = {
            "bets": s_bets,
            "wins": s_wins,
            "losses": s_losses,
            "profit": round(s_profit, 2),
            "roi": round(s_profit / s_wagered * 100, 2) if s_wagered > 0 else 0,
            "win_rate": round(s_wins / (s_wins + s_losses) * 100, 1) if (s_wins + s_losses) > 0 else 0
        }
    
    summary = BacktestSummary(
        market=config.market.value,
        seasons=config.seasons,
        total_games=total_games,
        games_with_odds=games_with_odds,
        games_with_ratings=games_with_ratings,
        total_bets=total_bets,
        wins=wins,
        losses=losses,
        pushes=pushes,
        total_wagered=round(total_wagered, 2),
        total_profit=round(total_profit, 2),
        roi=round(roi, 2),
        win_rate=round(win_rate, 1),
        avg_edge=round(avg_edge, 2),
        by_season=by_season
    )
    
    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS: {config.market.value.upper()}")
    print(f"{'='*60}")
    print(f"Total Bets: {total_bets}")
    print(f"Record: {wins}W - {losses}L - {pushes}P")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Total Wagered: ${total_wagered:,.2f}")
    print(f"Total Profit: ${total_profit:+,.2f}")
    print(f"ROI: {roi:+.2f}%")
    print(f"Avg Edge: {avg_edge:.2f}%")
    
    print(f"\nBy Season:")
    for season, stats in sorted(by_season.items()):
        print(f"  {season}: {stats['bets']} bets, {stats['win_rate']:.1f}% win, ${stats['profit']:+,.0f} ({stats['roi']:+.1f}% ROI)")
    
    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed results
    results_path = RESULTS_DIR / f"{config.market.value}_results_{timestamp}.csv"
    if results:
        results_df = pd.DataFrame([
            {
                "game_date": r.game_date,
                "home_team": r.home_team,
                "away_team": r.away_team,
                "season": r.season,
                "market": r.market,
                "predicted": r.predicted_line,
                "market_line": r.market_line,
                "edge": r.edge,
                "bet_side": r.bet_side,
                "actual": r.actual_result,
                "outcome": r.outcome.value,
                "wager": r.wager,
                "profit": r.profit
            }
            for r in results
        ])
        results_df.to_csv(results_path, index=False)
        print(f"\n[OK] Saved {len(results)} bet results to {results_path.name}")
    
    # Save summary
    summary_path = RESULTS_DIR / f"{config.market.value}_summary_{timestamp}.json"
    with open(summary_path, "w") as f:
        # Convert numpy int64 to Python int for JSON serialization
        by_season_serializable = {
            int(k): {sk: int(sv) if isinstance(sv, (np.integer,)) else sv for sk, sv in v.items()}
            for k, v in summary.by_season.items()
        }
        json.dump({
            "market": summary.market,
            "seasons": [int(s) for s in summary.seasons],
            "total_games": int(summary.total_games),
            "games_with_odds": int(summary.games_with_odds),
            "games_with_ratings": int(summary.games_with_ratings),
            "total_bets": int(summary.total_bets),
            "wins": int(summary.wins),
            "losses": int(summary.losses),
            "pushes": int(summary.pushes),
            "total_wagered": float(summary.total_wagered),
            "total_profit": float(summary.total_profit),
            "roi": float(summary.roi),
            "win_rate": float(summary.win_rate),
            "avg_edge": float(summary.avg_edge),
            "by_season": by_season_serializable,
            "timestamp": timestamp
        }, f, indent=2)
    print(f"[OK] Saved summary to {summary_path.name}")
    
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run historical NCAAM backtest")
    parser.add_argument(
        "--market",
        choices=["fg_spread", "fg_total", "h1_spread", "h1_total"],
        default="fg_spread",
        help="Market to backtest"
    )
    parser.add_argument(
        "--seasons",
        default="2021,2022,2023,2024,2025",
        help="Comma-separated seasons to include"
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=1.5,
        help="Minimum edge (percent) to place bet"
    )
    parser.add_argument(
        "--all-markets",
        action="store_true",
        help="Run all four markets"
    )
    
    args = parser.parse_args()
    
    seasons = [int(s.strip()) for s in args.seasons.split(",")]
    
    if args.all_markets:
        markets = [MarketType.FG_SPREAD, MarketType.FG_TOTAL, MarketType.H1_SPREAD, MarketType.H1_TOTAL]
    else:
        markets = [MarketType(args.market)]
    
    print("\n" + "="*60)
    print("NCAAM HISTORICAL BACKTEST")
    print("="*60)
    print(f"Markets: {[m.value for m in markets]}")
    print(f"Seasons: {seasons}")
    print(f"Min Edge: {args.min_edge}%")
    
    summaries = []
    for market in markets:
        config = BacktestConfig(
            market=market,
            seasons=seasons,
            min_edge=args.min_edge
        )
        summary = run_backtest(config)
        summaries.append(summary)
    
    # Print overall summary
    if len(summaries) > 1:
        print("\n" + "="*60)
        print("OVERALL SUMMARY")
        print("="*60)
        total_bets = sum(s.total_bets for s in summaries)
        total_profit = sum(s.total_profit for s in summaries)
        total_wagered = sum(s.total_wagered for s in summaries)
        overall_roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        
        print(f"Total Bets: {total_bets}")
        print(f"Total Wagered: ${total_wagered:,.2f}")
        print(f"Total Profit: ${total_profit:+,.2f}")
        print(f"Overall ROI: {overall_roi:+.2f}%")
        
        for s in summaries:
            print(f"  {s.market}: {s.total_bets} bets, {s.roi:+.2f}% ROI")


if __name__ == "__main__":
    main()
