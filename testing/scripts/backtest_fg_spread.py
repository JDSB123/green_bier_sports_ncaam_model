#!/usr/bin/env python3
"""Backtest FG Spread Model against historical data.

Uses actual game margins from ESPN + Barttorvik ratings.
This derives calibration values FROM REAL DATA.

This uses FGSpreadModel directly - the same model used in production.
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

sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from app.predictors.fg_spread import FGSpreadModel


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


def load_games(filepath: Path) -> list[dict]:
    """Load game data from CSV."""
    games = []
    with filepath.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Need both home and away scores
            if not row.get("home_score") or not row.get("away_score"):
                continue
            home_score = int(row.get("home_score", 0) or 0)
            away_score = int(row.get("away_score", 0) or 0)
            if home_score == 0 and away_score == 0:
                continue
            games.append({
                "game_id": row["game_id"],
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": home_score,
                "away_score": away_score,
                "margin": home_score - away_score,  # positive = home win
                "neutral": row.get("neutral", "").lower() == "true",
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
    """Run FG Spread backtest using FGSpreadModel."""
    print("=" * 72)
    print(" FG SPREAD MODEL BACKTEST")
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
    for season in range(2019, 2026):
        ratings = load_barttorvik_ratings(season)
        if ratings:
            all_ratings[season] = ratings
            print(f"[INFO] Loaded {len(ratings)} team ratings for {season}")

    # Initialize model
    model = FGSpreadModel()
    print(f"[INFO] Model version: {model.MODEL_VERSION}")
    print(f"[INFO] Current HCA: {model.HCA}")
    print()

    # Run predictions
    predictions = []
    matched_games = 0
    skipped_games = 0
    neutral_games = 0

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

        is_neutral = game.get("neutral", False)
        if is_neutral:
            neutral_games += 1

        pred = model.predict(home_rating, away_rating, is_neutral=is_neutral)

        # Convert model spread to margin prediction
        # Model spread is from home perspective, negative = home favored
        # So predicted margin = -spread
        predicted_margin = -pred.value

        actual_margin = game["margin"]

        predictions.append({
            "game_id": game["game_id"],
            "date": game["date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "actual_margin": actual_margin,
            "predicted_margin": predicted_margin,
            "model_spread": pred.value,
            "error": predicted_margin - actual_margin,
            "abs_error": abs(predicted_margin - actual_margin),
            "is_neutral": is_neutral,
            # Direction accuracy: did we pick the winner?
            "direction_correct": (predicted_margin > 0) == (actual_margin > 0) if actual_margin != 0 else None,
        })
        matched_games += 1

    print(f"[INFO] Matched {matched_games} games, skipped {skipped_games}")
    print(f"[INFO] Neutral site games: {neutral_games}")
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

    # HCA Analysis
    print("=" * 72)
    print(" HOME COURT ADVANTAGE ANALYSIS")
    print("=" * 72)

    # Actual home margin in non-neutral games
    non_neutral = [p for p in predictions if not p["is_neutral"]]
    actual_home_margin = np.mean([p["actual_margin"] for p in non_neutral])
    print(f" Non-neutral games: {len(non_neutral)}")
    print(f" Actual avg home margin: {actual_home_margin:+.2f} points")
    print(f" Current model HCA: {model.HCA}")

    # What HCA should be
    # Our model predicts margin. If we're off by mean_error, HCA should adjust.
    # But HCA specifically applies to non-neutral games
    non_neutral_errors = [p["error"] for p in non_neutral]
    non_neutral_bias = np.mean(non_neutral_errors)
    optimal_hca = model.HCA - non_neutral_bias
    print(f" Non-neutral bias: {non_neutral_bias:+.2f} points")
    print(f" Optimal HCA: {optimal_hca:.2f}")
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

    # Error by margin bucket
    print("=" * 72)
    print(" ERROR BY ACTUAL MARGIN")
    print("=" * 72)
    buckets = [(-999, -20), (-20, -10), (-10, -5), (-5, 0),
               (0, 5), (5, 10), (10, 20), (20, 999)]
    for low, high in buckets:
        bucket_preds = [p for p in predictions if low < p["actual_margin"] <= high]
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

    # Bettable games analysis (market typically has spreads < 20)
    print("=" * 72)
    print(" BETTABLE GAMES (|predicted margin| < 20)")
    print("=" * 72)
    bettable = [p for p in predictions if abs(p["predicted_margin"]) < 20]
    if bettable:
        bettable_mae = np.mean([p["abs_error"] for p in bettable])
        bettable_dir = [p["direction_correct"] for p in bettable if p["direction_correct"] is not None]
        bettable_accuracy = np.mean(bettable_dir) * 100 if bettable_dir else 0
        print(f" Bettable games: {len(bettable)} ({100*len(bettable)/len(predictions):.1f}%)")
        print(f" Bettable MAE: {bettable_mae:.2f} points")
        print(f" Bettable direction: {bettable_accuracy:.1f}%")
    print()

    # Save results
    results_file = HIST_DATA_DIR / "fg_spread_backtest_results.csv"
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
    print(f" Current HCA: {model.HCA}")
    print(f" Optimal HCA: {optimal_hca:.2f}")
    print(f" Adjustment needed: {-non_neutral_bias:+.2f}")
    print()
    print(" Model is using production FGSpreadModel directly.")
    print("=" * 72)


if __name__ == "__main__":
    run_backtest()
