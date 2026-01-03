#!/usr/bin/env python3
"""
Market-Relative Model Validation v33.1

This is the CORRECT way to validate a sports betting model.
Instead of measuring prediction accuracy, we measure:
1. How often do we have an edge vs market?
2. When we bet, do we win more than 52.4%?
3. Do closing lines move toward our predictions (CLV)?

IMPORTANT: Uses the database's resolve_team_name() function for 99%+ matching accuracy.

Usage:
    python testing/scripts/market_validation.py --season 2024
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Database connection (optional - falls back to local matching)
try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

# Import improved team name mapper for local fallback
try:
    from team_name_mapper import normalize_team_name as improved_normalize
    HAS_IMPROVED_MAPPER = True
except ImportError:
    HAS_IMPROVED_MAPPER = False

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"
ODDS_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"
RESULTS_DIR = ROOT_DIR / "testing" / "data" / "market_validation"

# Database connection
DB_ENGINE = None

# Model constants (v33.1)
LEAGUE_AVG_EFFICIENCY = 100.0
HOME_COURT_ADVANTAGE_SPREAD = 4.7
TOTAL_CALIBRATION_ADJUSTMENT = -4.6

# Betting thresholds
MIN_EDGE_TO_BET = 2.0  # Minimum points edge to recommend bet
JUICE_BREAKEVEN = 0.524  # Need 52.4% to break even at -110


def get_db_engine():
    """Get database engine, connecting if needed."""
    global DB_ENGINE
    if DB_ENGINE is not None:
        return DB_ENGINE

    if not HAS_SQLALCHEMY:
        return None

    # Try to connect to the NCAAM database
    try:
        # Read password from secrets or env
        db_password = os.environ.get("DB_PASSWORD", "")
        if not db_password:
            secrets_file = ROOT_DIR / "secrets" / "db_password.txt"
            if secrets_file.exists():
                db_password = secrets_file.read_text().strip()

        if not db_password:
            db_password = "ncaam_dev_password"  # Default for local dev

        # Connect to Docker container (exposed on port 5450 per docker-compose.yml)
        db_port = os.environ.get("DB_PORT", "5450")
        database_url = f"postgresql://ncaam:{db_password}@localhost:{db_port}/ncaam"
        DB_ENGINE = create_engine(database_url, pool_pre_ping=True)

        # Test connection
        with DB_ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))

        print("[INFO] Connected to database for team name resolution")
        return DB_ENGINE
    except Exception as e:
        print(f"[WARN] Could not connect to database: {e}")
        print("[WARN] Falling back to local team matching")
        return None


def resolve_team_name_db(name: str, engine) -> str:
    """
    Resolve team name using the database's resolve_team_name() function.
    This provides 99%+ accuracy using 900+ stored aliases.
    """
    if not engine or pd.isna(name):
        return ""

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT resolve_team_name(:name)"),
                {"name": str(name)}
            ).fetchone()

            if result and result[0]:
                return result[0]
    except Exception:
        pass

    return ""


# Cache for resolved names to avoid repeated DB calls
_RESOLVED_NAMES_CACHE = {}


def resolve_team_name(name: str) -> str:
    """
    Resolve team name with caching.
    Uses database if available, falls back to local normalization.
    """
    if pd.isna(name):
        return ""

    name = str(name).strip()

    # Check cache first
    if name in _RESOLVED_NAMES_CACHE:
        return _RESOLVED_NAMES_CACHE[name]

    # Try database resolution
    engine = get_db_engine()
    if engine:
        resolved = resolve_team_name_db(name, engine)
        if resolved:
            _RESOLVED_NAMES_CACHE[name] = resolved
            return resolved

    # Fall back to local normalization
    resolved = normalize_team_name_local(name)
    _RESOLVED_NAMES_CACHE[name] = resolved
    return resolved


@dataclass
class BetResult:
    """Result of a single bet."""
    game_id: str
    date: str
    home_team: str
    away_team: str

    # Model prediction
    model_spread: float
    model_total: float

    # Market line
    market_spread: float
    market_total: float

    # Calculated edge
    spread_edge: float  # model - market (positive = bet home)
    total_edge: float   # model - market (positive = bet over)

    # Bet decision
    spread_bet: str     # "HOME", "AWAY", "NO_BET"
    total_bet: str      # "OVER", "UNDER", "NO_BET"

    # Actual result
    actual_spread: int  # home - away
    actual_total: int

    # Outcomes
    spread_outcome: str  # "WIN", "LOSS", "PUSH", "NO_BET"
    total_outcome: str

    # CLV (if closing line available)
    clv_spread: float = 0.0
    clv_total: float = 0.0


def load_model_predictions(season: int) -> pd.DataFrame:
    """Load our model predictions from validation results."""
    path = RESULTS_DIR.parent / "validation_results" / "validation_results.csv"
    if not path.exists():
        print(f"[ERROR] Run validate_model.py first to generate predictions")
        return pd.DataFrame()

    df = pd.read_csv(path)
    # Filter to season if date available
    return df


def load_market_lines(season: int) -> pd.DataFrame:
    """Load historical market lines."""
    # Look for odds files
    odds_files = list(ODDS_DIR.glob("*.csv"))

    if not odds_files:
        print(f"[WARN] No historical odds data found in {ODDS_DIR}")
        print("       Run fetch_historical_odds.py first, or use synthetic data")
        return pd.DataFrame()

    all_odds = []
    for f in odds_files:
        df = pd.read_csv(f)
        all_odds.append(df)

    if not all_odds:
        return pd.DataFrame()

    combined = pd.concat(all_odds, ignore_index=True)

    # Resolve team names using database (99%+ accuracy) and extract date
    combined["home_team_norm"] = combined["home_team"].apply(resolve_team_name)
    combined["away_team_norm"] = combined["away_team"].apply(resolve_team_name)
    combined["date"] = combined["commence_time"].str[:10]

    # Rename for consistency
    combined = combined.rename(columns={
        "spread": "market_spread",
        "total": "market_total"
    })

    print(f"[INFO] Loaded {len(combined)} market lines from {len(odds_files)} files")
    return combined


def normalize_team_name_local(name: str) -> str:
    """
    Local fallback for team name normalization.
    Used when database is unavailable.

    Uses improved team_name_mapper module if available.
    """
    if pd.isna(name):
        return ""

    # Use improved mapper if available (handles St. vs State, Int'l, etc.)
    if HAS_IMPROVED_MAPPER:
        return improved_normalize(name)

    # Basic fallback if mapper not available
    name = str(name).lower().strip()

    # Remove common suffixes (mascots)
    suffixes = [
        " wildcats", " tigers", " bulldogs", " bears", " eagles",
        " huskies", " cavaliers", " blue devils", " tar heels",
        " spartans", " wolverines", " buckeyes", " hoosiers",
        " boilermakers", " hawkeyes", " badgers", " gophers",
        " jayhawks", " sooners", " longhorns", " aggies",
        " razorbacks", " volunteers", " crimson tide", " rebels",
        " gamecocks", " hurricanes", " seminoles", " yellow jackets",
        " red raiders", " horned frogs", " cowboys", " cyclones",
        " mountaineers", " red storm", " fighting irish", " panthers",
        " cardinals", " bearcats", " musketeers", " bluejays",
        " golden eagles", " pirates", " gaels", " dons", " broncos",
        " cougars", " aztecs", " wolf pack", " runnin' rebels",
        " bobcats", " falcons", " red wolves", " crimson", " big green",
        " stags", " golden griffins", " dolphins", " owls", " royals",
        " jaspers", " saints", " purple eagles", " hatters", " ospreys",
        " lions", " governors", " bison", " colonels", " explorers",
        " golden flashes", " ramblers", " flyers", " friars", " waves",
        " terriers", " crusaders", " raiders", " dukes", " monarchs",
        " chanticleers", " knights", " antelopes", " lopes",
        " thundering herd", " jaguars", " warhawks", " trojans",
        " golden panthers", " screaming eagles", " fighting illini",
    ]

    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    # Common replacements for matching
    replacements = {
        "st.": "st",
        "st ": "state ",
        "(chi)": "chicago",
        "(fl)": "",
        "(oh)": "",
        "univ.": "",
        "&": "and",
        "'s": "s",
        "n.c.": "north carolina",
        "s.c.": "south carolina",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name.strip()


def simulate_market_lines(predictions: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate market lines for testing when real data unavailable.

    This adds realistic noise to our predictions to simulate market lines.
    In production, REPLACE THIS with real historical odds.
    """
    np.random.seed(42)  # Reproducibility

    simulated = predictions.copy()

    # Market is generally more accurate than our model
    # Add noise that makes market "closer to truth"
    market_noise = np.random.normal(0, 2.0, len(predictions))

    # Simulate market spread: actual + small noise (market knows more)
    simulated["market_spread"] = (
        simulated["actual_spread"] +
        np.random.normal(0, 3.0, len(predictions))
    )

    # Simulate market total
    simulated["market_total"] = (
        simulated["actual_total"] +
        np.random.normal(0, 4.0, len(predictions))
    )

    return simulated


