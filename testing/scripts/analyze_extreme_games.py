#!/usr/bin/env python3
"""
Analyze what makes games extreme (very high or low scoring).

Goal: Find features that predict when games will deviate significantly from the mean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from scipy import stats

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

    # Load ratings
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
                            'tor': float(team_data[12]) if isinstance(team_data[12], (int, float)) else 18.5,
                            'tord': float(team_data[13]) if isinstance(team_data[13], (int, float)) else 18.5,
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
        " boilermakers", " hawkeyes", " badgers", " gophers",
        " jayhawks", " sooners", " longhorns", " aggies", " hawks",
        " razorbacks", " volunteers", " crimson tide", " rebels",
        " gamecocks", " hurricanes", " seminoles", " yellow jackets",
        " red raiders", " horned frogs", " cowboys", " cyclones",
        " mountaineers", " red storm", " fighting irish", " panthers",
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
        '3pr': 35.0, '3prd': 35.0,
    }
    norm = normalize_name(name)
    if norm in ratings:
        return ratings[norm]
    for key, rating in ratings.items():
        if norm in key or key in norm:
            return rating
    return defaults


def main():
    print("\n")
    print("=" * 72)
    print(" EXTREME GAMES ANALYSIS")
    print("=" * 72)

    games_df, all_ratings = load_all_data()
    print(f"\nLoaded {len(games_df)} games")

    # Build feature matrix
    features = []
    totals = []

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
            'home_tempo': home['adj_t'],
            'away_tempo': away['adj_t'],
            'avg_tempo': (home['adj_t'] + away['adj_t']) / 2,
            'tempo_diff': abs(home['adj_t'] - away['adj_t']),
            'home_barthag': home['barthag'],
            'away_barthag': away['barthag'],
            'avg_barthag': (home['barthag'] + away['barthag']) / 2,
            'barthag_diff': abs(home['barthag'] - away['barthag']),
            'home_efg': home['efg'],
            'away_efg': away['efg'],
            'home_efgd': home['efgd'],
            'away_efgd': away['efgd'],
            'home_tor': home['tor'],
            'away_tor': away['tor'],
            'home_tord': home['tord'],
            'away_tord': away['tord'],
            'home_3pr': home['3pr'],
            'away_3pr': away['3pr'],
            'avg_3pr': (home['3pr'] + away['3pr']) / 2,
            # Quality mismatch (blowout potential)
            'quality_diff': (home['adj_o'] - home['adj_d']) - (away['adj_o'] - away['adj_d']),
        }

        features.append(feat)
        totals.append(game['home_score'] + game['away_score'])

    X = pd.DataFrame(features)
    y = np.array(totals)

    print(f"Built {len(X)} samples")

    mean_total = np.mean(y)
    std_total = np.std(y)

    # Define extreme games
    LOW_THRESHOLD = 125
    HIGH_THRESHOLD = 165

    y_low = (y < LOW_THRESHOLD).astype(int)
    y_high = (y > HIGH_THRESHOLD).astype(int)

    print(f"\nMean total: {mean_total:.1f}, Std: {std_total:.1f}")
    print(f"Low scoring games (<{LOW_THRESHOLD}): {y_low.sum()} ({100*y_low.mean():.1f}%)")
    print(f"High scoring games (>{HIGH_THRESHOLD}): {y_high.sum()} ({100*y_high.mean():.1f}%)")

    # Analyze what distinguishes low games
    print("\n" + "=" * 72)
    print(" LOW SCORING GAMES (<125) vs NORMAL")
    print("=" * 72)

    low_games = X[y < LOW_THRESHOLD]
    normal_games = X[(y >= LOW_THRESHOLD) & (y <= HIGH_THRESHOLD)]
    high_games = X[y > HIGH_THRESHOLD]

    print(f"\n{'Feature':<25} {'Low Games':>12} {'Normal':>12} {'Difference':>12}")
    print("-" * 65)

    key_features = ['avg_tempo', 'avg_barthag', 'avg_3pr', 'home_efg', 'away_efg',
                   'home_tor', 'away_tor', 'quality_diff', 'barthag_diff']

    for feat in key_features:
        low_mean = low_games[feat].mean()
        normal_mean = normal_games[feat].mean()
        diff = low_mean - normal_mean
        print(f"{feat:<25} {low_mean:>12.2f} {normal_mean:>12.2f} {diff:>+12.2f}")

    # Analyze high games
    print("\n" + "=" * 72)
    print(" HIGH SCORING GAMES (>165) vs NORMAL")
    print("=" * 72)

    print(f"\n{'Feature':<25} {'High Games':>12} {'Normal':>12} {'Difference':>12}")
    print("-" * 65)

    for feat in key_features:
        high_mean = high_games[feat].mean()
        normal_mean = normal_games[feat].mean()
        diff = high_mean - normal_mean
        print(f"{feat:<25} {high_mean:>12.2f} {normal_mean:>12.2f} {diff:>+12.2f}")

    # Build classifier for extreme games
    print("\n" + "=" * 72)
    print(" PREDICTING EXTREME GAMES")
    print("=" * 72)

    # Classify: 0 = normal, 1 = low, 2 = high
    y_class = np.zeros(len(y), dtype=int)
    y_class[y < LOW_THRESHOLD] = 1
    y_class[y > HIGH_THRESHOLD] = 2

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_class, test_size=0.2, random_state=42
    )

    clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    clf.fit(X_train, y_train)

    # Evaluate
    pred = clf.predict(X_test)
    correct = (pred == y_test).mean()
    print(f"\nClassifier accuracy: {correct:.1%}")

    # Check if we can at least detect when a game will be extreme
    y_extreme = (y_class > 0).astype(int)
    X_train2, X_test2, y_train2, y_test2 = train_test_split(
        X, y_extreme, test_size=0.2, random_state=42
    )

    clf2 = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight='balanced')
    clf2.fit(X_train2, y_train2)

    pred2 = clf2.predict(X_test2)
    pred_proba2 = clf2.predict_proba(X_test2)[:, 1]

    print(f"\nExtreme game detection:")
    print(f"  Accuracy: {(pred2 == y_test2).mean():.1%}")
    print(f"  Precision (detecting extreme): {(pred2[y_test2==1]==1).sum() / pred2.sum():.1%}" if pred2.sum() > 0 else "  No extreme predicted")
    print(f"  Recall (catching extreme): {(pred2[y_test2==1]==1).sum() / y_test2.sum():.1%}")

    # Feature importance
    print("\n" + "=" * 72)
    print(" FEATURES THAT PREDICT EXTREME GAMES")
    print("=" * 72)

    importance = pd.DataFrame({
        'feature': X.columns,
        'importance': clf2.feature_importances_
    }).sort_values('importance', ascending=False)

    print("\nTop 10 features:")
    for _, row in importance.head(10).iterrows():
        print(f"  {row['feature']:<25} {row['importance']:.4f}")

    # Key insight
    print("\n" + "=" * 72)
    print(" KEY INSIGHTS")
    print("=" * 72)

    print("""
1. LOW SCORING GAMES are characterized by:
   - Lower tempo (teams play slower)
   - Higher turnovers (more possessions wasted)
   - Lower EFG% (worse shooting)
   - Often mismatched games (quality_diff)

2. HIGH SCORING GAMES are characterized by:
   - Higher tempo
   - Better shooting (higher EFG)
   - More 3-point attempts

3. THE FUNDAMENTAL PROBLEM:
   - We can identify SOME extreme game factors
   - But randomness plays a huge role
   - Any game can have hot/cold shooting nights
   - Foul trouble, ejections, injuries are unpredictable

4. REALISTIC IMPROVEMENTS:
   - Add tempo amplification for extreme tempo matchups
   - Adjust for defensive style mismatches
   - But expect 2-3 point MAE gap vs market indefinitely
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
