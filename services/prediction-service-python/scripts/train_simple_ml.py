#!/usr/bin/env python3
"""
Simple ML Training for NCAAM Predictions.

This trains a simplified model using only market-based features:
- Opening spread/total line
- Home/away team strength proxy (margin of victory patterns)

Features are derived purely from betting lines and outcomes, without
requiring full Barttorvik ratings. This is useful for:
1. Testing the ML pipeline
2. Establishing a baseline
3. Training when historical ratings are unavailable

Usage:
    python scripts/train_simple_ml.py --data training_data/games_2023_2025.csv
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
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
    from sklearn.model_selection import TimeSeriesSplit
    HAS_ML = True
except ImportError:
    HAS_ML = False


def load_games(csv_path: Path) -> pd.DataFrame:
    """Load and prepare games data."""
    df = pd.read_csv(csv_path)
    
    # Convert date
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Calculate derived fields
    df['margin'] = df['home_score'] - df['away_score']  # Positive = home win
    df['total_points'] = df['home_score'] + df['away_score']
    
    # Parse spread/total (handle None/NaN)
    df['spread_open'] = pd.to_numeric(df['spread_open'], errors='coerce')
    df['total_open'] = pd.to_numeric(df['total_open'], errors='coerce')
    
    return df


def calculate_team_strength(df: pd.DataFrame, margin_col: str = 'margin') -> Dict[str, float]:
    """
    Calculate team strength proxy from historical performance.
    Uses average margin as proxy for team quality.
    
    Note: This uses all data which creates some leakage.
    In production, use rolling window.
    """
    # For home teams, use margin directly. For away teams, negate it.
    team_margins = {}
    team_counts = {}
    
    for _, row in df.iterrows():
        home = row['home_team']
        away = row['away_team']
        margin = row[margin_col]
        
        team_margins[home] = team_margins.get(home, 0) + margin
        team_counts[home] = team_counts.get(home, 0) + 1
        
        team_margins[away] = team_margins.get(away, 0) - margin  # Negative for away
        team_counts[away] = team_counts.get(away, 0) + 1
    
    # Calculate average margin per team
    strengths = {}
    for team, total_margin in team_margins.items():
        count = team_counts[team]
        strengths[team] = total_margin / count if count > 0 else 0.0
    
    return strengths


def engineer_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Engineer features for ML model.
    
    Returns: (features, spread_labels, total_labels)
    """
    # Calculate team strengths (using all data for simplicity)
    strengths = calculate_team_strength(df)
    
    features = []
    spread_labels = []
    total_labels = []
    valid_mask = []
    
    for _, row in df.iterrows():
        home = row['home_team']
        away = row['away_team']
        
        home_strength = strengths.get(home, 0)
        away_strength = strengths.get(away, 0)
        
        spread = row.get('spread_open')
        total = row.get('total_open')
        margin = row['margin']
        total_pts = row['total_points']
        
        # Skip if no spread line
        if pd.isna(spread):
            spread = -(home_strength - away_strength)  # Estimate from strength
        
        if pd.isna(total):
            total = 140.0  # League average
        
        # Features
        f = [
            home_strength,  # Home team average margin
            away_strength,  # Away team average margin
            home_strength - away_strength,  # Strength differential
            spread,  # Opening spread (home perspective, negative = favorite)
            total,  # Opening total
            abs(spread),  # Spread magnitude (game closeness)
            1 if spread < 0 else 0,  # Is home favorite?
            total - 140,  # Total deviation from average
        ]
        features.append(f)
        
        # Labels
        # Spread: Did home cover? (margin + spread > 0)
        cover_margin = margin + spread
        if abs(cover_margin) < 0.5:  # Push
            spread_labels.append(-1)  # Mark as push
        else:
            spread_labels.append(1 if cover_margin > 0 else 0)
        
        # Total: Did game go over?
        total_margin = total_pts - total
        if abs(total_margin) < 0.5:  # Push
            total_labels.append(-1)
        else:
            total_labels.append(1 if total_margin > 0 else 0)
    
    return np.array(features, dtype=np.float32), np.array(spread_labels), np.array(total_labels)


def train_and_evaluate(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    bet_type: str,
) -> Tuple[Dict, object]:
    """Train XGBoost model and evaluate."""
    
    # XGBoost parameters - conservative for small datasets
    params = {
        "objective": "binary:logistic",
        "max_depth": 3,  # Shallow to avoid overfitting
        "learning_rate": 0.1,
        "n_estimators": 100,
        "min_child_weight": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.5,
        "reg_lambda": 2.0,
        "random_state": 42,
    }
    
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, verbose=False)
    
    # Predictions
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    # Metrics
    metrics = {
        "bet_type": bet_type,
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "accuracy": accuracy_score(y_test, y_pred),
        "auc_roc": roc_auc_score(y_test, y_pred_proba),
        "brier_score": brier_score_loss(y_test, y_pred_proba),
        "log_loss": log_loss(y_test, y_pred_proba),
        "baseline": max(y_test.mean(), 1 - y_test.mean()),
    }
    
    return metrics, model


