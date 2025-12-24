#!/usr/bin/env python3
"""Backtest 1H Total Model against historical data.

Uses same methodology as FG Total backtest:
1. Load historical 1H scores (from ESPN)
2. Load Barttorvik team ratings for each season
3. Run 1H Total model predictions
4. Calculate MAE, bias, and optimal calibration
5. Analyze error patterns

This will give us empirically validated calibration for 1H Total.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
H1_DATA_DIR = ROOT_DIR / "testing" / "data" / "h1_historical"
HIST_DATA_DIR = ROOT_DIR / "testing" / "data" / "historical"

# Add prediction service to path
sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from app.predictors.h1_total import H1TotalModel


@dataclass
class TeamRatings:
    """Team ratings from Barttorvik."""
    adj_o: float
    adj_d: float
    tempo: float
    barthag: float = 0.5
    three_pt_rate: float = 35.0


def load_h1_games(filepath: Path) -> list[dict]:
    """Load 1H game data."""
    games = []
    with filepath.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip if missing 1H data
            if not row.get("h1_total") or not row.get("fg_total"):
                continue
            games.append({
                "game_id": row["game_id"],
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_h1": int(row["home_h1"]),
                "away_h1": int(row["away_h1"]),
                "h1_total": int(row["h1_total"]),
                "home_fg": int(row["home_fg"]),
                "away_fg": int(row["away_fg"]),
                "fg_total": int(row["fg_total"]),
            })
    return games


def load_barttorvik_ratings(season: int) -> dict[str, TeamRatings]:
    """Load Barttorvik ratings for a season."""
    filepath = HIST_DATA_DIR / f"barttorvik_{season}.json"
    if not filepath.exists():
        return {}

    with filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)

    ratings = {}
    for team_data in data:
        if not isinstance(team_data, list) or len(team_data) < 45:
            continue

        # Barttorvik format: [rank, team_name, conf, record, adj_o, ..., tempo at 44]
        team_name = team_data[1]  # Team name is at index 1, not 0
        if not isinstance(team_name, str):
            continue

        try:
            ratings[team_name] = TeamRatings(
                adj_o=float(team_data[4]) if team_data[4] else 100.0,
                adj_d=float(team_data[6]) if team_data[6] else 100.0,
                tempo=float(team_data[44]) if team_data[44] else 68.0,
                barthag=float(team_data[8]) if team_data[8] else 0.5,
                three_pt_rate=float(team_data[22]) if isinstance(team_data[22], (int, float)) else 35.0,
            )
        except (ValueError, TypeError, IndexError):
            continue

    return ratings


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    # Remove common suffixes
    name = name.replace(" Wildcats", "").replace(" Tigers", "").replace(" Bears", "")
    name = name.replace(" Bulldogs", "").replace(" Eagles", "").replace(" Hawks", "")
    name = name.replace(" Cardinals", "").replace(" Hurricanes", "").replace(" Gators", "")
    name = name.replace(" Terrapins", "").replace(" Crusaders", "").replace(" Hornets", "")
    return name.strip().lower()


def find_team_rating(team_name: str, ratings: dict[str, TeamRatings]) -> TeamRatings | None:
    """Find team rating with fuzzy matching."""
    # Direct match
    if team_name in ratings:
        return ratings[team_name]

    # Normalize and try
    norm_name = normalize_team_name(team_name)
    for rating_name, rating in ratings.items():
        # Skip non-string keys
        if not isinstance(rating_name, str):
            continue
        if normalize_team_name(rating_name) == norm_name:
            return rating
        # Partial match
        rating_norm = normalize_team_name(rating_name)
        if norm_name in rating_norm or rating_norm in norm_name:
            return rating

    return None


def get_season_from_date(date_str: str) -> int:
    """Get season year from date string (YYYY-MM-DD)."""
    parts = date_str.split("-")
    year = int(parts[0])
    month = int(parts[1])
    # Nov-Dec is next year's season
    if month >= 11:
        return year + 1
    return year


def run_backtest():
    """Run 1H Total backtest."""
    print("=" * 72)
    print(" 1H TOTAL MODEL BACKTEST")
    print("=" * 72)

    # Load 1H game data
    h1_file = H1_DATA_DIR / "h1_games_all.csv"
    if not h1_file.exists():
        print(f"[ERROR] 1H data not found: {h1_file}")
        print("        Run fetch_h1_data.py first!")
        return

    games = load_h1_games(h1_file)
    print(f"[INFO] Loaded {len(games)} games with 1H data")

    # Load all Barttorvik ratings
    all_ratings = {}
    for season in range(2020, 2026):
        ratings = load_barttorvik_ratings(season)
        if ratings:
            all_ratings[season] = ratings
            print(f"[INFO] Loaded {len(ratings)} team ratings for {season}")

    # Initialize model (with current calibration)
    model = H1TotalModel()
    print(f"[INFO] Model version: {model.MODEL_VERSION}")
    print(f"[INFO] Current calibration: {model.CALIBRATION}")
    print()

    # Run predictions
    predictions = []
    matched_games = 0
    skipped_games = 0

    for game in games:
        season = get_season_from_date(game["date"])
        if season not in all_ratings:
            skipped_games += 1
            continue

        ratings = all_ratings[season]
        home_rating = find_team_rating(game["home_team"], ratings)
        away_rating = find_team_rating(game["away_team"], ratings)

        if not home_rating or not away_rating:
            skipped_games += 1
            continue

        # Run prediction
        pred = model.predict(home_rating, away_rating)

        predictions.append({
            "game_id": game["game_id"],
            "date": game["date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "actual_h1": game["h1_total"],
            "predicted_h1": pred.value,
            "error": pred.value - game["h1_total"],
            "abs_error": abs(pred.value - game["h1_total"]),
            "actual_fg": game["fg_total"],
            "h1_fg_ratio": game["h1_total"] / game["fg_total"] if game["fg_total"] > 0 else 0,
        })
        matched_games += 1

    print(f"[INFO] Matched {matched_games} games, skipped {skipped_games}")
    print()

    if not predictions:
        print("[ERROR] No predictions generated!")
        return

    # Calculate metrics
    errors = [p["error"] for p in predictions]
    abs_errors = [p["abs_error"] for p in predictions]

    mean_error = np.mean(errors)  # Bias
    mae = np.mean(abs_errors)
    std_error = np.std(errors)
    rmse = np.sqrt(np.mean([e**2 for e in errors]))

    print("=" * 72)
    print(" RESULTS (Current Model)")
    print("=" * 72)
    print(f" Games analyzed: {len(predictions)}")
    print(f" Mean Error (Bias): {mean_error:+.2f} points")
    print(f" MAE: {mae:.2f} points")
    print(f" RMSE: {rmse:.2f} points")
    print(f" Std Dev of Error: {std_error:.2f} points")
    print()

    # Calculate optimal calibration
    # If mean_error is positive, we over-predict -> need more negative calibration
    optimal_calibration = model.CALIBRATION - mean_error
    print(f" Current Calibration: {model.CALIBRATION}")
    print(f" Optimal Calibration: {optimal_calibration:.2f}")
    print(f" Adjustment Needed: {-mean_error:+.2f}")
    print()

    # Analyze by H1/FG ratio
    ratios = [p["h1_fg_ratio"] for p in predictions if p["h1_fg_ratio"] > 0]
    avg_ratio = np.mean(ratios)
    std_ratio = np.std(ratios)
    print(f" Actual 1H/FG Ratio: {avg_ratio:.3f} (std: {std_ratio:.3f})")
    print()

    # Error distribution
    print("=" * 72)
    print(" ERROR DISTRIBUTION")
    print("=" * 72)
    bins = [(-999, -15), (-15, -10), (-10, -5), (-5, 0), (0, 5), (5, 10), (10, 15), (15, 999)]
    for low, high in bins:
        count = sum(1 for e in errors if low < e <= high)
        pct = count / len(errors) * 100
        label = f"{low:+d} to {high:+d}" if high < 100 else f">{low:+d}"
        if low == -999:
            label = f"<{high:+d}"
        print(f"  {label:>12}: {count:4d} ({pct:5.1f}%)")
    print()

    # Analyze by actual total
    print("=" * 72)
    print(" ERROR BY ACTUAL 1H TOTAL")
    print("=" * 72)
    buckets = [(0, 55), (55, 65), (65, 75), (75, 85), (85, 999)]
    for low, high in buckets:
        bucket_preds = [p for p in predictions if low <= p["actual_h1"] < high]
        if bucket_preds:
            bucket_mae = np.mean([p["abs_error"] for p in bucket_preds])
            bucket_bias = np.mean([p["error"] for p in bucket_preds])
            label = f"{low}-{high}" if high < 100 else f"{low}+"
            print(f"  {label:>8}: n={len(bucket_preds):4d}, MAE={bucket_mae:.1f}, Bias={bucket_bias:+.1f}")
    print()

    # Analyze by tempo
    print("=" * 72)
    print(" 1H MODEL PARAMETER ANALYSIS")
    print("=" * 72)

    # Check if our possessions estimate is reasonable
    # Actual 1H total / expected points per possession can estimate actual possessions
    # League avg efficiency ~107 pts per 100 poss, so ~1.07 pts per poss combined
    # If actual 1H avg is X, then estimated possessions = X / 1.07 / 2 * 100
    avg_h1 = np.mean([p["actual_h1"] for p in predictions])
    estimated_h1_poss = avg_h1 / 2.14  # ~2.14 pts per poss for both teams combined
    print(f" Average actual 1H total: {avg_h1:.1f}")
    print(f" Estimated 1H possessions: {estimated_h1_poss:.1f}")
    print(f" Model base possessions: {model.config.h1_possessions_base}")
    print()

    # Save detailed results
    results_file = H1_DATA_DIR / "h1_backtest_results.csv"
    with results_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
        writer.writeheader()
        writer.writerows(predictions)
    print(f"[INFO] Saved detailed results to {results_file}")

    # Summary recommendations
    print()
    print("=" * 72)
    print(" RECOMMENDATIONS")
    print("=" * 72)
    print(f" 1. Update CALIBRATION to: {optimal_calibration:.1f}")
    print(f" 2. Current MAE: {mae:.1f} (target: <7.0 for 1H)")

    # Check if we under/over predict by actual total
    low_games = [p for p in predictions if p["actual_h1"] < 60]
    high_games = [p for p in predictions if p["actual_h1"] > 80]
    if low_games:
        low_bias = np.mean([p["error"] for p in low_games])
        print(f" 3. Low-scoring games (<60): Bias={low_bias:+.1f}")
    if high_games:
        high_bias = np.mean([p["error"] for p in high_games])
        print(f" 4. High-scoring games (>80): Bias={high_bias:+.1f}")

    print("=" * 72)


if __name__ == "__main__":
    run_backtest()
