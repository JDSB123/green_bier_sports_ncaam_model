#!/usr/bin/env python3
"""
Model Calibration Script

Analyzes validation results to find optimal model parameters.
Uses grid search and regression to minimize MAE and eliminate biases.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy import optimize

from testing.azure_data_reader import get_azure_reader, read_barttorvik_ratings

LEAGUE_AVG_EFFICIENCY = 100.0


def load_all_data():
    """Load all seasons of game data and ratings from Azure."""
    all_games = []
    all_ratings = {}
    reader = get_azure_reader()

    def parse_barttorvik_payload(payload):
        ratings = {}
        if isinstance(payload, list):
            for team_data in payload:
                if isinstance(team_data, list) and len(team_data) > 10:
                    name = str(team_data[1]).lower()
                    ratings[name] = {
                        'adj_o': float(team_data[4]),
                        'adj_d': float(team_data[6]),
                        'adj_t': float(team_data[44]) if len(team_data) > 44 else 68.0,
                    }
        elif isinstance(payload, dict):
            for name, row in payload.items():
                if not isinstance(row, dict):
                    continue
                ratings[str(name).lower()] = {
                    'adj_o': float(row.get('adj_o', 100)),
                    'adj_d': float(row.get('adj_d', 100)),
                    'adj_t': float(row.get('tempo', 68)),
                }
        return ratings

    for season in range(2020, 2025):
        try:
            df = reader.read_canonical_scores(season)
            df['season'] = season
            all_games.append(df)
        except Exception as e:
            print(f"[WARN] Missing Azure games for season {season}: {e}")

        try:
            payload = read_barttorvik_ratings(season)
            ratings = parse_barttorvik_payload(payload)
            if ratings:
                all_ratings[season] = ratings
        except Exception as e:
            print(f"[WARN] Missing Azure ratings for season {season}: {e}")

    games_df = pd.concat(all_games, ignore_index=True) if all_games else pd.DataFrame()
    return games_df, all_ratings


def normalize_name(name: str) -> str:
    """Normalize team name for matching."""
    name = name.lower().strip()

    replacements = {
        "uconn": "connecticut", "pitt": "pittsburgh",
        "ole miss": "mississippi", "lsu": "louisiana state",
        "ucf": "central florida", "usc": "southern california",
        "smu": "southern methodist", "tcu": "texas christian",
        "byu": "brigham young",
    }

    for abbr, full in replacements.items():
        if name == abbr or name.startswith(abbr + " "):
            return full

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
        " lumberjacks", " golden", " screaming eagles", " dukes",
    ]

    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    return name.strip()


def find_rating(team_name: str, ratings: dict) -> dict | None:
    """Find team rating with fuzzy matching."""
    normalized = normalize_name(team_name)

    if normalized in ratings:
        return ratings[normalized]

    for key, rating in ratings.items():
        if normalized in key or key in normalized:
            return rating

    return None


def predict_with_params(
    home_adj_o: float, home_adj_d: float, home_adj_t: float,
    away_adj_o: float, away_adj_d: float, away_adj_t: float,
    neutral: bool, hca_spread: float, total_adj: float
) -> tuple[float, float]:
    """Generate prediction with given parameters."""
    tempo = (home_adj_t + away_adj_t) / 2

    home_eff = home_adj_o + away_adj_d - LEAGUE_AVG_EFFICIENCY
    away_eff = away_adj_o + home_adj_d - LEAGUE_AVG_EFFICIENCY

    home_score = home_eff * tempo / 100
    away_score = away_eff * tempo / 100

    if not neutral:
        home_score += hca_spread / 2
        away_score -= hca_spread / 2

    spread = home_score - away_score
    total = home_score + away_score + total_adj

    return spread, total


def evaluate_params(params, games_with_ratings):
    """Evaluate MAE for given parameters."""
    hca_spread, total_adj = params

    spread_errors = []
    total_errors = []

    for _, row in games_with_ratings.iterrows():
        pred_spread, pred_total = predict_with_params(
            row['home_adj_o'], row['home_adj_d'], row['home_adj_t'],
            row['away_adj_o'], row['away_adj_d'], row['away_adj_t'],
            row.get('neutral', False), hca_spread, total_adj
        )

        actual_spread = row['home_score'] - row['away_score']
        actual_total = row['home_score'] + row['away_score']

        spread_errors.append(abs(pred_spread - actual_spread))
        total_errors.append(abs(pred_total - actual_total))

    # Combined objective: weighted MAE
    spread_mae = np.mean(spread_errors)
    total_mae = np.mean(total_errors)

    return spread_mae + 0.5 * total_mae  # Weight spread more


def main():
    print("=" * 72)
    print(" NCAAM Model Calibration")
    print("=" * 72)

    games_df, all_ratings = load_all_data()
    print(f"\nLoaded {len(games_df)} games across {len(all_ratings)} seasons")

    # Build dataset with ratings
    rows = []
    for _, game in games_df.iterrows():
        season = game['season']
        if season not in all_ratings:
            continue

        ratings = all_ratings[season]
        home_r = find_rating(game['home_team'], ratings)
        away_r = find_rating(game['away_team'], ratings)

        if not home_r or not away_r:
            continue

        rows.append({
            'home_team': game['home_team'],
            'away_team': game['away_team'],
            'home_score': game['home_score'],
            'away_score': game['away_score'],
            'neutral': game.get('neutral', False),
            'home_adj_o': home_r['adj_o'],
            'home_adj_d': home_r['adj_d'],
            'home_adj_t': home_r['adj_t'],
            'away_adj_o': away_r['adj_o'],
            'away_adj_d': away_r['adj_d'],
            'away_adj_t': away_r['adj_t'],
            'season': season,
        })

    df = pd.DataFrame(rows)
    print(f"Matched {len(df)} games with ratings")

    # Calculate actual spreads/totals
    df['actual_spread'] = df['home_score'] - df['away_score']
    df['actual_total'] = df['home_score'] + df['away_score']

    # Current model baseline (HCA=3.2, total_adj=0)
    print("\n" + "=" * 72)
    print(" CURRENT MODEL (HCA=3.2, Total Adj=0)")
    print("=" * 72)

    current_mae = evaluate_params([3.2, 0], df)
    print(f"Combined MAE: {current_mae:.2f}")

    # Grid search for optimal parameters
    print("\n" + "=" * 72)
    print(" GRID SEARCH OPTIMIZATION")
    print("=" * 72)

    best_mae = float('inf')
    best_params = (3.2, 0)

    print("\nSearching HCA from 2.0 to 7.0, Total Adj from -10 to +5...")

    for hca in np.arange(2.0, 7.5, 0.5):
        for total_adj in np.arange(-10, 6, 1):
            mae = evaluate_params([hca, total_adj], df)
            if mae < best_mae:
                best_mae = mae
                best_params = (hca, total_adj)

    print(f"\nBest Grid Search: HCA={best_params[0]:.1f}, Total Adj={best_params[1]:.1f}")
    print(f"Combined MAE: {best_mae:.2f}")

    # Fine-tune with scipy optimizer
    print("\n" + "=" * 72)
    print(" FINE-TUNING WITH SCIPY")
    print("=" * 72)

    result = optimize.minimize(
        evaluate_params,
        best_params,
        args=(df,),
        method='Nelder-Mead',
        options={'xatol': 0.01, 'fatol': 0.001}
    )

    optimal_hca, optimal_total_adj = result.x
    print(f"\nOptimal HCA: {optimal_hca:.2f}")
    print(f"Optimal Total Adj: {optimal_total_adj:.2f}")
    print(f"Optimized Combined MAE: {result.fun:.2f}")

    # Evaluate optimal params in detail
    print("\n" + "=" * 72)
    print(" DETAILED EVALUATION OF OPTIMAL PARAMS")
    print("=" * 72)

    spread_errors = []
    total_errors = []
    spread_raw_errors = []
    total_raw_errors = []

    for _, row in df.iterrows():
        pred_spread, pred_total = predict_with_params(
            row['home_adj_o'], row['home_adj_d'], row['home_adj_t'],
            row['away_adj_o'], row['away_adj_d'], row['away_adj_t'],
            row.get('neutral', False), optimal_hca, optimal_total_adj
        )

        spread_err = pred_spread - row['actual_spread']
        total_err = pred_total - row['actual_total']

        spread_errors.append(abs(spread_err))
        total_errors.append(abs(total_err))
        spread_raw_errors.append(spread_err)
        total_raw_errors.append(total_err)

    print(f"\nSpread MAE:  {np.mean(spread_errors):.2f} points")
    print(f"Spread RMSE: {np.sqrt(np.mean([e**2 for e in spread_errors])):.2f} points")
    print(f"Spread Bias: {np.mean(spread_raw_errors):+.2f}")
    print(f"\nTotal MAE:   {np.mean(total_errors):.2f} points")
    print(f"Total RMSE:  {np.sqrt(np.mean([e**2 for e in total_errors])):.2f} points")
    print(f"Total Bias:  {np.mean(total_raw_errors):+.2f}")

    # Filter analysis - remove blowout matchups
    print("\n" + "=" * 72)
    print(" ANALYSIS: FILTERING NON-BETTABLE GAMES")
    print("=" * 72)

    # Calculate expected margin for each game
    df['expected_margin'] = df.apply(
        lambda r: predict_with_params(
            r['home_adj_o'], r['home_adj_d'], r['home_adj_t'],
            r['away_adj_o'], r['away_adj_d'], r['away_adj_t'],
            r.get('neutral', False), optimal_hca, optimal_total_adj
        )[0], axis=1
    )

    # Filter to "bettable" games (expected margin < 20)
    bettable = df[abs(df['expected_margin']) < 20].copy()
    print(f"\nBettable games (|margin| < 20): {len(bettable)} / {len(df)} ({100*len(bettable)/len(df):.1f}%)")

    bettable_errors = []
    for _, row in bettable.iterrows():
        pred_spread, _ = predict_with_params(
            row['home_adj_o'], row['home_adj_d'], row['home_adj_t'],
            row['away_adj_o'], row['away_adj_d'], row['away_adj_t'],
            row.get('neutral', False), optimal_hca, optimal_total_adj
        )
        bettable_errors.append(abs(pred_spread - row['actual_spread']))

    print(f"Bettable Spread MAE: {np.mean(bettable_errors):.2f} points")

    # Tighter filter
    tight = df[abs(df['expected_margin']) < 15].copy()
    print(f"\nTight games (|margin| < 15): {len(tight)} / {len(df)} ({100*len(tight)/len(df):.1f}%)")

    tight_errors = []
    for _, row in tight.iterrows():
        pred_spread, _ = predict_with_params(
            row['home_adj_o'], row['home_adj_d'], row['home_adj_t'],
            row['away_adj_o'], row['away_adj_d'], row['away_adj_t'],
            row.get('neutral', False), optimal_hca, optimal_total_adj
        )
        tight_errors.append(abs(pred_spread - row['actual_spread']))

    print(f"Tight Spread MAE: {np.mean(tight_errors):.2f} points")

    # Summary
    print("\n" + "=" * 72)
    print(" RECOMMENDED PARAMETER CHANGES")
    print("=" * 72)
    print(f"""
    CURRENT VALUES:
        HOME_COURT_ADVANTAGE_SPREAD = 3.2
        HOME_COURT_ADVANTAGE_TOTAL = 0.0

    RECOMMENDED VALUES:
        HOME_COURT_ADVANTAGE_SPREAD = {optimal_hca:.1f}
        TOTAL_ADJUSTMENT = {optimal_total_adj:.1f}

    ADDITIONAL RECOMMENDATIONS:
        1. Filter games with |expected_margin| > 20 for betting
        2. Consider using prior season ratings for first month
        3. The fundamental MAE limit appears to be ~9.5 points
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
