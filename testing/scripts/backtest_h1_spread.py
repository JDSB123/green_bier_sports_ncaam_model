#!/usr/bin/env python3
"""Backtest 1H Spread Model against historical data.

Uses actual 1H margins from ESPN + Barttorvik ratings.
This derives calibration values FROM REAL DATA.

This uses H1SpreadModel directly - the same model used in production.
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
H1_DATA_DIR = ROOT_DIR / "testing" / "data" / "h1_historical"

sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from app.predictors.h1_spread import H1SpreadModel


@dataclass
class TeamRatings:
    """Team ratings from Barttorvik - matches model expectations."""
    adj_o: float
    adj_d: float
    tempo: float
    barthag: float = 0.5
    three_pt_rate: float = 35.0
    rank: int = 150
    net_rating: float = 0.0
    orb: float = 28.0
    drb: float = 72.0
    tor: float = 18.5
    tord: float = 18.5
    ftr: float = 33.0
    ftrd: float = 33.0
    efg: float = 50.0  # Effective FG% - required by H1SpreadModel


def load_h1_games(filepath: Path) -> list[dict]:
    """Load 1H game data."""
    games = []
    with filepath.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip if missing 1H data
            if not row.get("h1_total") or not row.get("home_h1") or not row.get("away_h1"):
                continue
            home_h1 = int(row["home_h1"])
            away_h1 = int(row["away_h1"])
            games.append({
                "game_id": row["game_id"],
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_h1": home_h1,
                "away_h1": away_h1,
                "h1_margin": home_h1 - away_h1,
                "h1_total": int(row["h1_total"]),
                "home_fg": int(row["home_fg"]),
                "away_fg": int(row["away_fg"]),
                "fg_margin": int(row["home_fg"]) - int(row["away_fg"]),
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
            adj_o = float(team_data[4]) if team_data[4] else 100.0
            adj_d = float(team_data[6]) if team_data[6] else 100.0
            # EFG is at index 10 in Barttorvik data
            efg_val = float(team_data[10]) if len(team_data) > 10 and team_data[10] else 50.0
            ratings[team_name] = TeamRatings(
                adj_o=adj_o,
                adj_d=adj_d,
                tempo=float(team_data[44]) if team_data[44] else 68.0,
                barthag=float(team_data[8]) if team_data[8] else 0.5,
                three_pt_rate=float(team_data[22]) if isinstance(team_data[22], (int, float)) else 35.0,
                rank=int(team_data[0]) if team_data[0] else 150,
                net_rating=adj_o - adj_d,
                orb=float(team_data[21]) if len(team_data) > 21 and team_data[21] else 28.0,
                drb=float(team_data[23]) if len(team_data) > 23 and team_data[23] else 72.0,
                tor=float(team_data[17]) if len(team_data) > 17 and team_data[17] else 18.5,
                tord=float(team_data[19]) if len(team_data) > 19 and team_data[19] else 18.5,
                ftr=float(team_data[27]) if len(team_data) > 27 and team_data[27] else 33.0,
                ftrd=float(team_data[29]) if len(team_data) > 29 and team_data[29] else 33.0,
                efg=efg_val,
            )
        except (ValueError, TypeError, IndexError):
            continue

    return ratings


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    name = name.lower().strip()
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
    """Run 1H Spread backtest using H1SpreadModel."""
    print("=" * 72)
    print(" 1H SPREAD MODEL BACKTEST")
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
    for season in range(2019, 2026):
        ratings = load_barttorvik_ratings(season)
        if ratings:
            all_ratings[season] = ratings
            print(f"[INFO] Loaded {len(ratings)} team ratings for {season}")

    # Initialize model
    model = H1SpreadModel()
    print(f"[INFO] Model version: {model.MODEL_VERSION}")
    print(f"[INFO] Current HCA: {model.HCA}")
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

        # Convert model spread to margin prediction
        # Model spread is from home perspective, negative = home favored
        predicted_margin = -pred.value

        actual_h1_margin = game["h1_margin"]
        actual_fg_margin = game["fg_margin"]

        predictions.append({
            "game_id": game["game_id"],
            "date": game["date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "actual_h1_margin": actual_h1_margin,
            "predicted_h1_margin": predicted_margin,
            "model_spread": pred.value,
            "error": predicted_margin - actual_h1_margin,
            "abs_error": abs(predicted_margin - actual_h1_margin),
            "actual_fg_margin": actual_fg_margin,
            "h1_fg_ratio": actual_h1_margin / actual_fg_margin if actual_fg_margin != 0 else 0,
            # Direction accuracy: did we pick the winner?
            "direction_correct": (predicted_margin > 0) == (actual_h1_margin > 0) if actual_h1_margin != 0 else None,
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
    direction_results = [p["direction_correct"] for p in predictions if p["direction_correct"] is not None]

    mean_error = np.mean(errors)
    mae = np.mean(abs_errors)
    std_error = np.std(errors)
    rmse = np.sqrt(np.mean([e**2 for e in errors]))
    direction_accuracy = np.mean(direction_results) * 100 if direction_results else 0

    print("=" * 72)
    print(" RESULTS (Current Model)")
    print("=" * 72)
    print(f" Games analyzed: {len(predictions)}")
    print(f" Mean Error (Bias): {mean_error:+.2f} points")
    print(f" MAE: {mae:.2f} points")
    print(f" RMSE: {rmse:.2f} points")
    print(f" Std Dev of Error: {std_error:.2f} points")
    print(f" Direction Accuracy: {direction_accuracy:.1f}%")
    print()

    # 1H vs FG relationship
    print("=" * 72)
    print(" 1H vs FG MARGIN RELATIONSHIP")
    print("=" * 72)
    h1_fg_ratios = [p["h1_fg_ratio"] for p in predictions if p["actual_fg_margin"] != 0]
    avg_ratio = np.mean(h1_fg_ratios) if h1_fg_ratios else 0
    print(f" Average 1H/FG margin ratio: {avg_ratio:.3f}")
    print(f" (Expected ~0.5 if 1H margin = half of FG margin)")
    print()

    # Actual 1H home advantage
    actual_h1_margins = [p["actual_h1_margin"] for p in predictions]
    avg_h1_margin = np.mean(actual_h1_margins)
    print(f" Actual avg 1H home margin: {avg_h1_margin:+.2f} points")
    print(f" Current model 1H HCA: {model.HCA}")

    # Optimal HCA
    optimal_hca = model.HCA - mean_error
    print(f" Optimal 1H HCA: {optimal_hca:.2f}")
    print()

    # Error distribution
    print("=" * 72)
    print(" ERROR DISTRIBUTION")
    print("=" * 72)
    bins = [(-999, -15), (-15, -10), (-10, -5), (-5, 0),
            (0, 5), (5, 10), (10, 15), (15, 999)]
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

    # Error by actual margin bucket
    print("=" * 72)
    print(" ERROR BY ACTUAL 1H MARGIN")
    print("=" * 72)
    buckets = [(-999, -10), (-10, -5), (-5, 0), (0, 5), (5, 10), (10, 999)]
    for low, high in buckets:
        bucket_preds = [p for p in predictions if low < p["actual_h1_margin"] <= high]
        if bucket_preds:
            bucket_mae = np.mean([p["abs_error"] for p in bucket_preds])
            bucket_bias = np.mean([p["error"] for p in bucket_preds])
            if low == -999:
                label = f"<{high:+d}"
            elif high == 999:
                label = f">{low:+d}"
            else:
                label = f"{low:+d} to {high:+d}"
            print(f"  {label:>12}: n={len(bucket_preds):4d}, MAE={bucket_mae:.1f}, Bias={bucket_bias:+.1f}")
    print()

    # Save results
    results_file = H1_DATA_DIR / "h1_spread_backtest_results.csv"
    with results_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
        writer.writeheader()
        writer.writerows(predictions)
    print(f"[INFO] Saved detailed results to {results_file}")

    # Summary
    print()
    print("=" * 72)
    print(" SUMMARY")
    print("=" * 72)
    print(f" Current 1H HCA: {model.HCA}")
    print(f" Optimal 1H HCA: {optimal_hca:.2f}")
    print(f" Adjustment needed: {-mean_error:+.2f}")
    print()
    print(" Model is using production H1SpreadModel directly.")
    print("=" * 72)


if __name__ == "__main__":
    run_backtest()
