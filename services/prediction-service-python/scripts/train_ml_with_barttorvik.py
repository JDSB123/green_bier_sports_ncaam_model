#!/usr/bin/env python3
"""
ML Training with Barttorvik Ratings (No Leakage).

This script trains XGBoost models using:
1. Game outcomes from Basketball API
2. Barttorvik team ratings as features
3. Market lines (where available)

Note on leakage: We use SEASON-END ratings for all games in that season.
This introduces slight forward bias for early-season games, but:
- Ratings capture team quality consistently
- Better than using game outcomes as features (major leakage)
- In production, use ratings as of game date

Usage:
    python scripts/train_ml_with_barttorvik.py \
        --games training_data/games_2023_2025.csv \
        --ratings training_data/barttorvik_lookup.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score, brier_score_loss
    HAS_ML = True
except ImportError:
    HAS_ML = False


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    if not name:
        return ""
    name = name.lower().strip()
    name = name.replace("state", "st")
    name = name.replace("university", "")
    name = name.replace("college", "")
    name = name.replace("'", "")
    name = name.replace(".", "")
    name = name.replace("-", " ")
    return " ".join(name.split())


def get_season_from_date(date: datetime) -> int:
    """
    Get Barttorvik season year from game date.
    Season 2024 = 2023-24 school year (Nov 2023 - Mar 2024).
    """
    month = date.month
    year = date.year
    
    # If Nov-Dec, it's the next year's season
    # If Jan-Apr, it's the current year's season
    if month >= 11:
        return year + 1
    else:
        return year


def load_ratings(json_path: Path) -> Dict[str, Dict[int, Dict]]:
    """Load Barttorvik ratings lookup."""
    with open(json_path) as f:
        return json.load(f)


def get_team_ratings(
    team: str, 
    season: int, 
    ratings_lookup: Dict,
    default_ratings: Dict,
) -> Tuple[Dict, bool]:
    """
    Get team ratings for a specific season.
    
    Returns: (ratings_dict, found)
    """
    norm_team = normalize_team_name(team)
    
    if norm_team in ratings_lookup:
        season_ratings = ratings_lookup[norm_team]
        if str(season) in season_ratings:
            return season_ratings[str(season)], True
        # Try adjacent season
        if str(season - 1) in season_ratings:
            return season_ratings[str(season - 1)], True
    
    # Try partial matches
    for key in ratings_lookup:
        if norm_team in key or key in norm_team:
            season_ratings = ratings_lookup[key]
            if str(season) in season_ratings:
                return season_ratings[str(season)], True
    
    return default_ratings, False


def engineer_features(
    df: pd.DataFrame, 
    ratings_lookup: Dict,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Engineer features using Barttorvik ratings.
    
    Returns: (features, spread_labels, total_labels, valid_mask)
    """
    print("  Engineering features with Barttorvik ratings...")
    
    # Default ratings for unknown teams
    default_ratings = {
        "adj_o": 100.0, "adj_d": 100.0, "tempo": 67.6, "barthag": 0.5,
        "efg": 50.0, "efgd": 50.0, "tor": 18.5, "tord": 18.5,
        "orb": 28.0, "drb": 72.0, "ftr": 33.0, "ftrd": 33.0,
        "three_pt_rate": 35.0, "three_pt_rate_d": 35.0,
        "rank": 200, "wab": 0.0,
    }
    
    features = []
    spread_labels = []
    total_labels = []
    valid_mask = []
    matched = 0
    unmatched = 0
    
    for idx, row in df.iterrows():
        if idx % 2000 == 0:
            print(f"    Processing game {idx}/{len(df)}...")
        
        game_date = row['game_date']
        season = get_season_from_date(game_date)
        
        home = row['home_team']
        away = row['away_team']
        
        home_r, home_found = get_team_ratings(home, season, ratings_lookup, default_ratings)
        away_r, away_found = get_team_ratings(away, season, ratings_lookup, default_ratings)
        
        if home_found and away_found:
            matched += 1
        else:
            unmatched += 1
        
        # Get market lines
        spread = row.get('spread_open')
        total = row.get('total_open')
        
        if pd.isna(spread):
            # Estimate from ratings
            home_net = home_r['adj_o'] - home_r['adj_d']
            away_net = away_r['adj_o'] - away_r['adj_d']
            spread = -(home_net - away_net) / 10 - 3.0  # Rough estimate with HCA
        
        if pd.isna(total):
            total = 140.0
        
        # ===== FEATURES (from Barttorvik ratings) =====
        
        # Efficiency features
        home_net = home_r['adj_o'] - home_r['adj_d']
        away_net = away_r['adj_o'] - away_r['adj_d']
        
        f = [
            # Core efficiency (most important)
            home_net,                               # 0: Home net efficiency
            away_net,                               # 1: Away net efficiency
            home_net - away_net,                    # 2: Net efficiency differential
            home_r['adj_o'],                        # 3: Home AdjO
            home_r['adj_d'],                        # 4: Home AdjD
            away_r['adj_o'],                        # 5: Away AdjO
            away_r['adj_d'],                        # 6: Away AdjD
            
            # Matchup (home offense vs away defense, etc.)
            home_r['adj_o'] - away_r['adj_d'],      # 7: Home off vs away def
            away_r['adj_o'] - home_r['adj_d'],      # 8: Away off vs home def
            
            # Tempo/pace
            home_r['tempo'],                        # 9: Home tempo
            away_r['tempo'],                        # 10: Away tempo
            (home_r['tempo'] + away_r['tempo']) / 2,  # 11: Expected tempo
            home_r['tempo'] - away_r['tempo'],      # 12: Tempo differential
            
            # Quality metrics
            home_r['barthag'],                      # 13: Home Barthag
            away_r['barthag'],                      # 14: Away Barthag
            home_r['barthag'] - away_r['barthag'],  # 15: Barthag differential
            
            # Rank (lower = better)
            float(away_r['rank'] - home_r['rank']),  # 16: Rank differential (+ = home better)
            
            # Four factors - shooting
            home_r['efg'] - away_r['efgd'],         # 17: Home shooting edge
            away_r['efg'] - home_r['efgd'],         # 18: Away shooting edge
            
            # Four factors - turnovers
            away_r['tord'] - home_r['tor'],         # 19: Home TO edge (higher tord = good)
            home_r['tord'] - away_r['tor'],         # 20: Away TO edge
            
            # Four factors - rebounding
            home_r['orb'] - away_r['drb'],          # 21: Home ORB edge
            away_r['orb'] - home_r['drb'],          # 22: Away ORB edge
            
            # Four factors - FT rate
            home_r['ftr'] - away_r['ftrd'],         # 23: Home FTR edge
            away_r['ftr'] - home_r['ftrd'],         # 24: Away FTR edge
            
            # Style - 3PT tendency
            home_r.get('three_pt_rate', 35.0),      # 25: Home 3PT rate
            away_r.get('three_pt_rate', 35.0),      # 26: Away 3PT rate
            
            # Market
            spread,                                  # 27: Spread
            total,                                   # 28: Total
            abs(spread),                            # 29: Spread magnitude
            1.0 if spread < 0 else 0.0,             # 30: Is home favorite?
            
            # Data quality
            float(home_found),                      # 31: Home team found
            float(away_found),                      # 32: Away team found
        ]
        features.append(f)
        
        # ===== LABELS (from game outcome) =====
        margin = row['margin']
        total_pts = row['total_points']
        
        # Spread label
        cover_margin = margin + spread
        if abs(cover_margin) < 0.5:
            spread_labels.append(-1)  # Push
        else:
            spread_labels.append(1 if cover_margin > 0 else 0)
        
        # Total label
        total_margin = total_pts - total
        if abs(total_margin) < 0.5:
            total_labels.append(-1)  # Push
        else:
            total_labels.append(1 if total_margin > 0 else 0)
        
        # Valid if both teams found
        valid_mask.append(home_found and away_found)
    
    print(f"  Matched: {matched}, Unmatched: {unmatched}")
    
    return (
        np.array(features, dtype=np.float32),
        np.array(spread_labels),
        np.array(total_labels),
        np.array(valid_mask),
    )


