#!/usr/bin/env python3
"""
NCAAM Backtesting Engine - 4 Market Types

Run backtests across betting markets:
- 1H Spread, 1H Total
- FG Spread, FG Total

Usage:
    python testing/scripts/run_backtest.py --market fg_spread
    python testing/scripts/run_backtest.py --market 1h_total --seasons 2022,2023,2024

For parallel execution:
    python testing/scripts/run_backtest.py --all-parallel
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import concurrent.futures

import numpy as np
import pandas as pd

# Paths
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "testing" / "data" / "kaggle"
RESULTS_DIR = ROOT_DIR / "testing" / "data" / "backtest_results"


class MarketType(str, Enum):
    """Four independent markets for backtesting."""
    SPREAD_1H = "1h_spread"
    TOTAL_1H = "1h_total"
    SPREAD_FG = "fg_spread"
    TOTAL_FG = "fg_total"


class BetOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"


@dataclass
class TeamRating:
    """Team efficiency ratings from Kaggle data."""
    name: str
    conf: str
    games: int
    wins: int
    adj_o: float  # Adjusted Offensive Efficiency
    adj_d: float  # Adjusted Defensive Efficiency
    barthag: float  # Expected win % vs avg D1 team
    adj_t: float  # Adjusted Tempo
    efg_o: float  # Effective FG% Offense
    efg_d: float  # Effective FG% Defense
    tor: float  # Turnover Rate
    tord: float  # Turnover Rate Allowed
    orb: float  # Offensive Rebound %
    drb: float  # Defensive Rebound %
    seed: Optional[int] = None
    postseason: Optional[str] = None

    @property
    def net_rating(self) -> float:
        return self.adj_o - self.adj_d


@dataclass
class BetResult:
    """Result of a single simulated bet."""
    season: int
    home_team: str
    away_team: str
    market: str
    predicted_line: float
    market_line: float
    edge: float
    bet_side: str
    outcome: BetOutcome
    wager: float
    profit: float
    actual_result: float
    clv: float = 0.0
    confidence: float = 0.0


@dataclass
class BacktestConfig:
    """Configuration for backtest run (synced with predictor.py v6.1)."""
    market: MarketType
    seasons: List[int]
    min_edge: float = 1.5  # Minimum edge to place bet
    kelly_fraction: float = 0.25  # Fractional Kelly
    base_unit: float = 100.0  # Base bet size
    max_kelly: float = 0.10  # Max Kelly fraction
    sigma_spread: float = 11.0  # Std dev for game margins
    sigma_total: float = 8.0  # Std dev for totals
    # HCA values - EXPLICIT (match config.py v6.1)
    hca_spread: float = 3.0  # Points added to spread
    hca_total: float = 0.0  # Points added to total (default zero-sum assumption)
    neutral_pct: float = 0.05  # % of games at neutral site
    seed: int = 42  # Random seed for reproducibility


@dataclass
class BacktestSummary:
    """Summary statistics for a backtest run."""
    market: str
    seasons: List[int]
    total_bets: int
    wins: int
    losses: int
    pushes: int
    total_wagered: float
    total_profit: float
    roi: float
    win_rate: float
    sharpe_ratio: float
    avg_edge: float
    avg_clv: float
    max_drawdown: float
    by_season: Dict[int, Dict] = field(default_factory=dict)


class NCAAMPredictor:
    """
    Replicates prediction logic from predictor.py v6.1.

    v6.1 Formula (CORRECTED):
    - Spread: Net rating difference approach (NOT multiplicative)
    - Total: Simple efficiency (AdjO * Tempo / 100)
    """

    def __init__(self, config: BacktestConfig):
        self.config = config

    def predict_matchup(
        self,
        home: TeamRating,
        away: TeamRating,
        is_neutral: bool = False
    ) -> Dict[str, float]:
        """Generate predictions for all 6 markets using v6.1 formulas."""
        avg_tempo = (home.adj_t + away.adj_t) / 2.0

        # ─────────────────────────────────────────────────────────────────
        # SPREAD: Net rating difference (v6.1 formula)
        # ─────────────────────────────────────────────────────────────────
        home_net = home.adj_o - home.adj_d
        away_net = away.adj_o - away.adj_d
        raw_margin = (home_net - away_net) / 2.0

        hca_spread = 0.0 if is_neutral else self.config.hca_spread
        fg_spread = -(raw_margin + hca_spread)

        # ─────────────────────────────────────────────────────────────────
        # TOTAL: Simple efficiency (v6.1 formula)
        # ─────────────────────────────────────────────────────────────────
        home_score_base = home.adj_o * avg_tempo / 100.0
        away_score_base = away.adj_o * avg_tempo / 100.0

        # HCA for total is explicit. Default is 0.0 (zero-sum assumption).
        hca_total = 0.0 if is_neutral else self.config.hca_total
        fg_total = home_score_base + away_score_base + hca_total

        # ─────────────────────────────────────────────────────────────────
        # FIRST HALF: Independent calculation (v6.1 formula)
        # ─────────────────────────────────────────────────────────────────
        hca_spread_1h = 0.0 if is_neutral else (self.config.hca_spread * 0.5)
        hca_total_1h = 0.0 if is_neutral else (self.config.hca_total * 0.25)

        # 1H Spread: 50% of raw margin + 1H HCA
        h1_spread = -(raw_margin * 0.5 + hca_spread_1h)

        # 1H Total: 48% tempo factor
        first_half_tempo_pct = 0.48
        home_score_1h = home.adj_o * avg_tempo * first_half_tempo_pct / 100.0
        away_score_1h = away.adj_o * avg_tempo * first_half_tempo_pct / 100.0
        h1_total = home_score_1h + away_score_1h + hca_total_1h

        # Derive final scores
        home_score = (fg_total - fg_spread) / 2
        away_score = (fg_total + fg_spread) / 2

        return {
            "fg_spread": fg_spread,
            "fg_total": fg_total,
                        "1h_spread": h1_spread,
            "1h_total": h1_total,
                        "home_score": home_score,
            "away_score": away_score,
        }


class MarketSimulator:
    """Simulates market lines and game outcomes."""

    def __init__(self, config: BacktestConfig, rng: np.random.Generator):
        self.config = config
        self.rng = rng

    def generate_market_line(
        self,
        true_line: float,
        market_type: MarketType,
        home_barthag: float,
        away_barthag: float
    ) -> float:
        """
        Generate a market line with some noise from true value.

        Markets are efficient but not perfect. We add noise proportional
        to the uncertainty in the matchup.
        """
        # Rating difference affects market uncertainty
        rating_diff = abs(home_barthag - away_barthag)
        uncertainty = max(0.5, 2.0 - rating_diff * 2)  # 0.5 to 2.0 points

        if market_type in [MarketType.SPREAD_FG, MarketType.SPREAD_1H]:
            # Spreads typically move in 0.5 increments
            noise = self.rng.normal(0, uncertainty)
            market_line = round(true_line * 2) / 2 + round(noise * 2) / 2
        elif market_type in [MarketType.TOTAL_FG, MarketType.TOTAL_1H]:
            # Totals also in 0.5 increments
            noise = self.rng.normal(0, uncertainty * 0.7)
            market_line = round(true_line * 2) / 2 + round(noise * 2) / 2
        return market_line

    def simulate_game_result(
        self,
        predictions: Dict[str, float],
        is_neutral: bool
    ) -> Dict[str, float]:
        """Simulate actual game outcome with variance."""
        # Full game margin
        expected_margin = predictions["home_score"] - predictions["away_score"]
        actual_margin = expected_margin + self.rng.normal(0, self.config.sigma_spread)

        # Full game total
        expected_total = predictions["home_score"] + predictions["away_score"]
        actual_total = expected_total + self.rng.normal(0, self.config.sigma_total)

        # First half (correlated with full game but with more variance)
        h1_margin = actual_margin * 0.5 + self.rng.normal(0, self.config.sigma_spread * 0.6)
        h1_total = actual_total * 0.5 + self.rng.normal(0, self.config.sigma_total * 0.6)

        # Win determination
        home_wins_fg = actual_margin > 0
        home_wins_1h = h1_margin > 0

        return {
            "fg_margin": actual_margin,
            "fg_total": actual_total,
            "1h_margin": h1_margin,
            "1h_total": h1_total,
            "home_wins_fg": home_wins_fg,
            "home_wins_1h": home_wins_1h,
        }


class KellyCalculator:
    """Kelly Criterion bet sizing."""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def calculate_kelly(
        self,
        edge: float,
        confidence: float,
        market_type: MarketType
    ) -> float:
        """
        Calculate Kelly fraction for bet sizing.

        For spread/total: edge is in points
        For ML: edge is probability difference
        """
        # Standard -110 juice (52.38% implied probability)
        odds_prob = 0.5238
        b = 100 / 110  # Win/loss ratio at -110

        # Convert point edge to probability edge
        # Roughly 2.5 points = 10% edge shift
        edge_prob = edge / 25.0
        p = min(0.99, max(0.01, odds_prob + edge_prob * confidence))

        q = 1 - p

        # Kelly formula: f* = (bp - q) / b
        kelly = max(0, (b * p - q) / b)

        # Apply fractional Kelly and cap
        kelly = min(kelly * self.config.kelly_fraction, self.config.max_kelly)

        return kelly

    def calculate_bet_size(
        self,
        edge: float,
        confidence: float,
        market_type: MarketType
    ) -> float:
        """Calculate bet size in dollars."""
        kelly = self.calculate_kelly(edge, confidence, market_type)
        return kelly * self.config.base_unit / self.config.kelly_fraction


def load_season_data(season: int) -> Dict[str, TeamRating]:
    """Load team ratings for a specific season."""
    # Map season year to file suffix
    suffix = str(season)[-2:]  # 2024 -> "24"
    filepath = DATA_DIR / f"cbb{suffix}.csv"

    if not filepath.exists():
        # Try combined file
        filepath = DATA_DIR / "cbb.csv"
        if not filepath.exists():
            raise FileNotFoundError(f"No data file found for season {season}")

    df = pd.read_csv(filepath)

    # If combined file, filter by year
    if "YEAR" in df.columns:
        df = df[df["YEAR"] == season]
    elif "Year" in df.columns:
        df = df[df["Year"] == season]

    teams = {}
    for _, row in df.iterrows():
        # Handle column name variations
        team_name = row.get("TEAM") or row.get("Team") or row.get("team")
        if pd.isna(team_name):
            continue

        # Extract required fields with fallbacks
        try:
            rating = TeamRating(
                name=str(team_name).strip(),
                conf=str(row.get("CONF", row.get("Conf", ""))).strip(),
                games=int(row.get("G", row.get("Games", 30))),
                wins=int(row.get("W", row.get("Wins", 15))),
                adj_o=float(row.get("ADJOE", row.get("AdjOE", 100))),
                adj_d=float(row.get("ADJDE", row.get("AdjDE", 100))),
                barthag=float(row.get("BARTHAG", row.get("Barthag", 0.5))),
                adj_t=float(row.get("ADJ_T", row.get("AdjT", 68))),
                efg_o=float(row.get("EFG_O", row.get("eFG%", 50))),
                efg_d=float(row.get("EFG_D", row.get("eFG%D", 50))),
                tor=float(row.get("TOR", row.get("TO%", 18))),
                tord=float(row.get("TORD", row.get("TO%D", 18))),
                orb=float(row.get("ORB", row.get("OR%", 30))),
                drb=float(row.get("DRB", row.get("DR%", 70))),
                seed=int(row["SEED"]) if pd.notna(row.get("SEED")) else None,
                postseason=str(row["POSTSEASON"]) if pd.notna(row.get("POSTSEASON")) else None,
            )
            teams[rating.name] = rating
        except (ValueError, KeyError) as e:
            continue  # Skip teams with missing data

    return teams


def generate_matchups(
    teams: Dict[str, TeamRating],
    config: BacktestConfig,
    rng: np.random.Generator
) -> List[Tuple[TeamRating, TeamRating, bool]]:
    """
    Generate all pairwise matchups for a season.

    Returns list of (home_team, away_team, is_neutral) tuples.
    """
    team_list = list(teams.values())
    matchups = []

    for i, home in enumerate(team_list):
        for away in team_list[i + 1:]:
            # Randomly assign home/away
            if rng.random() < 0.5:
                home, away = away, home

            # Some games are at neutral sites
            is_neutral = rng.random() < config.neutral_pct

            matchups.append((home, away, is_neutral))

    return matchups


def determine_outcome(
    market_type: MarketType,
    bet_side: str,
    market_line: float,
    actual: Dict[str, float]
) -> Tuple[BetOutcome, float]:
    """Determine bet outcome and actual result value."""
    if market_type == MarketType.SPREAD_FG:
        actual_margin = actual["fg_margin"]
        if bet_side == "HOME":
            diff = actual_margin - (-market_line)
        else:  # AWAY
            diff = -actual_margin - market_line
        actual_val = actual_margin
    elif market_type == MarketType.SPREAD_1H:
        actual_margin = actual["1h_margin"]
        if bet_side == "HOME":
            diff = actual_margin - (-market_line)
        else:
            diff = -actual_margin - market_line
        actual_val = actual_margin
    elif market_type == MarketType.TOTAL_FG:
        actual_total = actual["fg_total"]
        if bet_side == "OVER":
            diff = actual_total - market_line
        else:
            diff = market_line - actual_total
        actual_val = actual_total
    elif market_type == MarketType.TOTAL_1H:
        actual_total = actual["1h_total"]
        if bet_side == "OVER":
            diff = actual_total - market_line
        else:
            diff = market_line - actual_total
        actual_val = actual_total


    if abs(diff) < 0.001:  # Push
        return BetOutcome.PUSH, actual_val
    elif diff > 0:
        return BetOutcome.WIN, actual_val
    else:
        return BetOutcome.LOSS, actual_val


def calculate_profit(outcome: BetOutcome, wager: float, odds: int = -110) -> float:
    """Calculate profit/loss for a bet."""
    if outcome == BetOutcome.PUSH:
        return 0.0
    elif outcome == BetOutcome.WIN:
        if odds < 0:
            return wager * (100 / abs(odds))
        else:
            return wager * (odds / 100)
    else:
        return -wager


def run_market_backtest(config: BacktestConfig) -> BacktestSummary:
    """Run backtest for a single market type."""
    rng = np.random.default_rng(config.seed)
    predictor = NCAAMPredictor(config)
    simulator = MarketSimulator(config, rng)
    kelly_calc = KellyCalculator(config)

    all_results: List[BetResult] = []
    season_results: Dict[int, List[BetResult]] = {}

    for season in config.seasons:
        try:
            teams = load_season_data(season)
        except FileNotFoundError:
            print(f"  Skipping season {season} - no data file")
            continue

        if len(teams) < 50:
            print(f"  Skipping season {season} - only {len(teams)} teams")
            continue

        matchups = generate_matchups(teams, config, rng)
        season_bets = []

        for home, away, is_neutral in matchups:
            # Get predictions
            predictions = predictor.predict_matchup(home, away, is_neutral)

            # Get relevant prediction for this market
            if config.market == MarketType.SPREAD_FG:
                pred_line = predictions["fg_spread"]
            elif config.market == MarketType.SPREAD_1H:
                pred_line = predictions["1h_spread"]
            elif config.market == MarketType.TOTAL_FG:
                pred_line = predictions["fg_total"]
            elif config.market == MarketType.TOTAL_1H:
                pred_line = predictions["1h_total"]

            # Generate market line
            market_line = simulator.generate_market_line(
                pred_line, config.market, home.barthag, away.barthag
            )

            # Calculate edge
            if config.market in [MarketType.SPREAD_FG, MarketType.SPREAD_1H]:
                edge = market_line - pred_line  # Positive = home covers
                bet_side = "HOME" if edge > 0 else "AWAY"
                edge = abs(edge)
                min_edge_threshold = config.min_edge
            else:  # Totals
                edge = pred_line - market_line  # Positive = over
                bet_side = "OVER" if edge > 0 else "UNDER"
                edge = abs(edge)
                min_edge_threshold = config.min_edge

            # Only bet if edge exceeds minimum
            if edge < min_edge_threshold:
                continue

            # Calculate confidence based on rating difference
            rating_diff = abs(home.barthag - away.barthag)
            confidence = min(1.0, 0.5 + rating_diff)

            # Calculate bet size
            wager = kelly_calc.calculate_bet_size(edge, confidence, config.market)
            if wager < 1.0:  # Minimum bet
                continue

            # Simulate game outcome
            actual = simulator.simulate_game_result(predictions, is_neutral)

            # Determine bet outcome
            outcome, actual_val = determine_outcome(
                config.market, bet_side, market_line, actual
            )

            # Calculate profit
            profit = calculate_profit(outcome, wager)

            # Calculate CLV (simulated - assume market moves toward true line)
            closing_line = (market_line + pred_line) / 2  # Market corrects halfway
            if config.market in [MarketType.SPREAD_FG, MarketType.SPREAD_1H]:
                clv = (closing_line - market_line) if bet_side == "HOME" else (market_line - closing_line)
            else:
                clv = (closing_line - market_line) if bet_side == "OVER" else (market_line - closing_line)

            result = BetResult(
                season=season,
                home_team=home.name,
                away_team=away.name,
                market=config.market.value,
                predicted_line=round(pred_line, 2),
                market_line=round(market_line, 2),
                edge=round(edge, 2),
                bet_side=bet_side,
                outcome=outcome,
                wager=round(wager, 2),
                profit=round(profit, 2),
                actual_result=round(actual_val, 2),
                clv=round(clv, 3),
                confidence=round(confidence, 3),
            )
            season_bets.append(result)

        all_results.extend(season_bets)
        season_results[season] = season_bets
        print(f"  Season {season}: {len(season_bets)} bets")

    # Calculate summary statistics
    summary = calculate_summary(config, all_results, season_results)
    return summary


def calculate_summary(
    config: BacktestConfig,
    results: List[BetResult],
    season_results: Dict[int, List[BetResult]]
) -> BacktestSummary:
    """Calculate summary statistics from results."""
    if not results:
        return BacktestSummary(
            market=config.market.value,
            seasons=config.seasons,
            total_bets=0,
            wins=0,
            losses=0,
            pushes=0,
            total_wagered=0,
            total_profit=0,
            roi=0,
            win_rate=0,
            sharpe_ratio=0,
            avg_edge=0,
            avg_clv=0,
            max_drawdown=0,
        )

    wins = sum(1 for r in results if r.outcome == BetOutcome.WIN)
    losses = sum(1 for r in results if r.outcome == BetOutcome.LOSS)
    pushes = sum(1 for r in results if r.outcome == BetOutcome.PUSH)
    total_wagered = sum(r.wager for r in results)
    total_profit = sum(r.profit for r in results)

    roi = total_profit / total_wagered if total_wagered > 0 else 0
    non_push = wins + losses
    win_rate = wins / non_push if non_push > 0 else 0

    # Sharpe ratio
    returns = [r.profit / r.wager for r in results if r.wager > 0]
    if len(returns) > 1:
        avg_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        sharpe = (avg_return / std_return) * np.sqrt(len(returns)) if std_return > 0 else 0
    else:
        sharpe = 0

    avg_edge = np.mean([r.edge for r in results])
    avg_clv = np.mean([r.clv for r in results])

    # Max drawdown
    cumulative = np.cumsum([r.profit for r in results])
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0

    # Per-season stats
    by_season = {}
    for season, s_results in season_results.items():
        if s_results:
            s_wagered = sum(r.wager for r in s_results)
            s_profit = sum(r.profit for r in s_results)
            s_wins = sum(1 for r in s_results if r.outcome == BetOutcome.WIN)
            s_total = sum(1 for r in s_results if r.outcome != BetOutcome.PUSH)
            by_season[season] = {
                "bets": len(s_results),
                "roi": round(s_profit / s_wagered if s_wagered > 0 else 0, 4),
                "win_rate": round(s_wins / s_total if s_total > 0 else 0, 4),
                "profit": round(s_profit, 2),
            }

    return BacktestSummary(
        market=config.market.value,
        seasons=config.seasons,
        total_bets=len(results),
        wins=wins,
        losses=losses,
        pushes=pushes,
        total_wagered=round(total_wagered, 2),
        total_profit=round(total_profit, 2),
        roi=round(roi, 4),
        win_rate=round(win_rate, 4),
        sharpe_ratio=round(sharpe, 4),
        avg_edge=round(avg_edge, 4),
        avg_clv=round(avg_clv, 4),
        max_drawdown=round(max_drawdown, 2),
        by_season=by_season,
    )


def write_results(
    config: BacktestConfig,
    summary: BacktestSummary,
    results: List[BetResult]
) -> Path:
    """Write results to CSV and JSON files."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write detailed results CSV
    csv_path = RESULTS_DIR / f"{config.market.value}_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=asdict(results[0]).keys())
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))

    # Write summary JSON
    json_path = RESULTS_DIR / f"{config.market.value}_{timestamp}_summary.json"
    with open(json_path, "w") as f:
        json.dump(asdict(summary), f, indent=2)

    return json_path


