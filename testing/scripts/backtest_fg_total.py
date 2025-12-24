#!/usr/bin/env python3
"""Backtest FG Total Model against historical data.

Uses actual game totals from ESPN + Barttorvik ratings.
Compares our predictions to actual results AND to market lines.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
HIST_DATA_DIR = ROOT_DIR / "testing" / "data" / "historical"
ODDS_DATA_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"

sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from app.predictors.fg_total import FGTotalModel


@dataclass
class TeamRatings:
    """Team ratings from Barttorvik."""
    adj_o: float
    adj_d: float
    tempo: float
    barthag: float = 0.5
    three_pt_rate: float = 35.0


def load_games(filepath: Path) -> list[dict]:
    """Load game data from CSV."""
    games = []
    with filepath.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("total"):
                continue
            games.append({
                "game_id": row["game_id"],
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": int(row.get("home_score", 0) or 0),
                "away_score": int(row.get("away_score", 0) or 0),
                "total": int(row.get("total", 0) or 0),
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

        team_name = team_data[1]
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
    name = name.lower().strip()
    # Remove common suffixes
    suffixes = [" wildcats", " tigers", " bears", " bulldogs", " eagles",
                " hawks", " cardinals", " hurricanes", " gators", " terrapins",
                " crusaders", " hornets", " jayhawks", " wolverines", " buckeyes"]
    for suffix in suffixes:
        name = name.replace(suffix, "")
    return name.strip()


def find_team_rating(team_name: str, ratings: dict[str, TeamRatings]) -> TeamRatings | None:
    """Find team rating with fuzzy matching."""
    if team_name in ratings:
        return ratings[team_name]

    norm_name = normalize_team_name(team_name)
    for rating_name, rating in ratings.items():
        if not isinstance(rating_name, str):
            continue
        if normalize_team_name(rating_name) == norm_name:
            return rating
        rating_norm = normalize_team_name(rating_name)
        if norm_name in rating_norm or rating_norm in norm_name:
            return rating

    return None


def get_season_from_date(date_str: str) -> int:
    """Get season year from date string."""
    parts = date_str.split("-")
    year = int(parts[0])
    month = int(parts[1])
    if month >= 11:
        return year + 1
    return year


def run_backtest():
    """Run FG Total backtest."""
    print("=" * 72)
    print(" FG TOTAL MODEL BACKTEST")
    print("=" * 72)

    # Load game data
    games_file = HIST_DATA_DIR / "games_all.csv"
    if not games_file.exists():
        print(f"[ERROR] Games file not found: {games_file}")
        return

    games = load_games(games_file)
    print(f"[INFO] Loaded {len(games)} games")

    # Load all Barttorvik ratings
    all_ratings = {}
    for season in range(2020, 2026):
        ratings = load_barttorvik_ratings(season)
        if ratings:
            all_ratings[season] = ratings
            print(f"[INFO] Loaded {len(ratings)} team ratings for {season}")

    # Initialize model
    model = FGTotalModel()
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

        pred = model.predict(home_rating, away_rating)

        predictions.append({
            "game_id": game["game_id"],
            "date": game["date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "actual_total": game["total"],
            "predicted_total": pred.value,
            "error": pred.value - game["total"],
            "abs_error": abs(pred.value - game["total"]),
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
    actuals = [p["actual_total"] for p in predictions]

    mean_error = np.mean(errors)
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

    # Optimal calibration
    optimal_calibration = model.CALIBRATION - mean_error
    print(f" Current Calibration: {model.CALIBRATION}")
    print(f" Optimal Calibration: {optimal_calibration:.2f}")
    print(f" Adjustment Needed: {-mean_error:+.2f}")
    print()

    # Actual total stats
    avg_total = np.mean(actuals)
    std_total = np.std(actuals)
    print(f" Actual Total - Mean: {avg_total:.1f}, Std: {std_total:.1f}")
    print()

    # Prediction variance analysis
    pred_values = [p["predicted_total"] for p in predictions]
    pred_std = np.std(pred_values)
    print(f" Predicted Std Dev: {pred_std:.1f}")
    print(f" Actual Std Dev: {std_total:.1f}")
    print(f" Ratio: {pred_std/std_total:.3f} (should be ~1.0)")
    print()

    # Error distribution
    print("=" * 72)
    print(" ERROR DISTRIBUTION")
    print("=" * 72)
    bins = [(-999, -20), (-20, -15), (-15, -10), (-10, -5), (-5, 0),
            (0, 5), (5, 10), (10, 15), (15, 20), (20, 999)]
    for low, high in bins:
        count = sum(1 for e in errors if low < e <= high)
        pct = count / len(errors) * 100
        if low == -999:
            label = f"<{high:+d}"
        elif high == 999:
            label = f">{low:+d}"
        else:
            label = f"{low:+d} to {high:+d}"
        print(f"  {label:>12}: {count:4d} ({pct:5.1f}%)")
    print()

    # Error by actual total (key analysis)
    print("=" * 72)
    print(" ERROR BY ACTUAL TOTAL (Regression to Mean Analysis)")
    print("=" * 72)
    buckets = [(0, 120), (120, 130), (130, 140), (140, 150), (150, 160),
               (160, 170), (170, 180), (180, 999)]
    for low, high in buckets:
        bucket_preds = [p for p in predictions if low <= p["actual_total"] < high]
        if bucket_preds:
            bucket_mae = np.mean([p["abs_error"] for p in bucket_preds])
            bucket_bias = np.mean([p["error"] for p in bucket_preds])
            label = f"{low}-{high}" if high < 200 else f"{low}+"
            print(f"  {label:>8}: n={len(bucket_preds):4d}, MAE={bucket_mae:.1f}, Bias={bucket_bias:+.1f}")
    print()

    # Market comparison (if we have odds data)
    print("=" * 72)
    print(" MARKET COMPARISON")
    print("=" * 72)

    # Market typically has MAE ~10-11 pts
    market_mae_estimate = 10.5
    print(f" Our MAE: {mae:.1f} points")
    print(f" Market MAE (estimate): {market_mae_estimate:.1f} points")
    print(f" Gap: {mae - market_mae_estimate:.1f} points worse than market")
    print()

    # What would need to change
    print(" To match market accuracy, we need to:")
    print(f"   - Reduce MAE by {mae - market_mae_estimate:.1f} points")
    print(f"   - Better capture variance (our std {pred_std:.1f} vs actual {std_total:.1f})")
    print()

    # Save results
    results_file = HIST_DATA_DIR / "fg_backtest_results.csv"
    with results_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
        writer.writeheader()
        writer.writerows(predictions)
    print(f"[INFO] Saved detailed results to {results_file}")

    # Recommendations
    print()
    print("=" * 72)
    print(" ROOT CAUSE ANALYSIS")
    print("=" * 72)

    # The fundamental problem
    low_games = [p for p in predictions if p["actual_total"] < 130]
    high_games = [p for p in predictions if p["actual_total"] > 160]

    if low_games:
        low_bias = np.mean([p["error"] for p in low_games])
        print(f" Low-scoring games (<130): n={len(low_games)}, Bias={low_bias:+.1f}")
    if high_games:
        high_bias = np.mean([p["error"] for p in high_games])
        print(f" High-scoring games (>160): n={len(high_games)}, Bias={high_bias:+.1f}")

    print()
    print(" The REGRESSION TO MEAN problem:")
    print(f"   - We predict std dev of {pred_std:.1f}, but actual is {std_total:.1f}")
    print(f"   - We're only capturing {pred_std/std_total*100:.0f}% of actual variance")
    print("   - This causes systematic errors on extreme games")
    print()
    print(" This is a FUNDAMENTAL LIMITATION of efficiency-based models.")
    print(" The market uses additional signals we don't have:")
    print("   - Injury reports, lineup changes")
    print("   - Recent performance trends")
    print("   - Betting market signals")
    print("   - Weather/travel factors")
    print("=" * 72)


if __name__ == "__main__":
    run_backtest()