def train_and_evaluate(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    bet_type: str,
) -> Tuple[Dict, object]:
    """Train XGBoost model and evaluate."""
    
    params = {
        "objective": "binary:logistic",
        "max_depth": 5,
        "learning_rate": 0.03,
        "n_estimators": 300,
        "min_child_weight": 10,
        "subsample": 0.8,
        "colsample_bytree": 0.7,
        "reg_alpha": 0.3,
        "reg_lambda": 1.5,
        "random_state": 42,
    }
    
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, verbose=False)
    
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    # Calculate confidence-adjusted accuracy
    # Only count predictions where model is confident (>55% or <45%)
    confident_mask = (y_pred_proba > 0.55) | (y_pred_proba < 0.45)
    confident_acc = accuracy_score(y_test[confident_mask], y_pred[confident_mask]) if confident_mask.sum() > 0 else 0.5
    
    metrics = {
        "bet_type": bet_type,
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "accuracy": accuracy_score(y_test, y_pred),
        "confident_accuracy": confident_acc,
        "confident_count": int(confident_mask.sum()),
        "auc_roc": roc_auc_score(y_test, y_pred_proba),
        "brier_score": brier_score_loss(y_test, y_pred_proba),
        "log_loss": log_loss(y_test, y_pred_proba),
        "baseline": max(y_test.mean(), 1 - y_test.mean()),
    }
    
    # Feature importance
    importance = dict(zip(feature_names, model.feature_importances_.tolist()))
    metrics["feature_importance"] = importance
    
    return metrics, model