def print_summary(summary: BacktestSummary) -> None:
    """Print formatted summary to console."""
    print("\n" + "=" * 60)
    print(f"  BACKTEST RESULTS: {summary.market.upper()}")
    print("=" * 60)
    print(f"  Seasons: {min(summary.seasons)}-{max(summary.seasons)}")
    print(f"  Total Bets: {summary.total_bets:,}")
    print(f"  Record: {summary.wins}W - {summary.losses}L - {summary.pushes}P")
    print("-" * 60)
    print(f"  ROI:          {summary.roi:+.2%}")
    print(f"  Win Rate:     {summary.win_rate:.2%}")
    print(f"  Sharpe Ratio: {summary.sharpe_ratio:.2f}")
    print(f"  Avg Edge:     {summary.avg_edge:.2f}")
    print(f"  Avg CLV:      {summary.avg_clv:.3f}")
    print(f"  Max Drawdown: ${summary.max_drawdown:,.2f}")
    print("-" * 60)
    print(f"  Total Wagered: ${summary.total_wagered:,.2f}")
    print(f"  Total Profit:  ${summary.total_profit:+,.2f}")
    print("=" * 60)

    if summary.by_season:
        print("\n  BY SEASON:")
        for season, stats in sorted(summary.by_season.items()):
            print(f"    {season}: {stats['bets']} bets, ROI={stats['roi']:+.2%}, "
                  f"WR={stats['win_rate']:.2%}, P/L=${stats['profit']:+,.0f}")


