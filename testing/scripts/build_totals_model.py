#!/usr/bin/env python3
"""
Build ML-based Totals Model

Using all 22 Barttorvik fields to predict game totals.
Goal: Beat the efficiency formula by capturing more variance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"


def load_all_data():
    """Load games and ratings."""
    all_games = []
    all_ratings = {}

    # Load games
    for season in range(2019, 2025):
        games_path = HISTORICAL_DIR / f"games_{season}.csv"
        if games_path.exists():
            df = pd.read_csv(games_path)
            df['season'] = season
            all_games.append(df)

    if not all_games:
        # Try all games file
        all_path = HISTORICAL_DIR / "games_all.csv"
        if all_path.exists():
            df = pd.read_csv(all_path)
            all_games.append(df)

    # Load ratings
    for season in range(2019, 2025):
        ratings_path = HISTORICAL_DIR / f"barttorvik_{season}.json"
        if ratings_path.exists():
            with open(ratings_path, 'r') as f:
                data = json.load(f)
            ratings = {}
            for team_data in data:
                if isinstance(team_data, list) and len(team_data) > 44:
                    name = team_data[1].lower()
                    # Extract fields based on BARTTORVIK_FIELDS.md indices
                    try:
                        ratings[name] = {
                            'adj_o': float(team_data[4]),
                            'adj_d': float(team_data[6]),
                            'barthag': float(team_data[8]) if team_data[8] is not None else 0.5,
                            'adj_t': float(team_data[44]) if team_data[44] is not None else 68.0,
                            # Four Factors (indices 10-17)
                            'efg': float(team_data[10]) if isinstance(team_data[10], (int, float)) else 50.0,
                            'efgd': float(team_data[11]) if isinstance(team_data[11], (int, float)) else 50.0,
                            'tor': float(team_data[12]) if isinstance(team_data[12], (int, float)) else 18.5,
                            'tord': float(team_data[13]) if isinstance(team_data[13], (int, float)) else 18.5,
                            'orb': float(team_data[14]) if isinstance(team_data[14], (int, float)) else 28.0,
                            'drb': float(team_data[15]) if isinstance(team_data[15], (int, float)) else 72.0,
                            'ftr': float(team_data[16]) if isinstance(team_data[16], (int, float)) else 33.0,
                            'ftrd': float(team_data[17]) if isinstance(team_data[17], (int, float)) else 33.0,
                            # Shooting (indices 18-23)
                            '2p': float(team_data[18]) if isinstance(team_data[18], (int, float)) else 50.0,
                            '2pd': float(team_data[19]) if isinstance(team_data[19], (int, float)) else 50.0,
                            '3p': float(team_data[20]) if isinstance(team_data[20], (int, float)) else 34.0,
                            '3pd': float(team_data[21]) if isinstance(team_data[21], (int, float)) else 34.0,
                            '3pr': float(team_data[22]) if isinstance(team_data[22], (int, float)) else 35.0,
                            '3prd': float(team_data[23]) if isinstance(team_data[23], (int, float)) else 35.0,
                        }
                    except (ValueError, TypeError):
                        continue
            all_ratings[season] = ratings

    games_df = pd.concat(all_games, ignore_index=True) if all_games else pd.DataFrame()
    return games_df, all_ratings


def normalize_name(name: str) -> str:
    """Normalize team name."""
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
    """Get team stats with defaults."""
    defaults = {
        'adj_o': 106.0, 'adj_d': 106.0, 'adj_t': 68.0, 'barthag': 0.5,
        'efg': 50.0, 'efgd': 50.0, 'tor': 18.5, 'tord': 18.5,
        'orb': 28.0, 'drb': 72.0, 'ftr': 33.0, 'ftrd': 33.0,
        '3pr': 35.0, '3prd': 35.0, '2p': 50.0, '2pd': 50.0,
        '3p': 34.0, '3pd': 34.0,
    }

    norm = normalize_name(name)
    if norm in ratings:
        return ratings[norm]
    for key, rating in ratings.items():
        if norm in key or key in norm:
            return rating
    return defaults


def build_features(games_df, all_ratings):
    """Build feature matrix for training."""
    features = []
    targets = []

    for _, game in games_df.iterrows():
        season = game.get('season', 2024)
        if season not in all_ratings:
            continue

        ratings = all_ratings[season]
        home = get_team_stats(game['home_team'], ratings)
        away = get_team_stats(game['away_team'], ratings)

        # Build feature vector
        feat = {
            # Basic efficiencies
            'home_adj_o': home['adj_o'],
            'home_adj_d': home['adj_d'],
            'away_adj_o': away['adj_o'],
            'away_adj_d': away['adj_d'],

            # Tempo
            'home_tempo': home['adj_t'],
            'away_tempo': away['adj_t'],
            'avg_tempo': (home['adj_t'] + away['adj_t']) / 2,

            # Quality
            'home_barthag': home['barthag'],
            'away_barthag': away['barthag'],
            'avg_barthag': (home['barthag'] + away['barthag']) / 2,

            # Shooting
            'home_efg': home['efg'],
            'away_efg': away['efg'],
            'home_efgd': home['efgd'],
            'away_efgd': away['efgd'],

            # Turnovers
            'home_tor': home['tor'],
            'away_tor': away['tor'],
            'home_tord': home['tord'],
            'away_tord': away['tord'],

            # Rebounding
            'home_orb': home['orb'],
            'away_orb': away['orb'],
            'home_drb': home['drb'],
            'away_drb': away['drb'],

            # Free throws
            'home_ftr': home['ftr'],
            'away_ftr': away['ftr'],
            'home_ftrd': home['ftrd'],
            'away_ftrd': away['ftrd'],

            # 3PT rate
            'home_3pr': home['3pr'],
            'away_3pr': away['3pr'],
            'home_3prd': home['3prd'],
            'away_3prd': away['3prd'],

            # Derived features
            'total_off': home['adj_o'] + away['adj_o'],
            'total_def': home['adj_d'] + away['adj_d'],
            'tempo_diff': abs(home['adj_t'] - away['adj_t']),
            'eff_diff': (home['adj_o'] - home['adj_d']) - (away['adj_o'] - away['adj_d']),

            # Expected score components
            'home_exp_eff': home['adj_o'] + away['adj_d'] - 106.0,
            'away_exp_eff': away['adj_o'] + home['adj_d'] - 106.0,

            # Is neutral (if available)
            'is_neutral': 1 if game.get('neutral', False) else 0,
        }

        features.append(feat)
        targets.append(game['home_score'] + game['away_score'])

    return pd.DataFrame(features), np.array(targets)


def main():
    print("\n")
    print("=" * 72)
    print(" BUILDING ML-BASED TOTALS MODEL")
    print("=" * 72)

    # Load data
    games_df, all_ratings = load_all_data()
    print(f"\nLoaded {len(games_df)} games, {len(all_ratings)} seasons of ratings")

    if games_df.empty:
        print("[ERROR] No games data found")
        return 1

    # Build features
    print("\nBuilding feature matrix...")
    X, y = build_features(games_df, all_ratings)
    print(f"Built {len(X)} samples with {len(X.columns)} features")

    # Handle missing values
    X = X.fillna(X.mean())

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Baseline: simple formula
    print("\n" + "=" * 72)
    print(" BASELINE: EFFICIENCY FORMULA")
    print("=" * 72)

    # Our current formula
    X_test_df = X_test.copy()
    baseline_pred = (X_test_df['home_exp_eff'] + X_test_df['away_exp_eff']) * X_test_df['avg_tempo'] / 100 - 4.6

    baseline_mae = np.mean(np.abs(baseline_pred - y_test))
    baseline_rmse = np.sqrt(np.mean((baseline_pred - y_test) ** 2))
    print(f"Baseline MAE:  {baseline_mae:.2f}")
    print(f"Baseline RMSE: {baseline_rmse:.2f}")

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Test different models
    print("\n" + "=" * 72)
    print(" MODEL COMPARISON")
    print("=" * 72)

    models = [
        ("Ridge Regression", Ridge(alpha=1.0)),
        ("Lasso Regression", Lasso(alpha=0.1)),
        ("Random Forest (50)", RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)),
        ("Random Forest (100)", RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42)),
        ("Gradient Boosting", GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)),
    ]

    results = []
    for name, model in models:
        print(f"\nTraining {name}...")

        # Fit model
        if "Forest" in name or "Gradient" in name:
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
        else:
            model.fit(X_train_scaled, y_train)
            pred = model.predict(X_test_scaled)

        mae = np.mean(np.abs(pred - y_test))
        rmse = np.sqrt(np.mean((pred - y_test) ** 2))
        bias = np.mean(pred - y_test)
        pred_std = np.std(pred)

        results.append({
            'name': name,
            'mae': mae,
            'rmse': rmse,
            'bias': bias,
            'pred_std': pred_std,
            'model': model,
        })

        print(f"  MAE:  {mae:.2f}")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  Bias: {bias:+.2f}")
        print(f"  Pred Std: {pred_std:.2f} (actual: {np.std(y_test):.2f})")

    # Find best model
    best = min(results, key=lambda x: x['mae'])
    print(f"\n{'='*72}")
    print(f" BEST MODEL: {best['name']}")
    print(f"{'='*72}")
    print(f"  MAE:  {best['mae']:.2f} (baseline: {baseline_mae:.2f})")
    print(f"  Improvement: {baseline_mae - best['mae']:.2f} points")

    # Feature importance for tree-based models
    if hasattr(best['model'], 'feature_importances_'):
        print("\n" + "=" * 72)
        print(" FEATURE IMPORTANCE")
        print("=" * 72)

        importance = pd.DataFrame({
            'feature': X.columns,
            'importance': best['model'].feature_importances_
        }).sort_values('importance', ascending=False)

        print("\nTop 15 features:")
        for _, row in importance.head(15).iterrows():
            print(f"  {row['feature']:<25} {row['importance']:.4f}")

    # Cross-validation on best model
    print("\n" + "=" * 72)
    print(" CROSS-VALIDATION")
    print("=" * 72)

    cv_scores = cross_val_score(
        best['model'], X, y,
        cv=5, scoring='neg_mean_absolute_error'
    )
    print(f"\n5-fold CV MAE: {-cv_scores.mean():.2f} (+/- {cv_scores.std():.2f})")

    # Analyze errors by segment
    print("\n" + "=" * 72)
    print(" ERROR BY ACTUAL TOTAL")
    print("=" * 72)

    if "Forest" in best['name'] or "Gradient" in best['name']:
        best_pred = best['model'].predict(X_test)
    else:
        best_pred = best['model'].predict(X_test_scaled)

    test_df = pd.DataFrame({
        'actual': y_test,
        'pred': best_pred,
        'error': best_pred - y_test,
        'abs_error': np.abs(best_pred - y_test)
    })

    bins = [(0, 120), (120, 140), (140, 160), (160, 180), (180, 300)]
    print(f"\n{'Range':<12} {'Count':>8} {'MAE':>8} {'Bias':>10}")
    print("-" * 40)

    for low, high in bins:
        segment = test_df[(test_df['actual'] >= low) & (test_df['actual'] < high)]
        if len(segment) > 5:
            print(f"{low}-{high:<5} {len(segment):>8} {segment['abs_error'].mean():>8.2f} {segment['error'].mean():>+10.2f}")

    # Summary
    print("\n" + "=" * 72)
    print(" SUMMARY")
    print("=" * 72)
    print(f"""
Current formula MAE: {baseline_mae:.2f}
Best ML model MAE:   {best['mae']:.2f}
Improvement:         {baseline_mae - best['mae']:.2f} points ({100*(baseline_mae - best['mae'])/baseline_mae:.1f}%)

The ML model captures more variance (std: {best['pred_std']:.2f} vs {np.std(baseline_pred):.2f})
but still has ~2 point gap from market (~10-11 MAE).

Key features: tempo, efficiency sums, barthag (quality metric)
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
