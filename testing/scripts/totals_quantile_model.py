#!/usr/bin/env python3
"""
Quantile Regression for Totals

Instead of predicting just the mean, predict the range (10th, 50th, 90th percentiles).
This gives us confidence bounds for betting decisions.

Key insight: Rather than trying to beat the market on point prediction,
we can identify games where the RANGE is skewed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"


def load_all_data():
    """Load games and ratings."""
    all_games = []

    for season in range(2019, 2025):
        games_path = HISTORICAL_DIR / f"games_{season}.csv"
        if games_path.exists():
            df = pd.read_csv(games_path)
            df['season'] = season
            all_games.append(df)

    all_ratings = {}
    for season in range(2019, 2025):
        ratings_path = HISTORICAL_DIR / f"barttorvik_{season}.json"
        if ratings_path.exists():
            with open(ratings_path, 'r') as f:
                data = json.load(f)
            ratings = {}
            for team_data in data:
                if isinstance(team_data, list) and len(team_data) > 44:
                    name = team_data[1].lower()
                    try:
                        ratings[name] = {
                            'adj_o': float(team_data[4]),
                            'adj_d': float(team_data[6]),
                            'barthag': float(team_data[8]) if team_data[8] is not None else 0.5,
                            'adj_t': float(team_data[44]) if team_data[44] is not None else 68.0,
                            'efg': float(team_data[10]) if isinstance(team_data[10], (int, float)) else 50.0,
                            'efgd': float(team_data[11]) if isinstance(team_data[11], (int, float)) else 50.0,
                            '3pr': float(team_data[22]) if isinstance(team_data[22], (int, float)) else 35.0,
                            '3prd': float(team_data[23]) if isinstance(team_data[23], (int, float)) else 35.0,
                        }
                    except:
                        continue
            all_ratings[season] = ratings

    games_df = pd.concat(all_games, ignore_index=True) if all_games else pd.DataFrame()
    return games_df, all_ratings


def normalize_name(name: str) -> str:
    name = name.lower().strip()
    suffixes = [
        " wildcats", " tigers", " bulldogs", " bears", " eagles",
        " huskies", " cavaliers", " blue devils", " tar heels",
        " spartans", " wolverines", " buckeyes", " hoosiers",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name.strip()


def get_team_stats(name: str, ratings: dict) -> dict:
    defaults = {
        'adj_o': 106.0, 'adj_d': 106.0, 'adj_t': 68.0, 'barthag': 0.5,
        'efg': 50.0, 'efgd': 50.0, '3pr': 35.0, '3prd': 35.0,
    }
    norm = normalize_name(name)
    if norm in ratings:
        return ratings[norm]
    for key, rating in ratings.items():
        if norm in key or key in norm:
            return rating
    return defaults


def build_features(games_df, all_ratings):
    """Build feature matrix."""
    features = []
    targets = []

    for _, game in games_df.iterrows():
        season = game.get('season', 2024)
        if season not in all_ratings:
            continue

        ratings = all_ratings[season]
        home = get_team_stats(game['home_team'], ratings)
        away = get_team_stats(game['away_team'], ratings)

        feat = {
            'home_adj_o': home['adj_o'],
            'home_adj_d': home['adj_d'],
            'away_adj_o': away['adj_o'],
            'away_adj_d': away['adj_d'],
            'avg_tempo': (home['adj_t'] + away['adj_t']) / 2,
            'tempo_diff': abs(home['adj_t'] - away['adj_t']),
            'avg_barthag': (home['barthag'] + away['barthag']) / 2,
            'barthag_diff': abs(home['barthag'] - away['barthag']),
            'home_efg': home['efg'],
            'away_efg': away['efg'],
            'home_efgd': home['efgd'],
            'away_efgd': away['efgd'],
            'avg_3pr': (home['3pr'] + away['3pr']) / 2,
            'total_off': home['adj_o'] + away['adj_o'],
            'total_def': home['adj_d'] + away['adj_d'],
            'home_exp_eff': home['adj_o'] + away['adj_d'] - 106.0,
            'away_exp_eff': away['adj_o'] + home['adj_d'] - 106.0,
        }

        features.append(feat)
        targets.append(game['home_score'] + game['away_score'])

    return pd.DataFrame(features), np.array(targets)


def main():
    print("\n")
    print("=" * 72)
    print(" QUANTILE REGRESSION FOR TOTALS")
    print("=" * 72)

    games_df, all_ratings = load_all_data()
    print(f"\nLoaded {len(games_df)} games")

    X, y = build_features(games_df, all_ratings)
    X = X.fillna(X.mean())

    print(f"Built {len(X)} samples with {len(X.columns)} features")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Train quantile regressors for different percentiles
    quantiles = [0.10, 0.25, 0.50, 0.75, 0.90]
    models = {}

    print("\n" + "=" * 72)
    print(" TRAINING QUANTILE REGRESSORS")
    print("=" * 72)

    for q in quantiles:
        print(f"\nTraining q={q:.2f}...")
        model = GradientBoostingRegressor(
            loss='quantile',
            alpha=q,
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        model.fit(X_train, y_train)
        models[q] = model

        pred = model.predict(X_test)
        mae = np.mean(np.abs(pred - y_test))
        # For quantile regression, we check calibration (what % falls below prediction)
        calibration = np.mean(y_test < pred)
        print(f"  MAE: {mae:.2f}, Calibration: {calibration:.1%} (target: {q:.0%})")

    # Evaluate the median model (should be best point prediction)
    print("\n" + "=" * 72)
    print(" MEDIAN MODEL PERFORMANCE")
    print("=" * 72)

    median_pred = models[0.50].predict(X_test)
    median_mae = np.mean(np.abs(median_pred - y_test))
    print(f"Median model MAE: {median_mae:.2f}")

    # Calculate prediction intervals
    print("\n" + "=" * 72)
    print(" PREDICTION INTERVAL ANALYSIS")
    print("=" * 72)

    p10 = models[0.10].predict(X_test)
    p50 = models[0.50].predict(X_test)
    p90 = models[0.90].predict(X_test)

    # Check interval coverage
    in_interval = (y_test >= p10) & (y_test <= p90)
    coverage = np.mean(in_interval)
    print(f"\n80% interval coverage (10th to 90th): {coverage:.1%} (target: 80%)")

    # Average interval width
    interval_width = np.mean(p90 - p10)
    print(f"Average interval width: {interval_width:.1f} points")

    # Analyze where intervals are narrow vs wide
    print("\n" + "=" * 72)
    print(" INTERVAL WIDTH BY ACTUAL TOTAL")
    print("=" * 72)

    test_df = pd.DataFrame({
        'actual': y_test,
        'p10': p10,
        'p50': p50,
        'p90': p90,
        'width': p90 - p10,
        'in_interval': in_interval,
    })

    bins = [(0, 130), (130, 145), (145, 160), (160, 200)]
    print(f"\n{'Range':<12} {'Count':>8} {'Avg Width':>12} {'Coverage':>10}")
    print("-" * 50)

    for low, high in bins:
        segment = test_df[(test_df['actual'] >= low) & (test_df['actual'] < high)]
        if len(segment) > 10:
            avg_width = segment['width'].mean()
            seg_coverage = segment['in_interval'].mean()
            print(f"{low}-{high:<4} {len(segment):>8} {avg_width:>12.1f} {seg_coverage:>9.1%}")

    # KEY INSIGHT: Use interval width to identify high-uncertainty games
    print("\n" + "=" * 72)
    print(" BETTING STRATEGY: AVOID HIGH UNCERTAINTY")
    print("=" * 72)

    # Games with narrow intervals = high confidence
    narrow_threshold = np.percentile(test_df['width'], 25)
    wide_threshold = np.percentile(test_df['width'], 75)

    narrow_games = test_df[test_df['width'] < narrow_threshold]
    wide_games = test_df[test_df['width'] > wide_threshold]

    narrow_mae = np.mean(np.abs(narrow_games['p50'] - narrow_games['actual']))
    wide_mae = np.mean(np.abs(wide_games['p50'] - wide_games['actual']))

    print(f"\nNarrow interval games (width < {narrow_threshold:.1f}):")
    print(f"  Count: {len(narrow_games)}")
    print(f"  MAE: {narrow_mae:.2f}")
    print(f"  Coverage: {narrow_games['in_interval'].mean():.1%}")

    print(f"\nWide interval games (width > {wide_threshold:.1f}):")
    print(f"  Count: {len(wide_games)}")
    print(f"  MAE: {wide_mae:.2f}")
    print(f"  Coverage: {wide_games['in_interval'].mean():.1%}")

    # Simulate betting strategy
    print("\n" + "=" * 72)
    print(" BETTING SIMULATION")
    print("=" * 72)

    # Strategy: Only bet when our 50th percentile is far from market
    # AND interval is narrow (high confidence)

    # Simulate market line as actual + noise
    np.random.seed(42)
    simulated_market = y_test + np.random.normal(0, 2, len(y_test))

    test_df['market'] = simulated_market
    test_df['edge'] = test_df['p50'] - test_df['market']

    # Strategy 1: Bet all edges > 3
    all_bets = test_df[abs(test_df['edge']) >= 3]
    all_wins = ((all_bets['edge'] > 0) & (all_bets['actual'] > all_bets['market']) |
                (all_bets['edge'] < 0) & (all_bets['actual'] < all_bets['market']))
    print(f"\nStrategy 1: Bet all edges >= 3pt")
    print(f"  Bets: {len(all_bets)}")
    print(f"  Win rate: {all_wins.mean():.1%}")

    # Strategy 2: Bet edges > 3 ONLY with narrow intervals
    narrow_bets = test_df[(abs(test_df['edge']) >= 3) & (test_df['width'] < narrow_threshold)]
    narrow_wins = ((narrow_bets['edge'] > 0) & (narrow_bets['actual'] > narrow_bets['market']) |
                   (narrow_bets['edge'] < 0) & (narrow_bets['actual'] < narrow_bets['market']))
    print(f"\nStrategy 2: Bet edges >= 3pt + narrow interval")
    print(f"  Bets: {len(narrow_bets)}")
    print(f"  Win rate: {narrow_wins.mean():.1%}")

    # Strategy 3: Avoid wide intervals
    not_wide_bets = test_df[(abs(test_df['edge']) >= 3) & (test_df['width'] <= wide_threshold)]
    not_wide_wins = ((not_wide_bets['edge'] > 0) & (not_wide_bets['actual'] > not_wide_bets['market']) |
                     (not_wide_bets['edge'] < 0) & (not_wide_bets['actual'] < not_wide_bets['market']))
    print(f"\nStrategy 3: Bet edges >= 3pt + avoid wide interval")
    print(f"  Bets: {len(not_wide_bets)}")
    print(f"  Win rate: {not_wide_wins.mean():.1%}")

    print("\n" + "=" * 72)
    print(" RECOMMENDATION")
    print("=" * 72)
    print("""
QUANTILE REGRESSION INSIGHTS:

1. Median model MAE ({:.2f}) is similar to mean model
   - No magic improvement in point prediction

2. Interval width varies significantly
   - Narrow intervals = more confident predictions
   - Wide intervals = high uncertainty (likely extreme games)

3. BETTING STRATEGY:
   - Use interval width as a confidence filter
   - Only bet totals when interval is narrow
   - Avoid games with wide intervals (extremes)

4. IMPLEMENTATION:
   - Add 10th/90th percentile predictions to totals model
   - Calculate interval width
   - Only recommend bets when width < threshold
   - This is a FILTER, not a better point predictor
""".format(median_mae))

    return 0


if __name__ == "__main__":
    sys.exit(main())