def run_single_market(market: MarketType, seasons: List[int], seed: int) -> BacktestSummary:
    """Run backtest for a single market (for parallel execution)."""
    config = BacktestConfig(
        market=market,
        seasons=seasons,
        seed=seed,
    )
    print(f"\nRunning {market.value}...")
    summary = run_market_backtest(config)
    print_summary(summary)
    return summary


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NCAAM Backtesting Engine - 4 Market Types"
    )
    parser.add_argument(
        "--market",
        type=str,
        choices=[m.value for m in MarketType],
        help="Market type to backtest",
    )
    parser.add_argument(
        "--all-parallel",
        action="store_true",
        help="Run all 4 markets in parallel",
    )
    parser.add_argument(
        "--seasons",
        type=str,
        default="2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025",
        help="Comma-separated list of seasons",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=1.5,
        help="Minimum edge to place bet (default: 1.5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )

    args = parser.parse_args(argv)
    seasons = [int(s.strip()) for s in args.seasons.split(",")]

    if args.all_parallel:
        # Run all 6 markets in parallel
        print("Running all 4 markets in parallel...")
        markets = list(MarketType)

        with concurrent.futures.ProcessPoolExecutor(max_workers=len(markets)) as executor:
            futures = {
                executor.submit(run_single_market, m, seasons, args.seed + i): m
                for i, m in enumerate(markets)
            }

            results = {}
            for future in concurrent.futures.as_completed(futures):
                market = futures[future]
                try:
                    summary = future.result()
                    results[market.value] = summary
                except Exception as e:
                    print(f"Error in {market.value}: {e}")

        # Print combined summary
        print("\n" + "=" * 70)
        print("  COMBINED RESULTS - ALL MARKETS")
        print("=" * 70)
        print(f"  {'Market':<15} {'Bets':>8} {'ROI':>10} {'Win Rate':>10} {'Sharpe':>8} {'Profit':>12}")
        print("-" * 70)
        for market in MarketType:
            if market.value in results:
                s = results[market.value]
                print(f"  {s.market:<15} {s.total_bets:>8,} {s.roi:>+10.2%} "
                      f"{s.win_rate:>10.2%} {s.sharpe_ratio:>8.2f} ${s.total_profit:>+11,.0f}")
        print("=" * 70)

    elif args.market:
        # Run single market
        market = MarketType(args.market)
        config = BacktestConfig(
            market=market,
            seasons=seasons,
            min_edge=args.min_edge,
            seed=args.seed,
        )
        print(f"Running backtest for {market.value}...")
        summary = run_market_backtest(config)
        print_summary(summary)

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