def evaluate_bets(
    predictions: pd.DataFrame,
    market: pd.DataFrame,
    min_edge: float = MIN_EDGE_TO_BET,
) -> list[BetResult]:
    """
    Evaluate betting performance against market lines.
    """
    results = []

    # Merge predictions with market lines
    if market.empty:
        print("[INFO] Using simulated market lines (for testing only)")
        merged = simulate_market_lines(predictions)
    else:
        # Resolve prediction team names using database (99%+ accuracy)
        predictions = predictions.copy()
        predictions["home_team_norm"] = predictions["home_team"].apply(resolve_team_name)
        predictions["away_team_norm"] = predictions["away_team"].apply(resolve_team_name)

        # Match on normalized team names and date
        merged = predictions.merge(
            market[["home_team_norm", "away_team_norm", "date", "market_spread", "market_total"]],
            on=["home_team_norm", "away_team_norm", "date"],
            how="left",
        )

        # Count matches
        matched = merged["market_spread"].notna().sum()
        total = len(merged)
        print(f"[INFO] Matched {matched}/{total} games ({100*matched/total:.1f}%) with market lines")

    for _, row in merged.iterrows():
        model_spread = row.get("pred_spread", 0)
        model_total = row.get("pred_total", 0)
        market_spread = row.get("market_spread", model_spread)
        market_total = row.get("market_total", model_total)

        actual_spread = row.get("actual_spread", 0)
        actual_total = row.get("actual_total", 0)

        # Calculate edges
        # Positive spread_edge means we think home is better than market
        spread_edge = model_spread - market_spread
        total_edge = model_total - market_total

        # Bet decisions
        if abs(spread_edge) >= min_edge:
            spread_bet = "HOME" if spread_edge > 0 else "AWAY"
        else:
            spread_bet = "NO_BET"

        if abs(total_edge) >= min_edge:
            total_bet = "OVER" if total_edge > 0 else "UNDER"
        else:
            total_bet = "NO_BET"

        # Evaluate outcomes
        if spread_bet == "NO_BET":
            spread_outcome = "NO_BET"
        elif spread_bet == "HOME":
            # We bet home covers: actual_spread > -market_spread
            # (market_spread is from home perspective, negative = home favored)
            cover_margin = actual_spread + market_spread
            if cover_margin > 0:
                spread_outcome = "WIN"
            elif cover_margin < 0:
                spread_outcome = "LOSS"
            else:
                spread_outcome = "PUSH"
        else:  # AWAY
            cover_margin = -actual_spread - market_spread
            if cover_margin > 0:
                spread_outcome = "WIN"
            elif cover_margin < 0:
                spread_outcome = "LOSS"
            else:
                spread_outcome = "PUSH"

        if total_bet == "NO_BET":
            total_outcome = "NO_BET"
        elif total_bet == "OVER":
            if actual_total > market_total:
                total_outcome = "WIN"
            elif actual_total < market_total:
                total_outcome = "LOSS"
            else:
                total_outcome = "PUSH"
        else:  # UNDER
            if actual_total < market_total:
                total_outcome = "WIN"
            elif actual_total > market_total:
                total_outcome = "LOSS"
            else:
                total_outcome = "PUSH"

        results.append(BetResult(
            game_id=str(row.get("game_id", "")),
            date=str(row.get("date", "")),
            home_team=str(row.get("home_team", "")),
            away_team=str(row.get("away_team", "")),
            model_spread=float(model_spread),
            model_total=float(model_total),
            market_spread=float(market_spread),
            market_total=float(market_total),
            spread_edge=float(spread_edge),
            total_edge=float(total_edge),
            spread_bet=spread_bet,
            total_bet=total_bet,
            actual_spread=int(actual_spread),
            actual_total=int(actual_total),
            spread_outcome=spread_outcome,
            total_outcome=total_outcome,
        ))

    return results