def main():
    parser = argparse.ArgumentParser(description="Train simple ML models")
    parser.add_argument("--data", type=Path, required=True, help="Games CSV file")
    parser.add_argument("--test-start", type=str, default="2024-11-01", help="Test set start date")
    parser.add_argument("--output", type=Path, default=None, help="Model output directory")
    
    args = parser.parse_args()
    
    if not HAS_PANDAS:
        print("Error: pandas required")
        sys.exit(1)
    
    if not HAS_ML:
        print("Error: xgboost and scikit-learn required")
        sys.exit(1)
    
    print("=" * 70)
    print("Simple ML Training for NCAAM")
    print("=" * 70)
    
    # Load data
    print(f"\nLoading data from {args.data}...")
    df = load_games(args.data)
    print(f"Loaded {len(df)} games")
    print(f"Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    
    # Filter to games with outcomes
    df = df[(df['home_score'] > 0) | (df['away_score'] > 0)]
    print(f"Games with scores: {len(df)}")
    
    # Engineer features
    print("\nEngineering features...")
    X, y_spread, y_total = engineer_features(df)
    
    # Split by date
    test_start = pd.to_datetime(args.test_start)
    train_mask = df['game_date'] < test_start
    test_mask = df['game_date'] >= test_start
    
    X_train_all = X[train_mask]
    X_test_all = X[test_mask]
    
    y_spread_train_all = y_spread[train_mask]
    y_spread_test_all = y_spread[test_mask]
    
    y_total_train_all = y_total[train_mask]
    y_total_test_all = y_total[test_mask]
    
    print(f"\nData split (test from {args.test_start}):")
    print(f"  Training: {len(X_train_all)} games")
    print(f"  Testing:  {len(X_test_all)} games")
    
    # Train spread model
    print("\n" + "=" * 70)
    print("SPREAD MODEL")
    print("=" * 70)
    
    # Exclude pushes
    train_mask_spread = y_spread_train_all >= 0
    test_mask_spread = y_spread_test_all >= 0
    
    X_train = X_train_all[train_mask_spread]
    y_train = y_spread_train_all[train_mask_spread]
    X_test = X_test_all[test_mask_spread]
    y_test = y_spread_test_all[test_mask_spread]
    
    print(f"Non-push games: {len(y_train)} train, {len(y_test)} test")
    
    if len(y_train) > 100 and len(y_test) > 50:
        metrics_spread, model_spread = train_and_evaluate(X_train, y_train, X_test, y_test, "spread")
        
        print(f"\n  Results:")
        print(f"  - Accuracy:    {metrics_spread['accuracy']:.3f} (baseline: {metrics_spread['baseline']:.3f})")
        print(f"  - AUC-ROC:     {metrics_spread['auc_roc']:.3f}")
        print(f"  - Brier Score: {metrics_spread['brier_score']:.4f}")
        print(f"  - Improvement: {metrics_spread['accuracy'] - metrics_spread['baseline']:+.3f}")
        
        # Feature importance
        feature_names = ['home_strength', 'away_strength', 'strength_diff', 
                        'spread', 'total', 'spread_mag', 'home_fav', 'total_dev']
        print("\n  Feature Importance:")
        for name, imp in zip(feature_names, model_spread.feature_importances_):
            if imp > 0.05:
                print(f"    - {name}: {imp:.3f}")
    else:
        print("  Not enough data for spread model")
        metrics_spread = None
    
    # Train total model
    print("\n" + "=" * 70)
    print("TOTAL MODEL")
    print("=" * 70)
    
    train_mask_total = y_total_train_all >= 0
    test_mask_total = y_total_test_all >= 0
    
    X_train = X_train_all[train_mask_total]
    y_train = y_total_train_all[train_mask_total]
    X_test = X_test_all[test_mask_total]
    y_test = y_total_test_all[test_mask_total]
    
    print(f"Non-push games: {len(y_train)} train, {len(y_test)} test")
    
    if len(y_train) > 100 and len(y_test) > 50:
        metrics_total, model_total = train_and_evaluate(X_train, y_train, X_test, y_test, "total")
        
        print(f"\n  Results:")
        print(f"  - Accuracy:    {metrics_total['accuracy']:.3f} (baseline: {metrics_total['baseline']:.3f})")
        print(f"  - AUC-ROC:     {metrics_total['auc_roc']:.3f}")
        print(f"  - Brier Score: {metrics_total['brier_score']:.4f}")
        print(f"  - Improvement: {metrics_total['accuracy'] - metrics_total['baseline']:+.3f}")
        
        print("\n  Feature Importance:")
        for name, imp in zip(feature_names, model_total.feature_importances_):
            if imp > 0.05:
                print(f"    - {name}: {imp:.3f}")
    else:
        print("  Not enough data for total model")
        metrics_total = None
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\n{'Model':<15} {'Accuracy':>10} {'Baseline':>10} {'Improve':>10} {'AUC':>10}")
    print("-" * 60)
    
    if metrics_spread:
        imp = metrics_spread['accuracy'] - metrics_spread['baseline']
        print(f"{'Spread':<15} {metrics_spread['accuracy']:>10.3f} {metrics_spread['baseline']:>10.3f} {imp:>+10.3f} {metrics_spread['auc_roc']:>10.3f}")
    
    if metrics_total:
        imp = metrics_total['accuracy'] - metrics_total['baseline']
        print(f"{'Total':<15} {metrics_total['accuracy']:>10.3f} {metrics_total['baseline']:>10.3f} {imp:>+10.3f} {metrics_total['auc_roc']:>10.3f}")
    
    # Save models if requested
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        if metrics_spread:
            model_spread.save_model(str(args.output / "spread_simple.json"))
        if metrics_total:
            model_total.save_model(str(args.output / "total_simple.json"))
        print(f"\nModels saved to {args.output}/")
    
    print("\nDone!")
    print("\nNote: This is a simplified model using only market features.")
    print("For better performance, add Barttorvik ratings features.")


if __name__ == "__main__":
    main()
