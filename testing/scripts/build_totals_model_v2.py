#!/usr/bin/env python3
"""
Build Totals Model v2 - Focus on capturing extreme games

Key insight from v1: All models regress to mean, missing extreme games.
This version tries:
1. Quantile regression to estimate distribution
2. Separate models for different tempo buckets
3. Hybrid approach: use ML for adjustment, not direct prediction
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, QuantileRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"


def load_all_data():
    """Load games and ratings."""
    all_games = []
    all_ratings = {}

    for season in range(2019, 2025):
        games_path = HISTORICAL_DIR / f"games_{season}.csv"
        if games_path.exists():
            df = pd.read_csv(games_path)
            df['season'] = season
            all_games.append(df)

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
                            'tor': float(team_data[12]) if isinstance(team_data[12], (int, float)) else 18.5,
                            'tord': float(team_data[13]) if isinstance(team_data[13], (int, float)) else 18.5,
                            'orb': float(team_data[14]) if isinstance(team_data[14], (int, float)) else 28.0,
                            'drb': float(team_data[15]) if isinstance(team_data[15], (int, float)) else 72.0,
                            'ftr': float(team_data[16]) if isinstance(team_data[16], (int, float)) else 33.0,
                            'ftrd': float(team_data[17]) if isinstance(team_data[17], (int, float)) else 33.0,
                            '3pr': float(team_data[22]) if isinstance(team_data[22], (int, float)) else 35.0,
                            '3prd': float(team_data[23]) if isinstance(team_data[23], (int, float)) else 35.0,
                        }
                    except (ValueError, TypeError):
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
        " boilermakers", " hawkeyes", " badgers", " gophers",
        " jayhawks", " sooners", " longhorns", " aggies", " hawks",
        " razorbacks", " volunteers", " crimson tide", " rebels",
        " gamecocks", " hurricanes", " seminoles", " yellow jackets",
        " red raiders", " horned frogs", " cowboys", " cyclones",
        " mountaineers", " red storm", " fighting irish", " panthers",
        " cardinals", " bearcats", " musketeers", " bluejays",
        " golden eagles", " pirates", " gaels", " dons", " broncos",
        " cougars", " aztecs", " wolf pack", " demon deacons",
        " friars", " waves", " colonels", " black bears",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name.strip()


def get_team_stats(name: str, ratings: dict) -> dict:
    defaults = {
        'adj_o': 106.0, 'adj_d': 106.0, 'adj_t': 68.0, 'barthag': 0.5,
        'efg': 50.0, 'efgd': 50.0, 'tor': 18.5, 'tord': 18.5,
        'orb': 28.0, 'drb': 72.0, 'ftr': 33.0, 'ftrd': 33.0,
        '3pr': 35.0, '3prd': 35.0,
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

        # Calculate baseline prediction (our current formula)
        avg_tempo = (home['adj_t'] + away['adj_t']) / 2
        home_eff = home['adj_o'] + away['adj_d'] - 106.0
        away_eff = away['adj_o'] + home['adj_d'] - 106.0
        baseline_total = (home_eff + away_eff) * avg_tempo / 100.0 - 4.6  # With calibration

        feat = {
            # Baseline prediction as anchor
            'baseline_total': baseline_total,

            # Raw efficiency metrics
            'home_adj_o': home['adj_o'],
            'home_adj_d': home['adj_d'],
            'away_adj_o': away['adj_o'],
            'away_adj_d': away['adj_d'],

            # Tempo features (key for extremes)
            'home_tempo': home['adj_t'],
            'away_tempo': away['adj_t'],
            'avg_tempo': avg_tempo,
            'tempo_sum': home['adj_t'] + away['adj_t'],
            'tempo_diff': abs(home['adj_t'] - away['adj_t']),
            'is_fast_game': 1 if avg_tempo > 70 else 0,
            'is_slow_game': 1 if avg_tempo < 66 else 0,

            # Efficiency sums
            'total_off': home['adj_o'] + away['adj_o'],
            'total_def': home['adj_d'] + away['adj_d'],
            'total_net': (home['adj_o'] - home['adj_d']) + (away['adj_o'] - away['adj_d']),

            # Quality metrics
            'home_barthag': home['barthag'],
            'away_barthag': away['barthag'],
            'avg_barthag': (home['barthag'] + away['barthag']) / 2,
            'barthag_diff': abs(home['barthag'] - away['barthag']),

            # Shooting profile
            'home_efg': home['efg'],
            'away_efg': away['efg'],
            'avg_efg': (home['efg'] + away['efg']) / 2,
            'home_3pr': home['3pr'],
            'away_3pr': away['3pr'],
            'avg_3pr': (home['3pr'] + away['3pr']) / 2,

            # Turnover factors
            'home_tor': home['tor'],
            'away_tor': away['tor'],
            'avg_tor': (home['tor'] + away['tor']) / 2,

            # Rebounding
            'home_orb': home['orb'],
            'away_orb': away['orb'],
            'home_drb': home['drb'],
            'away_drb': away['drb'],

            # Free throw rate
            'home_ftr': home['ftr'],
            'away_ftr': away['ftr'],

            # Neutral indicator
            'is_neutral': 1 if game.get('neutral', False) else 0,
        }

        features.append(feat)
        actual_total = game['home_score'] + game['away_score']
        targets.append(actual_total)

    return pd.DataFrame(features), np.array(targets)


def main():
    print("\n")
    print("=" * 72)
    print(" BUILDING TOTALS MODEL v2 - CAPTURING EXTREMES")
    print("=" * 72)

    games_df, all_ratings = load_all_data()
    print(f"\nLoaded {len(games_df)} games, {len(all_ratings)} seasons of ratings")

    X, y = build_features(games_df, all_ratings)
    print(f"Built {len(X)} samples with {len(X.columns)} features")

    X = X.fillna(X.mean())
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Get baseline predictions
    baseline_pred = X_test['baseline_total'].values
    baseline_mae = np.mean(np.abs(baseline_pred - y_test))
    print(f"\nBaseline MAE: {baseline_mae:.2f}")

    # Scale for regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print("\n" + "=" * 72)
    print(" APPROACH 1: HYBRID MODEL (Predict adjustment to baseline)")
    print("=" * 72)

    # Instead of predicting total directly, predict the ERROR in baseline
    # This way the model learns WHEN baseline is wrong
    y_train_error = y_train - X_train['baseline_total'].values
    y_test_error = y_test - X_test['baseline_total'].values

    # Train model to predict baseline error
    error_model = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
    error_model.fit(X_train, y_train_error)
    predicted_error = error_model.predict(X_test)

    # Adjusted prediction = baseline + predicted error
    hybrid_pred = baseline_pred + predicted_error
    hybrid_mae = np.mean(np.abs(hybrid_pred - y_test))
    hybrid_bias = np.mean(hybrid_pred - y_test)
    hybrid_std = np.std(hybrid_pred)

    print(f"\nHybrid Model (baseline + learned adjustment):")
    print(f"  MAE:  {hybrid_mae:.2f} (baseline: {baseline_mae:.2f})")
    print(f"  Improvement: {baseline_mae - hybrid_mae:.2f} points")
    print(f"  Bias: {hybrid_bias:+.2f}")
    print(f"  Pred Std: {hybrid_std:.2f} (actual: {np.std(y_test):.2f})")

    # Feature importance for error prediction
    print("\nTop features for predicting baseline errors:")
    importance = pd.DataFrame({
        'feature': X.columns,
        'importance': error_model.feature_importances_
    }).sort_values('importance', ascending=False)
    for _, row in importance.head(10).iterrows():
        print(f"  {row['feature']:<25} {row['importance']:.4f}")

    print("\n" + "=" * 72)
    print(" APPROACH 2: TEMPO-STRATIFIED MODELS")
    print("=" * 72)

    # Train separate models for different tempo regimes
    tempo_bins = [
        ('slow', X['avg_tempo'] < 66),
        ('medium', (X['avg_tempo'] >= 66) & (X['avg_tempo'] < 70)),
        ('fast', X['avg_tempo'] >= 70),
    ]

    strat_preds = np.zeros(len(X_test))

    for name, mask_all in tempo_bins:
        mask_train = mask_all.iloc[X_train.index]
        mask_test = mask_all.iloc[X_test.index]

        if mask_train.sum() < 50:
            continue

        X_train_sub = X_train[mask_train]
        y_train_sub = y_train[mask_train.values]
        X_test_sub = X_test[mask_test]

        model = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
        model.fit(X_train_sub, y_train_sub)
        pred_sub = model.predict(X_test_sub)

        # Fill in predictions
        strat_preds[mask_test.values] = pred_sub

        # Evaluate this segment
        y_test_sub = y_test[mask_test.values]
        mae = np.mean(np.abs(pred_sub - y_test_sub))
        bias = np.mean(pred_sub - y_test_sub)
        print(f"\n{name.upper()} tempo games ({mask_test.sum()} test samples):")
        print(f"  MAE: {mae:.2f}, Bias: {bias:+.2f}")

    # Fill remaining with baseline
    strat_preds[strat_preds == 0] = baseline_pred[strat_preds == 0]
    strat_mae = np.mean(np.abs(strat_preds - y_test))
    print(f"\nStratified overall MAE: {strat_mae:.2f}")

    print("\n" + "=" * 72)
    print(" APPROACH 3: QUANTILE REGRESSION")
    print("=" * 72)

    # Predict different quantiles to understand the distribution
    quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]

    print("\nTraining quantile models...")
    quantile_preds = {}
    for q in quantiles:
        qr = QuantileRegressor(quantile=q, alpha=0.1, solver='highs')
        qr.fit(X_train_scaled, y_train)
        quantile_preds[q] = qr.predict(X_test_scaled)
        print(f"  Q{int(q*100):02d}: {np.mean(quantile_preds[q]):.1f}")

    # Use median (Q50) as prediction
    median_pred = quantile_preds[0.5]
    median_mae = np.mean(np.abs(median_pred - y_test))
    print(f"\nMedian (Q50) MAE: {median_mae:.2f}")

    # Calculate prediction intervals
    interval_90 = quantile_preds[0.9] - quantile_preds[0.1]
    print(f"Average 80% prediction interval width: {np.mean(interval_90):.1f}")

    # Check coverage - what % of actuals fall within 80% interval
    in_interval = (y_test >= quantile_preds[0.1]) & (y_test <= quantile_preds[0.9])
    coverage = np.mean(in_interval)
    print(f"80% interval coverage: {coverage*100:.1f}% (target: 80%)")

    print("\n" + "=" * 72)
    print(" ERROR ANALYSIS BY SEGMENT")
    print("=" * 72)

    # Compare approaches by actual total segment
    test_df = pd.DataFrame({
        'actual': y_test,
        'baseline': baseline_pred,
        'hybrid': hybrid_pred,
        'median_qr': median_pred,
    })

    segments = [(0, 120), (120, 140), (140, 160), (160, 180), (180, 300)]
    print(f"\n{'Segment':<12} {'Count':>6} {'Baseline':>10} {'Hybrid':>10} {'Quantile':>10}")
    print("-" * 55)

    for low, high in segments:
        seg = test_df[(test_df['actual'] >= low) & (test_df['actual'] < high)]
        if len(seg) < 5:
            continue
        base_mae = np.mean(np.abs(seg['baseline'] - seg['actual']))
        hyb_mae = np.mean(np.abs(seg['hybrid'] - seg['actual']))
        qr_mae = np.mean(np.abs(seg['median_qr'] - seg['actual']))
        print(f"{low}-{high:<6} {len(seg):>6} {base_mae:>10.2f} {hyb_mae:>10.2f} {qr_mae:>10.2f}")

    # Summary
    print("\n" + "=" * 72)
    print(" SUMMARY")
    print("=" * 72)

    best_mae = min(baseline_mae, hybrid_mae, strat_mae, median_mae)
    best_method = ['Baseline', 'Hybrid', 'Stratified', 'Quantile'][[baseline_mae, hybrid_mae, strat_mae, median_mae].index(best_mae)]

    print(f"""
Results:
  Baseline Formula:    {baseline_mae:.2f} MAE
  Hybrid Adjustment:   {hybrid_mae:.2f} MAE
  Tempo Stratified:    {strat_mae:.2f} MAE
  Quantile Median:     {median_mae:.2f} MAE

Best: {best_method} with {best_mae:.2f} MAE
Market benchmark: ~10-11 MAE

Gap to market: {best_mae - 10.5:.2f} points

The fundamental limitation:
- We predict std of {hybrid_std:.1f} but actual std is {np.std(y_test):.1f}
- Extreme games (< 120 or > 180) are hard to predict
- Market likely uses additional data (injuries, rest, travel, motivation)
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