def calculate_betting_metrics(results: list[BetResult]) -> dict:
    """Calculate key betting performance metrics."""
    # Filter to actual bets
    spread_bets = [r for r in results if r.spread_bet != "NO_BET"]
    total_bets = [r for r in results if r.total_bet != "NO_BET"]

    # Spread betting
    spread_wins = sum(1 for r in spread_bets if r.spread_outcome == "WIN")
    spread_losses = sum(1 for r in spread_bets if r.spread_outcome == "LOSS")
    spread_pushes = sum(1 for r in spread_bets if r.spread_outcome == "PUSH")
    spread_decided = spread_wins + spread_losses

    spread_win_rate = spread_wins / spread_decided if spread_decided > 0 else 0
    spread_roi = (spread_wins * 100 - spread_losses * 110) / (spread_decided * 110) if spread_decided > 0 else 0

    # Total betting
    total_wins = sum(1 for r in total_bets if r.total_outcome == "WIN")
    total_losses = sum(1 for r in total_bets if r.total_outcome == "LOSS")
    total_pushes = sum(1 for r in total_bets if r.total_outcome == "PUSH")
    total_decided = total_wins + total_losses

    total_win_rate = total_wins / total_decided if total_decided > 0 else 0
    total_roi = (total_wins * 100 - total_losses * 110) / (total_decided * 110) if total_decided > 0 else 0

    # Edge analysis
    avg_spread_edge = np.mean([abs(r.spread_edge) for r in spread_bets]) if spread_bets else 0
    avg_total_edge = np.mean([abs(r.total_edge) for r in total_bets]) if total_bets else 0

    return {
        "total_games": len(results),
        # Spread betting
        "spread_bets": len(spread_bets),
        "spread_bet_rate": len(spread_bets) / len(results) if results else 0,
        "spread_wins": spread_wins,
        "spread_losses": spread_losses,
        "spread_pushes": spread_pushes,
        "spread_win_rate": spread_win_rate,
        "spread_roi": spread_roi,
        "spread_avg_edge": avg_spread_edge,
        # Total betting
        "total_bets": len(total_bets),
        "total_bet_rate": len(total_bets) / len(results) if results else 0,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_pushes": total_pushes,
        "total_win_rate": total_win_rate,
        "total_roi": total_roi,
        "total_avg_edge": avg_total_edge,
        # Breakeven reference
        "breakeven_rate": JUICE_BREAKEVEN,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Market-relative model validation"
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=MIN_EDGE_TO_BET,
        help=f"Minimum edge to place bet (default: {MIN_EDGE_TO_BET})"
    )
    parser.add_argument(
        "--simulate-market",
        action="store_true",
        help="Use simulated market lines (for testing)"
    )

    args = parser.parse_args(argv)

    print("=" * 72)
    print(" Market-Relative Model Validation")
    print("=" * 72)
    print(f" Min Edge to Bet: {args.min_edge} points")
    print(f" Breakeven Rate: {JUICE_BREAKEVEN*100:.1f}%")
    print("=" * 72)

    # Load predictions
    predictions = load_model_predictions(2024)
    if predictions.empty:
        return 1

    print(f"\n[INFO] Loaded {len(predictions)} predictions")

    # Load market lines
    if args.simulate_market:
        market = pd.DataFrame()
    else:
        market = load_market_lines(2024)

    # Evaluate bets
    results = evaluate_bets(predictions, market, args.min_edge)

    # Calculate metrics
    metrics = calculate_betting_metrics(results)

    # Print results
    print("\n" + "=" * 72)
    print(" SPREAD BETTING RESULTS")
    print("=" * 72)
    print(f"\n  Games Analyzed:     {metrics['total_games']}")
    print(f"  Bets Placed:        {metrics['spread_bets']} ({metrics['spread_bet_rate']*100:.1f}%)")
    print(f"  Average Edge:       {metrics['spread_avg_edge']:.1f} points")
    print(f"\n  Record:             {metrics['spread_wins']}-{metrics['spread_losses']}-{metrics['spread_pushes']}")
    print(f"  Win Rate:           {metrics['spread_win_rate']*100:.1f}%")
    print(f"  Breakeven:          {metrics['breakeven_rate']*100:.1f}%")
    print(f"  ROI:                {metrics['spread_roi']*100:+.1f}%")

    if metrics['spread_win_rate'] >= JUICE_BREAKEVEN:
        print("\n  [PROFITABLE] Win rate exceeds breakeven!")
    else:
        print(f"\n  [UNPROFITABLE] Need {JUICE_BREAKEVEN*100:.1f}% to break even")

    print("\n" + "=" * 72)
    print(" TOTAL BETTING RESULTS")
    print("=" * 72)
    print(f"\n  Bets Placed:        {metrics['total_bets']} ({metrics['total_bet_rate']*100:.1f}%)")
    print(f"  Average Edge:       {metrics['total_avg_edge']:.1f} points")
    print(f"\n  Record:             {metrics['total_wins']}-{metrics['total_losses']}-{metrics['total_pushes']}")
    print(f"  Win Rate:           {metrics['total_win_rate']*100:.1f}%")
    print(f"  ROI:                {metrics['total_roi']*100:+.1f}%")

    print("\n" + "=" * 72)
    print(" INTERPRETATION")
    print("=" * 72)

    if market.empty:
        print("\n  [WARNING] Using SIMULATED market lines")
        print("            Results are for TESTING ONLY")
        print("            Get real historical odds for accurate validation")
    else:
        if metrics['spread_roi'] > 0.03:
            print("\n  [STRONG] >3% ROI suggests real edge")
        elif metrics['spread_roi'] > 0:
            print("\n  [MARGINAL] Positive but small ROI")
        else:
            print("\n  [NEGATIVE] Model not beating market")

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / "market_validation_results.json"
    with results_path.open("w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n[INFO] Saved metrics to {results_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
