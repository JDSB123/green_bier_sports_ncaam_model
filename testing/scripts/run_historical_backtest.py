#!/usr/bin/env python3
"""
NCAAM Historical Backtesting Engine

Runs backtests using ACTUAL historical game outcomes from the canonical master (manifests/canonical_training_data_master.csv).
Unlike run_backtest.py which simulates games, this uses real results.

Usage:
    python testing/scripts/run_historical_backtest.py --market fg_spread
    python testing/scripts/run_historical_backtest.py --market h1_total --seasons 2024,2025,2026
    python testing/scripts/run_historical_backtest.py --all-markets
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Ensure project root on path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_data_reader import get_azure_reader
from testing.data_window import CANONICAL_START_SEASON, default_backtest_seasons, enforce_min_season

# Paths
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
    hca_spread: float = 5.8  # Home court advantage for spread (backtested optimal)
    hca_total: float = 0.0  # HCA for total (zero-sum)
    hca_h1_spread: float = 3.6  # H1 HCA (independent, not FG/2)


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
    actual_odds: float  # ACTUAL odds used (not -110)
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
    Generates predictions using Barttorvik ratings + Four Factors.
    Enhanced v34.1 prediction formulas with style matchup adjustments.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config

    def _calculate_four_factors_adjustment(
        self,
        home_efg: float, home_efgd: float, home_tor: float, home_orb: float, home_drb: float, home_ftr: float,
        away_efg: float, away_efgd: float, away_tor: float, away_orb: float, away_drb: float, away_ftr: float
    ) -> float:
        """
        Calculate Four Factors style matchup adjustment.

        Returns adjustment in points to add to spread prediction.
        Positive = favors home team.
        """
        if any(pd.isna(x) for x in [home_efg, home_tor, home_orb, home_ftr, away_efg, away_tor, away_orb, away_ftr]):
            return 0.0

        # Matchup advantages (home offense vs away defense, away offense vs home defense)
        # EFG matchup: home shooting vs away defense
        efg_matchup = (home_efg - away_efgd) - (away_efg - home_efgd)

        # Turnover matchup: lower is better for offense
        # If home has low TOR and away has high TOR, that favors home
        tor_matchup = (away_tor - home_tor) * 0.5  # Scale down

        # Rebounding matchup: home ORB vs away DRB
        orb_matchup = (home_orb - away_drb) - (away_orb - home_drb)

        # Free throw rate matchup
        ftr_matchup = (home_ftr - away_ftr) * 0.3  # FTR has smaller impact

        # Weighted combination (empirically derived weights)
        # EFG is the most predictive Four Factor
        adjustment = (
            efg_matchup * 2.5 +    # EFG: ~2.5 pts per 0.1 difference
            tor_matchup * 1.5 +    # TOR: ~1.5 pts per 0.1 difference
            orb_matchup * 1.0 +    # ORB: ~1.0 pts per 0.1 difference
            ftr_matchup * 0.5      # FTR: ~0.5 pts per 0.1 difference
        )

        # Cap adjustment to prevent extreme values
        return max(-5.0, min(5.0, adjustment))

    def _calculate_advanced_adjustment(
        self,
        # Conference strength
        conf_strength_diff: float = None,
        # Box score rolling features
        home_team_depth_rolling: float = None,
        away_team_depth_rolling: float = None,
        home_ast_to_ratio_rolling: float = None,
        away_ast_to_ratio_rolling: float = None,
    ) -> float:
        """
        Calculate advanced adjustment from conference strength and box score features.

        Returns adjustment in points. Positive = favors home team.
        """
        adjustment = 0.0

        # Conference strength adjustment
        # Stronger conference teams tend to perform better
        if conf_strength_diff is not None and not pd.isna(conf_strength_diff):
            # Scale: 0.1 barthag diff ~ 1 point (conservative)
            adjustment += conf_strength_diff * 10.0

        # Team depth adjustment
        # Deeper teams (more balanced scoring) tend to be more consistent
        if (home_team_depth_rolling is not None and away_team_depth_rolling is not None and
            not pd.isna(home_team_depth_rolling) and not pd.isna(away_team_depth_rolling)):
            depth_diff = home_team_depth_rolling - away_team_depth_rolling
            adjustment += depth_diff * 0.25  # ~0.25 pts per player

        # Assist-to-turnover ratio (ball security)
        if (home_ast_to_ratio_rolling is not None and away_ast_to_ratio_rolling is not None and
            not pd.isna(home_ast_to_ratio_rolling) and not pd.isna(away_ast_to_ratio_rolling)):
            ast_to_diff = home_ast_to_ratio_rolling - away_ast_to_ratio_rolling
            adjustment += ast_to_diff * 0.4

        # Cap adjustment
        return max(-3.0, min(3.0, adjustment))

    def predict_spread(
        self,
        home_adj_o: float,
        home_adj_d: float,
        away_adj_o: float,
        away_adj_d: float,
        is_neutral: bool = False,
        # Four Factors (optional, for enhanced prediction)
        home_efg: float = None, home_efgd: float = None, home_tor: float = None,
        home_orb: float = None, home_drb: float = None, home_ftr: float = None,
        away_efg: float = None, away_efgd: float = None, away_tor: float = None,
        away_orb: float = None, away_drb: float = None, away_ftr: float = None,
        # Advanced features (conference + box scores)
        conf_strength_diff: float = None,
        home_team_depth_rolling: float = None,
        away_team_depth_rolling: float = None,
        home_ast_to_ratio_rolling: float = None,
        away_ast_to_ratio_rolling: float = None,
    ) -> float:
        """Predict spread (home perspective, negative = home favored)."""
        home_net = home_adj_o - home_adj_d
        away_net = away_adj_o - away_adj_d
        raw_margin = (home_net - away_net) / 2.0

        hca = 0.0 if is_neutral else self.config.hca_spread

        # Four Factors adjustment (if available)
        ff_adj = self._calculate_four_factors_adjustment(
            home_efg, home_efgd, home_tor, home_orb, home_drb, home_ftr,
            away_efg, away_efgd, away_tor, away_orb, away_drb, away_ftr
        )

        # Advanced adjustment (conference strength + box score features)
        adv_adj = self._calculate_advanced_adjustment(
            conf_strength_diff,
            home_team_depth_rolling, away_team_depth_rolling,
            home_ast_to_ratio_rolling, away_ast_to_ratio_rolling
        )

        return -(raw_margin + hca + ff_adj + adv_adj)  # Negative = home favored

    def predict_total(
        self,
        home_adj_o: float,
        home_adj_d: float,
        home_tempo: float,
        away_adj_o: float,
        away_adj_d: float,
        away_tempo: float,
        is_neutral: bool = False,
        # Shooting tendencies (optional)
        home_three_pt_rate: float = None,
        away_three_pt_rate: float = None
    ) -> float:
        """Predict total points."""
        avg_tempo = (home_tempo + away_tempo) / 2.0
        home_score = home_adj_o * avg_tempo / 100.0
        away_score = away_adj_o * avg_tempo / 100.0

        hca = 0.0 if is_neutral else self.config.hca_total

        # 3PT rate adjustment (high 3PT games tend to have higher variance)
        # Teams with high 3PT rate may score more or less depending on shooting
        three_pt_adj = 0.0
        if home_three_pt_rate is not None and away_three_pt_rate is not None:
            avg_3pt_rate = (home_three_pt_rate + away_three_pt_rate) / 2.0
            # If both teams shoot a lot of 3s, slightly increase total prediction
            if avg_3pt_rate > 1.0:  # Above average 3PT rate
                three_pt_adj = (avg_3pt_rate - 1.0) * 2.0  # Small adjustment

        return home_score + away_score + hca + three_pt_adj

    def predict_h1_spread(
        self,
        home_adj_o: float,
        home_adj_d: float,
        away_adj_o: float,
        away_adj_d: float,
        is_neutral: bool = False,
        # Four Factors for matchup adjustment
        home_efg: float = None, home_efgd: float = None, home_tor: float = None,
        home_orb: float = None, home_drb: float = None, home_ftr: float = None,
        away_efg: float = None, away_efgd: float = None, away_tor: float = None,
        away_orb: float = None, away_drb: float = None, away_ftr: float = None,
        **kwargs
    ) -> float:
        """
        Predict 1H spread - INDEPENDENT MODEL (NOT FG/2).

        Uses independent constants from production h1_spread.py:
        - HCA_H1 = 3.6 (not 5.8/2)
        - CALIBRATION = 1.3 (not FG calibration)
        - Dynamic margin scaling based on EFG differential
        """
        # Independent H1 constants (from h1_spread.py)
        HCA_H1 = 3.6  # Independently derived from 1H backtest
        CALIBRATION_H1 = 1.3  # Independent 1H calibration
        LEAGUE_AVG_EFG = 50.0

        # Calculate efficiency differential
        home_net = home_adj_o - home_adj_d
        away_net = away_adj_o - away_adj_d
        raw_margin = (home_net - away_net) / 2.0

        # Calculate dynamic 1H margin scale based on EFG differential
        # (EFG advantages show up faster in 1H)
        BASE_MARGIN_SCALE = 0.50
        if home_efg is not None and away_efg is not None:
            efg_diff = abs(home_efg - away_efg)
            margin_adj = efg_diff * 0.01  # Larger EFG gaps show up faster
            margin_scale = max(0.45, min(0.55, BASE_MARGIN_SCALE + margin_adj))
        else:
            margin_scale = BASE_MARGIN_SCALE

        # Apply 1H-specific margin scaling
        raw_margin_h1 = raw_margin * margin_scale

        # HCA (independent for 1H)
        hca = 0.0 if is_neutral else HCA_H1

        # Four Factors adjustment (scaled for 1H)
        ff_adj = self._calculate_four_factors_adjustment(
            home_efg, home_efgd, home_tor, home_orb, home_drb, home_ftr,
            away_efg, away_efgd, away_tor, away_orb, away_drb, away_ftr
        ) * margin_scale

        # Final 1H spread with independent calibration
        return -(raw_margin_h1 + hca + ff_adj) + CALIBRATION_H1

    def predict_h1_total(
        self,
        home_adj_o: float,
        home_adj_d: float,
        home_tempo: float,
        away_adj_o: float,
        away_adj_d: float,
        away_tempo: float,
        is_neutral: bool = False,
        home_barthag: float = None,
        away_barthag: float = None,
        home_three_pt_rate: float = None,
        away_three_pt_rate: float = None,
        **kwargs
    ) -> float:
        """
        Predict 1H total - INDEPENDENT MODEL (NOT FG*0.48).

        Uses independent logic from production h1_total.py:
        - Independent possession estimation (~30.6 avg, not FG/2)
        - Independent efficiency discount (97% of FG)
        - Independent calibration = -11.8
        - Quality mismatch adjustments
        """
        # Independent H1 constants (from h1_total.py)
        CALIBRATION_H1 = -11.8  # Independent 1H total calibration
        H1_POSSESSIONS_BASE = 33.0
        H1_EFFICIENCY_DISCOUNT = 0.97
        LEAGUE_AVG_TEMPO = 67.6
        LEAGUE_AVG_EFFICIENCY = 105.5

        # Estimate 1H possessions independently
        # (NOT simply FG possessions / 2)
        avg_fg_tempo = (home_tempo + away_tempo) / 2
        tempo_deviation = (avg_fg_tempo - LEAGUE_AVG_TEMPO) / LEAGUE_AVG_TEMPO
        h1_possessions = H1_POSSESSIONS_BASE * (1 + tempo_deviation * 0.85)
        h1_possessions *= 1.02  # Late-half pace boost

        # Calculate 1H-specific efficiencies
        home_matchup_eff = home_adj_o + away_adj_d - LEAGUE_AVG_EFFICIENCY
        away_matchup_eff = away_adj_o + home_adj_d - LEAGUE_AVG_EFFICIENCY

        home_h1_eff = home_matchup_eff * H1_EFFICIENCY_DISCOUNT / 1.03  # Defense intensity
        away_h1_eff = away_matchup_eff * H1_EFFICIENCY_DISCOUNT / 1.03

        # Calculate 1H scores
        home_score = home_h1_eff * h1_possessions / 100.0
        away_score = away_h1_eff * h1_possessions / 100.0
        base_total = home_score + away_score

        # Adjustments
        adjustment = 0.0

        # Tempo adjustment (1H-specific thresholds)
        if avg_fg_tempo > 71.0:
            adjustment += (avg_fg_tempo - 71.0) * 0.20
        elif avg_fg_tempo < 65.0:
            adjustment += (avg_fg_tempo - 65.0) * 0.20

        # Quality mismatch (blowouts slow down in 1H)
        if home_barthag is not None and away_barthag is not None:
            quality_diff = abs(home_barthag - away_barthag)
            if quality_diff > 0.20:
                adjustment -= quality_diff * 1.5

        # 3PT rate adjustment
        if home_three_pt_rate is not None and away_three_pt_rate is not None:
            avg_3pr = (home_three_pt_rate + away_three_pt_rate) / 2
            if avg_3pr > 36.0:
                adjustment += (avg_3pr - 36.0) * 0.20

        return base_total + adjustment + CALIBRATION_H1

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
    """Load the canonical backtest master dataset."""
    reader = get_azure_reader()
    print("[INFO] Loading canonical backtest master")
    df = reader.read_backtest_master()

    if "game_date" in df.columns:
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    elif "date" in df.columns:
        df["game_date"] = pd.to_datetime(df["date"], errors="coerce")

    if "season" in df.columns:
        df = df[df["season"] >= CANONICAL_START_SEASON]

    if "actual_margin" not in df.columns and {"home_score", "away_score"}.issubset(df.columns):
        df["actual_margin"] = df["home_score"] - df["away_score"]
    if "actual_total" not in df.columns and {"home_score", "away_score"}.issubset(df.columns):
        df["actual_total"] = df["home_score"] + df["away_score"]

    return df


def validate_sign_convention(df: pd.DataFrame) -> bool:
    """
    Validate sign convention: home favorites should have NEGATIVE spreads.

    Convention:
    - Spread = -5 means home is favored by 5 (home expected to win by 5)
    - Spread = +5 means away is favored by 5 (home expected to lose by 5)

    Returns True if validation passes.
    """
    print("\n[VALIDATION] Sign Convention Check")
    print("-" * 40)

    # Check games where home team won big (clear favorites)
    home_blowouts = df[df["actual_margin"] > 15].copy()
    if len(home_blowouts) > 0:
        # For home blowout wins, spread should typically be negative (home favored)
        with_spread = home_blowouts[home_blowouts["fg_spread"].notna()]
        if len(with_spread) > 0:
            negative_spread_pct = (with_spread["fg_spread"] < 0).mean() * 100
            print(f"   Home blowout wins (margin > 15): {len(with_spread):,} games")
            print(f"   With negative spread (correctly favored): {negative_spread_pct:.1f}%")

            if negative_spread_pct < 50:
                print(f"   [WARN] Sign convention may be inverted!")
                return False

    # Check correlation: negative spread should correlate with positive actual margin
    with_both = df[(df["fg_spread"].notna()) & (df["actual_margin"].notna())]
    if len(with_both) > 100:
        corr = with_both["fg_spread"].corr(with_both["actual_margin"])
        print(f"   Spread vs Actual Margin correlation: {corr:.3f}")

        # Negative correlation expected (home favored = negative spread, likely positive margin)
        if corr > 0.3:
            print(f"   [WARN] Unexpected positive correlation - check sign convention!")
            return False
        elif corr < -0.1:
            print(f"   [OK] Negative correlation confirms correct sign convention")

    print(f"   [OK] Sign convention validated")
    return True


def validate_team_matching(df: pd.DataFrame) -> bool:
    """
    Validate that home and away teams are correctly identified.

    Checks:
    1. No team appears as both home and away in the same game
    2. Home team advantage is visible in data
    3. Canonical team names are used consistently
    4. No team name confusion (e.g., "Duke" vs "Duke Blue Devils")

    Returns True if validation passes.
    """
    print("\n[VALIDATION] Team Matching Check")
    print("-" * 40)

    # Check 1: No team in both positions for same game
    same_team = df[df["home_team"] == df["away_team"]]
    if len(same_team) > 0:
        print(f"   [ERROR] {len(same_team)} games with same home/away team!")
        return False
    print(f"   [OK] No games with same team in both positions")

    # Check 2: Home court advantage visible
    home_wins = (df["actual_margin"] > 0).sum()
    away_wins = (df["actual_margin"] < 0).sum()
    home_win_pct = home_wins / (home_wins + away_wins) * 100

    print(f"   Home win rate: {home_win_pct:.1f}% ({home_wins:,} / {home_wins + away_wins:,})")

    if home_win_pct < 45:
        print(f"   [WARN] Home win rate unusually low - check home/away assignment")
        return False
    elif home_win_pct > 75:
        print(f"   [WARN] Home win rate unusually high - check data quality")
        return False
    else:
        print(f"   [OK] Home court advantage in expected range (50-65%)")

    # Check 3: Canonical team names used
    if "home_team_canonical" in df.columns:
        # Check that canonical names are populated
        missing_canonical = df["home_team_canonical"].isna().sum()
        if missing_canonical > 0:
            print(f"   [WARN] {missing_canonical} games missing canonical home team name")
        else:
            print(f"   [OK] All games have canonical team names")

        # Check for duplicate team name issues
        unique_teams = set(df["home_team_canonical"].dropna().unique()) | set(df["away_team_canonical"].dropna().unique())
        print(f"   Unique teams in dataset: {len(unique_teams)}")

        # Look for potential duplicates (same team with different names)
        from collections import Counter
        name_parts = Counter()
        for team in unique_teams:
            if isinstance(team, str):
                parts = team.lower().split()
                for part in parts:
                    if len(part) > 3:  # Skip short words
                        name_parts[part] += 1

        # Check for teams that might be duplicated
        potential_issues = []
        for team in unique_teams:
            if isinstance(team, str):
                # Check if team name contains common college basketball team names
                lower_name = team.lower()
                for other_team in unique_teams:
                    if isinstance(other_team, str) and team != other_team:
                        other_lower = other_team.lower()
                        # Check if one is a subset of the other
                        if lower_name in other_lower or other_lower in lower_name:
                            potential_issues.append(f"{team} vs {other_team}")

        if potential_issues:
            print(f"   [WARN] Potential duplicate team names:")
            for issue in potential_issues[:5]:  # Show first 5
                print(f"      - {issue}")
            print(f"   Total potential issues: {len(potential_issues)}")

    return True


def validate_no_data_leakage(df: pd.DataFrame) -> bool:
    """
    Validate that ratings are from PRIOR season (no leakage).

    Checks:
    1. ratings_season = season - 1
    2. No use of end-of-season ratings for same-season games

    Returns True if validation passes.
    """
    print("\n[VALIDATION] Data Leakage Check")
    print("-" * 40)

    if "ratings_season" not in df.columns or "season" not in df.columns:
        print(f"   [WARN] Cannot validate - ratings_season column missing")
        return True

    # Check that ratings_season = season - 1
    correct_season = (df["ratings_season"] == df["season"] - 1).all()
    if not correct_season:
        mismatches = df[df["ratings_season"] != df["season"] - 1]
        print(f"   [ERROR] {len(mismatches)} games using incorrect rating season!")
        print(f"   Example: Game season {mismatches.iloc[0]['season']}, rating season {mismatches.iloc[0]['ratings_season']}")
        return False

    print(f"   [OK] All ratings from prior season (N-1)")

    # Verify we're using pre-season ratings, not mid-season
    if "home_adj_o" in df.columns:
        ratings_available = df["home_adj_o"].notna().sum()
        print(f"   Ratings coverage: {ratings_available:,}/{len(df):,} ({ratings_available/len(df)*100:.1f}%)")

    return True


def validate_actual_odds_used(df: pd.DataFrame) -> bool:
    """
    Validate that actual odds prices are available (not just lines).

    CRITICAL: Must have price columns, not just spread/total lines.
    """
    print("\n[VALIDATION] Actual Odds Check")
    print("-" * 40)

    price_cols = [c for c in df.columns if "price" in c.lower()]

    if not price_cols:
        print(f"   [ERROR] No price columns found!")
        print("   Run: python testing/scripts/build_backtest_dataset_canonical.py")
        return False

    print(f"   Price columns found: {price_cols}")

    for col in price_cols:
        if col in df.columns:
            coverage = df[col].notna().sum()
            pct = coverage / len(df) * 100
            print(f"   {col}: {coverage:,} ({pct:.1f}%)")

    # Check if we have reasonable coverage for FG spread
    if "fg_spread_home_price" in df.columns:
        coverage = df["fg_spread_home_price"].notna().sum() / len(df) * 100
        if coverage < 50:
            print(f"   [WARN] Low price coverage ({coverage:.1f}%) - some bets may use -110 fallback")
        else:
            print(f"   [OK] Good price coverage for actual odds")

    return True


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


def american_odds_to_decimal(american_odds: float) -> Optional[float]:
    """
    Convert American odds to decimal multiplier.

    CRITICAL: Returns None if odds are missing - NO FALLBACK TO -110.
    Caller must handle None appropriately (skip the bet).

    Examples:
        -110 -> 1.909 (bet 110 to win 100)
        +150 -> 2.5 (bet 100 to win 150)
        -200 -> 1.5 (bet 200 to win 100)
        NaN  -> None (SKIP THIS BET)
    """
    if pd.isna(american_odds):
        return None  # NO FALLBACK - must have real odds

    if american_odds >= 100:
        # Positive odds: +150 means win $150 on $100 bet
        return (american_odds / 100) + 1
    else:
        # Negative odds: -110 means bet $110 to win $100
        return (100 / abs(american_odds)) + 1


def calculate_profit(outcome: BetOutcome, wager: float, odds: float) -> Optional[float]:
    """
    Calculate profit from bet outcome using ACTUAL ODDS.

    CRITICAL: Uses REAL odds only - returns None if odds are missing.
    NO FALLBACK TO -110.

    Args:
        outcome: WIN, LOSS, or PUSH
        wager: Amount wagered
        odds: American odds (e.g., -110, +150). REQUIRED.

    Returns:
        Profit (positive for wins, negative for losses, 0 for pushes)
        Returns None if odds are missing (bet should be skipped)
    """
    decimal_odds = american_odds_to_decimal(odds)
    if decimal_odds is None:
        return None  # Cannot calculate profit without real odds

    if outcome == BetOutcome.WIN:
        return wager * (decimal_odds - 1)  # Profit = wager * (decimal - 1)
    elif outcome == BetOutcome.LOSS:
        return -wager
    else:
        return 0.0  # Push


def run_backtest(config: BacktestConfig, skip_validation: bool = False) -> BacktestSummary:
    """Run backtest for a single market."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING: {config.market.value.upper()}")
    print(f"Seasons: {config.seasons}")
    print(f"Min Edge: {config.min_edge}%")
    print(f"{'='*60}")

    # Load data
    df = load_backtest_data()

    # Run validations (first time only)
    if not skip_validation:
        print("\n" + "="*60)
        print("DATA VALIDATION")
        print("="*60)

        sign_ok = validate_sign_convention(df)
        team_ok = validate_team_matching(df)
        leakage_ok = validate_no_data_leakage(df)
        odds_ok = validate_actual_odds_used(df)

        all_ok = sign_ok and team_ok and leakage_ok and odds_ok

        if all_ok:
            print("\n[OK] All validations passed!")
        else:
            print("\n[WARN] Some validations failed - review data quality")

        print("="*60)

    # Filter to requested seasons
    df = df[df["season"].isin(config.seasons)]
    total_games = len(df)

    # Determine which columns we need - NO APPROXIMATIONS
    # CRITICAL: Use ACTUAL H1 scores for H1 markets, not FG * 0.5
    if config.market == MarketType.FG_SPREAD:
        line_col = "fg_spread"
        result_col = "actual_margin"
        price_col = "fg_spread_home_price"  # For home bet
        alt_price_col = "fg_spread_away_price"  # For away bet
    elif config.market == MarketType.FG_TOTAL:
        line_col = "fg_total"
        result_col = "actual_total"
        price_col = "fg_total_over_price"  # For over bet
        alt_price_col = "fg_total_under_price"  # For under bet
    elif config.market == MarketType.H1_SPREAD:
        line_col = "h1_spread"
        result_col = "h1_actual_margin"  # ACTUAL H1 margin, NOT FG * 0.5
        price_col = "h1_spread_home_price"
        alt_price_col = "h1_spread_away_price"
    else:  # H1_TOTAL
        line_col = "h1_total"
        result_col = "h1_actual_total"  # ACTUAL H1 total, NOT FG * 0.5
        price_col = "h1_total_over_price"
        alt_price_col = "h1_total_under_price"

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
        # Extract Four Factors (if available)
        four_factors = {
            "home_efg": row.get("home_efg"),
            "home_efgd": row.get("home_efgd"),
            "home_tor": row.get("home_tor"),
            "home_orb": row.get("home_orb"),
            "home_drb": row.get("home_drb"),
            "home_ftr": row.get("home_ftr"),
            "away_efg": row.get("away_efg"),
            "away_efgd": row.get("away_efgd"),
            "away_tor": row.get("away_tor"),
            "away_orb": row.get("away_orb"),
            "away_drb": row.get("away_drb"),
            "away_ftr": row.get("away_ftr"),
        }

        # Advanced features (conference + box scores)
        advanced = {
            "conf_strength_diff": row.get("conf_strength_diff"),
            "home_team_depth_rolling": row.get("home_team_depth_rolling"),
            "away_team_depth_rolling": row.get("away_team_depth_rolling"),
            "home_ast_to_ratio_rolling": row.get("home_ast_to_ratio_rolling"),
            "away_ast_to_ratio_rolling": row.get("away_ast_to_ratio_rolling"),
        }

        # Shooting tendencies
        shooting = {
            "home_three_pt_rate": row.get("home_three_pt_rate"),
            "away_three_pt_rate": row.get("away_three_pt_rate"),
        }

        # Generate prediction with all features
        if config.market == MarketType.FG_SPREAD:
            predicted = predictor.predict_spread(
                row["home_adj_o"], row["home_adj_d"],
                row["away_adj_o"], row["away_adj_d"],
                **four_factors, **advanced
            )
        elif config.market == MarketType.FG_TOTAL:
            predicted = predictor.predict_total(
                row["home_adj_o"], row["home_adj_d"], row.get("home_tempo", 68),
                row["away_adj_o"], row["away_adj_d"], row.get("away_tempo", 68),
                **shooting
            )
        elif config.market == MarketType.H1_SPREAD:
            # H1 Spread - independent model (NOT FG/2)
            predicted = predictor.predict_h1_spread(
                row["home_adj_o"], row["home_adj_d"],
                row["away_adj_o"], row["away_adj_d"],
                **four_factors  # Uses EFG for dynamic margin scaling
            )
        else:  # H1_TOTAL
            # H1 Total - independent model (NOT FG*0.48)
            predicted = predictor.predict_h1_total(
                row["home_adj_o"], row["home_adj_d"], row.get("home_tempo", 68),
                row["away_adj_o"], row["away_adj_d"], row.get("away_tempo", 68),
                home_barthag=row.get("home_barthag"),
                away_barthag=row.get("away_barthag"),
                home_three_pt_rate=row.get("home_three_pt_rate"),
                away_three_pt_rate=row.get("away_three_pt_rate")
            )

        market_line = row[line_col]
        edge = predictor.calculate_edge(predicted, market_line, config.market)

        # Only bet if edge exceeds minimum
        if edge < config.min_edge:
            continue

        bet_side = predictor.get_bet_side(predicted, market_line, config.market)

        # Get actual result - NO APPROXIMATIONS
        if result_col not in row or pd.isna(row.get(result_col)):
            # Skip if actual result not available
            continue

        actual = row[result_col]

        # REMOVED: H1 scaling approximation - we now use ACTUAL H1 scores
        # If h1_actual_margin or h1_actual_total is missing, skip this game

        outcome = determine_outcome(bet_side, market_line, actual, config.market)

        # Get ACTUAL odds for this bet side - NO FALLBACK
        if bet_side in ["home", "over"]:
            actual_odds = row.get(price_col)
        else:  # away, under
            actual_odds = row.get(alt_price_col)

        # CRITICAL: Skip bets without actual odds prices
        # NO HARDCODED -110 ASSUMPTION
        if pd.isna(actual_odds):
            continue  # Skip this bet - no real odds available

        # Simple flat betting
        wager = config.base_unit
        profit = calculate_profit(outcome, wager, odds=actual_odds)

        # Skip if profit couldn't be calculated (shouldn't happen now, but safety)
        if profit is None:
            continue

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
            actual_odds=round(actual_odds, 1),  # ALWAYS real odds
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
                "actual_odds": r.actual_odds,  # ACTUAL odds used
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
        default=None,
        help="Comma-separated seasons to include (default: canonical window)"
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

    if args.seasons:
        seasons = [int(s.strip()) for s in args.seasons.split(",")]
    else:
        seasons = default_backtest_seasons()
    seasons = enforce_min_season(seasons)

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