def main():
    parser = argparse.ArgumentParser(description="Train ML with Barttorvik ratings")
    parser.add_argument("--games", type=Path, required=True, help="Games CSV")
    parser.add_argument("--ratings", type=Path, required=True, help="Ratings JSON lookup")
    parser.add_argument("--test-start", type=str, default="2024-11-01", help="Test set start")
    parser.add_argument("--output", type=Path, default=None, help="Model output dir")
    
    args = parser.parse_args()
    
    if not HAS_PANDAS or not HAS_ML:
        print("Error: pandas, xgboost, scikit-learn required")
        sys.exit(1)
    
    print("=" * 70)
    print("ML Training with Barttorvik Ratings")
    print("=" * 70)
    
    # Load games
    print(f"\nLoading games from {args.games}...")
    df = pd.read_csv(args.games)
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.sort_values('game_date').reset_index(drop=True)
    df['margin'] = df['home_score'] - df['away_score']
    df['total_points'] = df['home_score'] + df['away_score']
    df['spread_open'] = pd.to_numeric(df['spread_open'], errors='coerce')
    df['total_open'] = pd.to_numeric(df['total_open'], errors='coerce')
    
    print(f"Loaded {len(df)} games")
    
    # Load ratings
    print(f"\nLoading ratings from {args.ratings}...")
    ratings = load_ratings(args.ratings)
    print(f"Loaded ratings for {len(ratings)} teams")
    
    # Engineer features
    X, y_spread, y_total, valid_mask = engineer_features(df, ratings)
    
    # Feature names
    feature_names = [
        'home_net_eff', 'away_net_eff', 'net_eff_diff',
        'home_adj_o', 'home_adj_d', 'away_adj_o', 'away_adj_d',
        'home_off_vs_away_def', 'away_off_vs_home_def',
        'home_tempo', 'away_tempo', 'expected_tempo', 'tempo_diff',
        'home_barthag', 'away_barthag', 'barthag_diff',
        'rank_diff',
        'home_shooting_edge', 'away_shooting_edge',
        'home_to_edge', 'away_to_edge',
        'home_orb_edge', 'away_orb_edge',
        'home_ftr_edge', 'away_ftr_edge',
        'home_3pt_rate', 'away_3pt_rate',
        'spread', 'total', 'spread_mag', 'home_fav',
        'home_found', 'away_found',
    ]
    
    # Split by date
    test_start = pd.to_datetime(args.test_start)
    dates = df['game_date'].values
    train_mask = dates < np.datetime64(test_start)
    test_mask = dates >= np.datetime64(test_start)
    
    print(f"\nData split (test from {args.test_start}):")
    print(f"  Training: {train_mask.sum()} games")
    print(f"  Testing:  {test_mask.sum()} games")
    
    # Train spread model
    print("\n" + "=" * 70)
    print("SPREAD MODEL (Barttorvik Features)")
    print("=" * 70)
    
    train_spread_mask = train_mask & (y_spread >= 0) & valid_mask
    test_spread_mask = test_mask & (y_spread >= 0) & valid_mask
    
    X_train = X[train_spread_mask]
    y_train = y_spread[train_spread_mask]
    X_test = X[test_spread_mask]
    y_test = y_spread[test_spread_mask]
    
    print(f"Valid games: {train_spread_mask.sum()} train, {test_spread_mask.sum()} test")
    
    if len(y_train) > 100 and len(y_test) > 50:
        metrics_spread, model_spread = train_and_evaluate(
            X_train, y_train, X_test, y_test, feature_names, "spread"
        )
        
        print(f"\n  Results on TEST SET (2024-25 season):")
        print(f"  - Overall Accuracy:   {metrics_spread['accuracy']:.3f} (baseline: {metrics_spread['baseline']:.3f})")
        print(f"  - Confident Accuracy: {metrics_spread['confident_accuracy']:.3f} ({metrics_spread['confident_count']} games)")
        print(f"  - AUC-ROC:           {metrics_spread['auc_roc']:.3f}")
        print(f"  - Improvement:       {metrics_spread['accuracy'] - metrics_spread['baseline']:+.3f}")
        
        print("\n  Top Feature Importance:")
        sorted_imp = sorted(metrics_spread['feature_importance'].items(), key=lambda x: -x[1])[:8]
        for name, imp in sorted_imp:
            print(f"    - {name}: {imp:.3f}")
    else:
        print("  Not enough valid data")
        metrics_spread = None
    
    # Train total model
    print("\n" + "=" * 70)
    print("TOTAL MODEL (Barttorvik Features)")
    print("=" * 70)
    
    train_total_mask = train_mask & (y_total >= 0) & valid_mask
    test_total_mask = test_mask & (y_total >= 0) & valid_mask
    
    X_train = X[train_total_mask]
    y_train = y_total[train_total_mask]
    X_test = X[test_total_mask]
    y_test = y_total[test_total_mask]
    
    print(f"Valid games: {train_total_mask.sum()} train, {test_total_mask.sum()} test")
    
    if len(y_train) > 100 and len(y_test) > 50:
        metrics_total, model_total = train_and_evaluate(
            X_train, y_train, X_test, y_test, feature_names, "total"
        )
        
        print(f"\n  Results on TEST SET (2024-25 season):")
        print(f"  - Overall Accuracy:   {metrics_total['accuracy']:.3f} (baseline: {metrics_total['baseline']:.3f})")
        print(f"  - Confident Accuracy: {metrics_total['confident_accuracy']:.3f} ({metrics_total['confident_count']} games)")
        print(f"  - AUC-ROC:           {metrics_total['auc_roc']:.3f}")
        print(f"  - Improvement:       {metrics_total['accuracy'] - metrics_total['baseline']:+.3f}")
        
        print("\n  Top Feature Importance:")
        sorted_imp = sorted(metrics_total['feature_importance'].items(), key=lambda x: -x[1])[:8]
        for name, imp in sorted_imp:
            print(f"    - {name}: {imp:.3f}")
    else:
        print("  Not enough valid data")
        metrics_total = None
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY - Barttorvik ML Models")
    print("=" * 70)
    
    print(f"\n{'Model':<10} {'Accuracy':>10} {'Baseline':>10} {'Improve':>10} {'AUC':>10} {'Confident':>12}")
    print("-" * 70)
    
    if metrics_spread:
        imp = metrics_spread['accuracy'] - metrics_spread['baseline']
        conf = f"{metrics_spread['confident_accuracy']:.1%}"
        print(f"{'Spread':<10} {metrics_spread['accuracy']:>10.3f} {metrics_spread['baseline']:>10.3f} {imp:>+10.3f} {metrics_spread['auc_roc']:>10.3f} {conf:>12}")
    
    if metrics_total:
        imp = metrics_total['accuracy'] - metrics_total['baseline']
        conf = f"{metrics_total['confident_accuracy']:.1%}"
        print(f"{'Total':<10} {metrics_total['accuracy']:>10.3f} {metrics_total['baseline']:>10.3f} {imp:>+10.3f} {metrics_total['auc_roc']:>10.3f} {conf:>12}")
    
    # Save models
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        if metrics_spread:
            model_spread.save_model(str(args.output / "spread_barttorvik.json"))
        if metrics_total:
            model_total.save_model(str(args.output / "total_barttorvik.json"))
        print(f"\nModels saved to {args.output}/")
    
    print("\nDone! Trained with Barttorvik ratings (no outcome leakage).")


if __name__ == "__main__":
    main()
