#!/usr/bin/env python3
"""
NCAAM Model Validation - Using REAL Historical Data

This script validates the prediction model against actual game outcomes.
Unlike run_backtest.py which simulates outcomes, this uses real ESPN data.

Key Features:
- Uses real game results from ESPN API
- Uses Barttorvik end-of-season ratings (conservative approach)
- Calculates true MAE, hit rate, and calibration
- No simulation or fake data

Usage:
    python testing/scripts/validate_model.py --season 2024
    python testing/scripts/validate_model.py --seasons 2020-2024 --output results.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"
KAGGLE_DIR = ROOT_DIR / "testing" / "data" / "kaggle"
RESULTS_DIR = ROOT_DIR / "testing" / "data" / "validation_results"


# ==================== Model Constants ====================
# These match the production model in predictor.py
# v33.1 CALIBRATED VALUES from 4194-game backtest
LEAGUE_AVG_EFFICIENCY = 100.0
HOME_COURT_ADVANTAGE_SPREAD = 4.7  # was 3.2, calibrated to 4.7
HOME_COURT_ADVANTAGE_TOTAL = 0.0  # negligible effect on totals
TOTAL_CALIBRATION_ADJUSTMENT = -4.6  # was 0, calibrated to -4.6

# Matchup adjustment weights (controversial - may double-count)
ORB_WEIGHT = 0.15
TOR_WEIGHT = 0.10
FTR_WEIGHT = 0.15


@dataclass
class TeamRatings:
    """Team efficiency ratings."""
    name: str
    adj_o: float  # Adjusted Offensive Efficiency
    adj_d: float  # Adjusted Defensive Efficiency
    adj_t: float  # Adjusted Tempo
    orb: float = 30.0   # Offensive Rebound %
    drb: float = 70.0   # Defensive Rebound %
    tor: float = 17.0   # Turnover Rate
    tord: float = 17.0  # Forced Turnover Rate
    ftr: float = 30.0   # Free Throw Rate


@dataclass
class Prediction:
    """Model prediction for a game."""
    home_score: float
    away_score: float
    spread: float  # positive = home favored
    total: float
    tempo: float


@dataclass
class ValidationResult:
    """Result of validating one game."""
    game_id: str
    date: str
    home_team: str
    away_team: str

    # Actual outcome
    actual_home_score: int
    actual_away_score: int
    actual_spread: int  # home - away
    actual_total: int

    # Predictions
    pred_spread: float
    pred_total: float

    # Errors
    spread_error: float  # pred - actual (positive = overestimated home)
    total_error: float   # pred - actual
    spread_abs_error: float
    total_abs_error: float

    # For ATS betting simulation (no real lines, just vs prediction)
    spread_direction_correct: bool  # Did we pick correct side?


def load_barttorvik_ratings(season: int) -> dict[str, TeamRatings]:
    """Load Barttorvik ratings for a season."""
    ratings = {}

    # Try historical JSON first
    json_path = HISTORICAL_DIR / f"barttorvik_{season}.json"
    if json_path.exists():
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        for team_data in data:
            if not isinstance(team_data, list) or len(team_data) < 10:
                continue

            name = team_data[1]
            ratings[name.lower()] = TeamRatings(
                name=name,
                adj_o=float(team_data[4]),   # Adjusted O
                adj_d=float(team_data[6]),   # Adjusted D
                adj_t=float(team_data[44]) if len(team_data) > 44 else 68.0,
                orb=float(team_data[21]) if len(team_data) > 21 else 30.0,
                drb=float(team_data[22]) if len(team_data) > 22 else 70.0,
            )
        print(f"[INFO] Loaded {len(ratings)} teams from Barttorvik JSON")
        return ratings

    # Fallback to Kaggle CSV
    csv_path = KAGGLE_DIR / f"cbb{str(season)[-2:]}.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        for _, row in df.iterrows():
            name = str(row.get("TEAM", "")).strip()
            if not name:
                continue
            ratings[name.lower()] = TeamRatings(
                name=name,
                adj_o=float(row.get("ADJOE", 100)),
                adj_d=float(row.get("ADJDE", 100)),
                adj_t=float(row.get("ADJ_T", 68)),
                orb=float(row.get("ORB", 30)),
                drb=float(row.get("DRB", 70)),
                tor=float(row.get("TOR", 17)),
                tord=float(row.get("TORD", 17)),
                ftr=float(row.get("FTR", 30)),
            )
        print(f"[INFO] Loaded {len(ratings)} teams from Kaggle CSV")
        return ratings

    print(f"[WARN] No ratings found for season {season}")
    return ratings


def load_game_results(season: int) -> pd.DataFrame:
    """Load game results from ESPN data."""
    csv_path = HISTORICAL_DIR / f"games_{season}.csv"
    if not csv_path.exists():
        print(f"[ERROR] No game data for season {season}. Run fetch_historical_data.py first.")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    print(f"[INFO] Loaded {len(df)} games for season {season}")
    return df


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    name = name.lower().strip()

    # Common replacements
    replacements = {
        "uconn": "connecticut",
        "uconn huskies": "connecticut",
        "pitt": "pittsburgh",
        "pitt panthers": "pittsburgh",
        "ole miss": "mississippi",
        "ole miss rebels": "mississippi",
        "umass": "massachusetts",
        "vcu": "virginia commonwealth",
        "lsu": "louisiana state",
        "lsu tigers": "louisiana state",
        "ucf": "central florida",
        "ucf knights": "central florida",
        "usc": "southern california",
        "usc trojans": "southern california",
        "smu": "southern methodist",
        "smu mustangs": "southern methodist",
        "tcu": "texas christian",
        "tcu horned frogs": "texas christian",
        "byu": "brigham young",
        "byu cougars": "brigham young",
    }

    for abbr, full in replacements.items():
        if name == abbr or name.startswith(abbr + " "):
            return full

    # Remove common suffixes
    suffixes = [
        " wildcats", " tigers", " bulldogs", " bears", " eagles",
        " huskies", " cavaliers", " blue devils", " tar heels",
        " spartans", " wolverines", " buckeyes", " hoosiers",
        " boilermakers", " hawkeyes", " badgers", " gophers",
        " cornhuskers", " jayhawks", " sooners", " longhorns",
        " aggies", " razorbacks", " volunteers", " crimson tide",
        " rebels", " gamecocks", " hurricanes", " seminoles",
        " yellow jackets", " red raiders", " horned frogs",
        " cowboys", " cyclones", " mountaineers", " red storm",
        " fighting irish", " panthers", " cardinals", " bearcats",
        " musketeers", " billikens", " bluejays", " golden eagles",
        " pirates", " colonials", " explorers", " hawks", " owls",
        " gaels", " zags", " dons", " toreros", " broncos",
        " cougars", " aztecs", " wolf pack", " runnin' rebels",
    ]

    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    return name.strip()


def find_team_rating(team_name: str, ratings: dict[str, TeamRatings]) -> Optional[TeamRatings]:
    """Find team rating with fuzzy matching."""
    normalized = normalize_team_name(team_name)

    # Direct match
    if normalized in ratings:
        return ratings[normalized]

    # Partial match
    for key, rating in ratings.items():
        if normalized in key or key in normalized:
            return rating

    return None


def predict_game(
    home: TeamRatings,
    away: TeamRatings,
    neutral_site: bool = False
) -> Prediction:
    """Generate prediction using the production model formula."""

    # Predicted tempo (possessions per 40 min)
    tempo = (home.adj_t + away.adj_t) / 2

    # Expected efficiency (points per 100 possessions)
    home_eff = home.adj_o + away.adj_d - LEAGUE_AVG_EFFICIENCY
    away_eff = away.adj_o + home.adj_d - LEAGUE_AVG_EFFICIENCY

    # Convert to points (scale by tempo)
    home_score = home_eff * tempo / 100
    away_score = away_eff * tempo / 100

    # Apply home court advantage
    if not neutral_site:
        home_score += HOME_COURT_ADVANTAGE_SPREAD / 2
        away_score -= HOME_COURT_ADVANTAGE_SPREAD / 2

    spread = home_score - away_score
    total = home_score + away_score + TOTAL_CALIBRATION_ADJUSTMENT

    return Prediction(
        home_score=home_score,
        away_score=away_score,
        spread=spread,
        total=total,
        tempo=tempo,
    )


def validate_season(
    season: int,
    ratings: dict[str, TeamRatings],
    games: pd.DataFrame,
    prior_ratings: dict[str, TeamRatings] | None = None,
    verbose: bool = True,
) -> list[ValidationResult]:
    """Validate model against all games in a season.

    Args:
        season: The season year (e.g., 2024 for 2023-24 season)
        ratings: End-of-season ratings for current season
        games: DataFrame of games to validate
        prior_ratings: Prior season's ratings (used for Nov-Dec games to avoid data leakage)
        verbose: Print progress
    """
    results = []
    matched = 0
    unmatched = 0

    for _, row in games.iterrows():
        home_team = str(row["home_team"])
        away_team = str(row["away_team"])

        # DATA LEAKAGE FIX: Use prior season ratings for early-season games
        # Games in Nov-Dec should use prior year's ratings since current year isn't stable
        game_date = str(row.get("date", ""))
        use_prior = False
        if prior_ratings and game_date:
            month = int(game_date[5:7]) if len(game_date) >= 7 else 0
            # Nov (11) and Dec (12) are early season - use prior ratings
            if month in (11, 12):
                use_prior = True

        active_ratings = prior_ratings if use_prior and prior_ratings else ratings

        home_rating = find_team_rating(home_team, active_ratings)
        away_rating = find_team_rating(away_team, active_ratings)

        if not home_rating or not away_rating:
            unmatched += 1
            continue

        matched += 1

        # Get actual scores
        actual_home = int(row["home_score"])
        actual_away = int(row["away_score"])
        actual_spread = actual_home - actual_away
        actual_total = actual_home + actual_away

        # Generate prediction
        neutral = bool(row.get("neutral", False))
        pred = predict_game(home_rating, away_rating, neutral)

        # Calculate errors
        spread_error = pred.spread - actual_spread
        total_error = pred.total - actual_total

        # Direction check: did we correctly predict who would cover?
        # If pred.spread > 0, we predict home wins. If actual_spread > 0, home won.
        spread_direction_correct = (pred.spread > 0) == (actual_spread > 0)

        results.append(ValidationResult(
            game_id=str(row.get("game_id", "")),
            date=str(row.get("date", "")),
            home_team=home_team,
            away_team=away_team,
            actual_home_score=actual_home,
            actual_away_score=actual_away,
            actual_spread=actual_spread,
            actual_total=actual_total,
            pred_spread=round(pred.spread, 2),
            pred_total=round(pred.total, 2),
            spread_error=round(spread_error, 2),
            total_error=round(total_error, 2),
            spread_abs_error=round(abs(spread_error), 2),
            total_abs_error=round(abs(total_error), 2),
            spread_direction_correct=spread_direction_correct,
        ))

    if verbose:
        print(f"[INFO] Matched {matched} games, {unmatched} unmatched")

    return results


def calculate_metrics(results: list[ValidationResult]) -> dict:
    """Calculate summary metrics from validation results."""
    if not results:
        return {}

    spread_errors = [r.spread_abs_error for r in results]
    total_errors = [r.total_abs_error for r in results]
    direction_correct = [1 if r.spread_direction_correct else 0 for r in results]

    # Filter to "bettable" games (predicted margin < 20 points)
    bettable = [r for r in results if abs(r.pred_spread) < 20]
    bettable_spread_errors = [r.spread_abs_error for r in bettable]
    bettable_direction = [1 if r.spread_direction_correct else 0 for r in bettable]

    return {
        "games_validated": len(results),
        "spread_mae": round(np.mean(spread_errors), 2),
        "spread_rmse": round(np.sqrt(np.mean([e**2 for e in spread_errors])), 2),
        "spread_std": round(np.std([r.spread_error for r in results]), 2),
        "total_mae": round(np.mean(total_errors), 2),
        "total_rmse": round(np.sqrt(np.mean([e**2 for e in total_errors])), 2),
        "total_std": round(np.std([r.total_error for r in results]), 2),
        "spread_direction_accuracy": round(np.mean(direction_correct) * 100, 1),
        "spread_bias": round(np.mean([r.spread_error for r in results]), 2),
        "total_bias": round(np.mean([r.total_error for r in results]), 2),
        # Bettable-only metrics (|margin| < 20)
        "bettable_games": len(bettable),
        "bettable_spread_mae": round(np.mean(bettable_spread_errors), 2) if bettable else 0,
        "bettable_direction_accuracy": round(np.mean(bettable_direction) * 100, 1) if bettable else 0,
    }


def save_results_csv(results: list[ValidationResult], filepath: Path) -> None:
    """Save validation results to CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("w", newline="", encoding="utf-8") as f:
        if not results:
            return

        writer = csv.DictWriter(f, fieldnames=results[0].__dict__.keys())
        writer.writeheader()
        for r in results:
            writer.writerow(r.__dict__)

    print(f"[INFO] Saved {len(results)} results to {filepath}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate NCAAM prediction model against real game data"
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2024,
        help="Single season to validate"
    )
    parser.add_argument(
        "--seasons",
        type=str,
        help="Range of seasons (e.g., '2020-2024')"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output CSV file for detailed results"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-game details"
    )

    args = parser.parse_args(argv)

    # Determine seasons to validate
    if args.seasons:
        start, end = map(int, args.seasons.split("-"))
        seasons = list(range(start, end + 1))
    else:
        seasons = [args.season]

    print("=" * 72)
    print(" NCAAM Model Validation - Real Data")
    print("=" * 72)
    print(f" Seasons: {seasons}")
    print(f" Model: Barttorvik Efficiency + HCA={HOME_COURT_ADVANTAGE_SPREAD}")
    print("=" * 72)
    print()

    all_results = []

    # Pre-load all ratings to enable prior-season lookup
    all_ratings = {}
    for s in range(min(seasons) - 1, max(seasons) + 1):
        r = load_barttorvik_ratings(s)
        if r:
            all_ratings[s] = r

    for season in seasons:
        print(f"\n{'='*40}")
        print(f" Season {season-1}-{str(season)[-2:]}")
        print(f"{'='*40}")

        ratings = all_ratings.get(season)
        if not ratings:
            print(f"[WARN] No ratings for {season}")
            continue

        games = load_game_results(season)
        if games.empty:
            continue

        # Get prior season ratings to avoid data leakage
        prior_ratings = all_ratings.get(season - 1)
        if prior_ratings:
            print(f"[INFO] Using prior season ratings for Nov-Dec games")

        results = validate_season(season, ratings, games, prior_ratings, verbose=True)
        all_results.extend(results)

        metrics = calculate_metrics(results)
        if metrics:
            print(f"\n  Spread MAE:     {metrics['spread_mae']} points")
            print(f"  Spread RMSE:    {metrics['spread_rmse']} points")
            print(f"  Spread Bias:    {metrics['spread_bias']:+.2f} (+ = overestimate home)")
            print(f"  Direction Acc:  {metrics['spread_direction_accuracy']}%")
            print(f"  Total MAE:      {metrics['total_mae']} points")
            print(f"  Total RMSE:     {metrics['total_rmse']} points")

    # Overall summary
    if all_results:
        print("\n" + "=" * 72)
        print(" OVERALL RESULTS")
        print("=" * 72)

        overall = calculate_metrics(all_results)
        print(f"\n  Games Validated:  {overall['games_validated']}")
        print(f"\n  SPREAD:")
        print(f"    MAE:           {overall['spread_mae']} points")
        print(f"    RMSE:          {overall['spread_rmse']} points")
        print(f"    Std Dev:       {overall['spread_std']} points")
        print(f"    Bias:          {overall['spread_bias']:+.2f}")
        print(f"    Direction:     {overall['spread_direction_accuracy']}%")
        print(f"\n  TOTAL:")
        print(f"    MAE:           {overall['total_mae']} points")
        print(f"    RMSE:          {overall['total_rmse']} points")
        print(f"    Std Dev:       {overall['total_std']} points")
        print(f"    Bias:          {overall['total_bias']:+.2f}")

        # Bettable-only metrics
        print("\n  BETTABLE GAMES (|predicted margin| < 20):")
        print(f"    Games:         {overall['bettable_games']} ({100*overall['bettable_games']/overall['games_validated']:.1f}%)")
        print(f"    Spread MAE:    {overall['bettable_spread_mae']} points")
        print(f"    Direction:     {overall['bettable_direction_accuracy']}%")

        # Interpretation
        print("\n" + "=" * 72)
        print(" INTERPRETATION")
        print("=" * 72)

        if overall['bettable_spread_mae'] > 10:
            print("  [WARNING] Bettable Spread MAE > 10 points is poor predictive power")
        elif overall['bettable_spread_mae'] > 8:
            print("  [CAUTION] Bettable Spread MAE 8-10 points is below market average")
        else:
            print("  [OK] Bettable Spread MAE < 8 points is competitive with markets")

        if overall['bettable_direction_accuracy'] < 52.4:
            print("  [WARNING] Direction accuracy below 52.4% = losing after juice")
        elif overall['bettable_direction_accuracy'] < 55:
            print("  [MARGINAL] Direction 52.4-55% = barely profitable")
        else:
            print("  [GOOD] Direction > 55% = potentially profitable edge")

    # Save detailed results
    if args.output:
        save_results_csv(all_results, Path(args.output))
    else:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        save_results_csv(all_results, RESULTS_DIR / "validation_results.csv")

    print("\n" + "=" * 72)
    print(" VALIDATION COMPLETE")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
