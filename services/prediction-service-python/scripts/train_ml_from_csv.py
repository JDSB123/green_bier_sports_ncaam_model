#!/usr/bin/env python3
"""
Train ML Models from CSV Files.

This script trains XGBoost models using CSV data files instead of the database.
Useful for training on specific seasons when database doesn't have historical data.

Required CSV Format (combined file):
    game_date,home_team,away_team,home_score,away_score,spread_open,total_open,
    home_adj_o,home_adj_d,home_tempo,home_rank,home_efg,home_efgd,home_tor,home_tord,
    home_orb,home_drb,home_ftr,home_ftrd,home_barthag,home_wab,
    away_adj_o,away_adj_d,away_tempo,away_rank,away_efg,away_efgd,away_tor,away_tord,
    away_orb,away_drb,away_ftr,away_ftrd,away_barthag,away_wab

Usage:
    # Train on historical data, test on 2023-2025
    python scripts/train_ml_from_csv.py --data training_data.csv --test-start 2023-11-01
    
    # With custom train/test split
    python scripts/train_ml_from_csv.py --data training_data.csv --train-end 2022-10-31 --test-start 2023-11-01
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


def load_training_data(csv_path: Path) -> pd.DataFrame:
    """Load and validate training data from CSV."""
    df = pd.read_csv(csv_path)
    
    # Convert date
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Required columns
    required = [
        'game_date', 'home_team', 'away_team', 'home_score', 'away_score',
        'spread_open', 'total_open',
        'home_adj_o', 'home_adj_d', 'home_tempo',
        'away_adj_o', 'away_adj_d', 'away_tempo',
    ]
    
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    return df


def engineer_features(df: pd.DataFrame) -> np.ndarray:
    """
    Engineer features from raw data.
    
    Returns feature matrix with same columns as app/ml/features.py
    """
    features = []
    
    for _, row in df.iterrows():
        # Efficiency features
        home_net = row.get('home_adj_o', 100) - row.get('home_adj_d', 100)
        away_net = row.get('away_adj_o', 100) - row.get('away_adj_d', 100)
        
        f = [
            home_net,  # home_net_efficiency
            away_net,  # away_net_efficiency
            home_net - away_net,  # efficiency_diff
            (row.get('home_tempo', 67.6) + row.get('away_tempo', 67.6)) / 2,  # tempo_avg
            row.get('home_tempo', 67.6) - row.get('away_tempo', 67.6),  # tempo_diff
            row.get('away_rank', 175) - row.get('home_rank', 175),  # rank_diff
            
            # Matchup features
            (row.get('home_adj_o', 100) - 105.5) - (row.get('away_adj_d', 100) - 105.5),  # home_off_vs_away_def
            (row.get('away_adj_o', 100) - 105.5) - (row.get('home_adj_d', 100) - 105.5),  # away_off_vs_home_def
            0.0,  # net_matchup (placeholder)
            
            # Four factors (use defaults if not available)
            row.get('home_efg', 50) - row.get('away_efgd', 50),  # shooting_matchup
            row.get('away_tord', 18.5) - row.get('home_tor', 18.5),  # turnover_matchup
            row.get('home_orb', 28) - row.get('away_drb', 72),  # rebound_matchup
            row.get('home_ftr', 33) - row.get('away_ftrd', 33),  # ftr_matchup
            
            # Style features
            (row.get('home_three_pt_rate', 35) + row.get('away_three_pt_rate', 35)) / 2,  # three_pt_rate_avg
            row.get('home_three_pt_rate', 35) - row.get('away_three_pt_rate', 35),  # three_pt_rate_diff
            ((row.get('home_tempo', 67.6) - 67.6) + (row.get('away_tempo', 67.6) - 67.6)) / 2,  # pace_factor
            
            # Quality features
            row.get('home_barthag', 0.5) - row.get('away_barthag', 0.5),  # barthag_diff
            row.get('home_wab', 0) - row.get('away_wab', 0),  # wab_diff
            row.get('home_barthag', 0.5),  # home_barthag
            row.get('away_barthag', 0.5),  # away_barthag
            
            # Market features
            row.get('spread_open', 0),  # spread_open
            row.get('total_open', 140),  # total_open
            0.0,  # line_movement_spread (not available in CSV)
            0.0,  # line_movement_total
            0.0,  # sharp_square_diff_spread
            0.0,  # sharp_square_diff_total
            
            # Situational features
            float(row.get('is_neutral', 0)),  # is_neutral
            0.0,  # home_rest_advantage (not available)
            0.0,  # home_b2b
            0.0,  # away_b2b
            
            # Public betting (not available)
            0.5,  # public_home_pct
            0.0,  # sharp_indicator_spread
            0.5,  # public_over_pct
            0.0,  # sharp_indicator_total
        ]
        features.append(f)
    
    return np.array(features, dtype=np.float32)


def calculate_labels(df: pd.DataFrame, bet_type: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate labels for each bet type.
    
    Returns: (labels, mask) where mask indicates non-push games
    """
    if bet_type == "fg_spread":
        # Did home cover the spread?
        margin = df['home_score'] - df['away_score']
        spread = df['spread_open']
        cover_margin = margin + spread
        
        labels = (cover_margin > 0).astype(float)
        mask = abs(cover_margin) >= 0.5  # Exclude pushes
        
    elif bet_type == "fg_total":
        # Did game go over?
        total = df['home_score'] + df['away_score']
        total_line = df['total_open']
        
        labels = (total > total_line).astype(float)
        mask = abs(total - total_line) >= 0.5  # Exclude pushes
        
    elif bet_type == "h1_spread":
        if 'home_h1_score' not in df.columns:
            return np.array([]), np.array([])
        
        margin = df['home_h1_score'] - df['away_h1_score']
        spread = df['spread_open'] / 2  # Approximate 1H spread
        cover_margin = margin + spread
        
        labels = (cover_margin > 0).astype(float)
        mask = abs(cover_margin) >= 0.5
        
    elif bet_type == "h1_total":
        if 'home_h1_score' not in df.columns:
            return np.array([]), np.array([])
        
        total = df['home_h1_score'] + df['away_h1_score']
        total_line = df['total_open'] / 2  # Approximate 1H total
        
        labels = (total > total_line).astype(float)
        mask = abs(total - total_line) >= 0.5
    
    else:
        raise ValueError(f"Unknown bet type: {bet_type}")
    
    return labels.values, mask.values


def train_and_evaluate(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    bet_type: str,
) -> Dict:
    """Train XGBoost model and evaluate on test set."""
    
    # XGBoost parameters
    params = {
        "objective": "binary:logistic",
        "max_depth": 4,
        "learning_rate": 0.05,
        "n_estimators": 200,
        "min_child_weight": 10,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
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
        "train_positive_rate": float(y_train.mean()),
        "test_positive_rate": float(y_test.mean()),
        "accuracy": accuracy_score(y_test, y_pred),
        "log_loss": log_loss(y_test, y_pred_proba),
        "auc_roc": roc_auc_score(y_test, y_pred_proba),
        "brier_score": brier_score_loss(y_test, y_pred_proba),
    }
    
    # Feature importance
    feature_names = [
        "home_net_eff", "away_net_eff", "eff_diff", "tempo_avg", "tempo_diff", "rank_diff",
        "home_off_vs_away_def", "away_off_vs_home_def", "net_matchup",
        "shooting_matchup", "turnover_matchup", "rebound_matchup", "ftr_matchup",
        "three_pt_rate_avg", "three_pt_rate_diff", "pace_factor",
        "barthag_diff", "wab_diff", "home_barthag", "away_barthag",
        "spread_open", "total_open", "line_move_spread", "line_move_total",
        "sharp_sq_spread", "sharp_sq_total",
        "is_neutral", "rest_advantage", "home_b2b", "away_b2b",
        "public_home", "sharp_indicator_spread", "public_over", "sharp_indicator_total",
    ]
    
    importance = dict(zip(feature_names, model.feature_importances_.tolist()))
    metrics["feature_importance"] = importance
    
    return metrics, model


def main():
    parser = argparse.ArgumentParser(description="Train ML models from CSV")
    parser.add_argument("--data", type=Path, required=True, help="Training data CSV")
    parser.add_argument("--test-start", type=str, default="2023-11-01", help="Test set start date")
    parser.add_argument("--output", type=Path, default=None, help="Output directory for models")
    parser.add_argument("--bet-type", type=str, default=None, 
                       choices=["fg_spread", "fg_total", "h1_spread", "h1_total"],
                       help="Train specific bet type only")
    
    args = parser.parse_args()
    
    if not HAS_PANDAS:
        print("❌ pandas required: pip install pandas")
        sys.exit(1)
    
    if not HAS_ML:
        print("❌ ML libraries required: pip install xgboost scikit-learn")
        sys.exit(1)
    
    print("=" * 70)
    print("NCAAM ML Training from CSV")
    print("=" * 70)
    
    # Load data
    print(f"\n📂 Loading data from: {args.data}")
    df = load_training_data(args.data)
    print(f"   Loaded {len(df)} games")
    print(f"   Date range: {df['game_date'].min()} to {df['game_date'].max()}")
    
    # Split data
    test_start = pd.to_datetime(args.test_start)
    train_df = df[df['game_date'] < test_start]
    test_df = df[df['game_date'] >= test_start]
    
    print(f"\n📊 Data split:")
    print(f"   Training: {len(train_df)} games (before {args.test_start})")
    print(f"   Testing:  {len(test_df)} games (on or after {args.test_start})")
    
    if len(train_df) < 100:
        print("❌ Not enough training data (need at least 100 games)")
        sys.exit(1)
    
    if len(test_df) < 50:
        print("⚠️ Warning: Small test set ({len(test_df)} games)")
    
    # Engineer features
    print("\n🔧 Engineering features...")
    X_train = engineer_features(train_df)
    X_test = engineer_features(test_df)
    
    # Train models
    bet_types = [args.bet_type] if args.bet_type else ["fg_spread", "fg_total"]
    results = {}
    
    for bet_type in bet_types:
        print(f"\n{'─' * 70}")
        print(f"Training: {bet_type}")
        print(f"{'─' * 70}")
        
        # Get labels
        y_train, mask_train = calculate_labels(train_df, bet_type)
        y_test, mask_test = calculate_labels(test_df, bet_type)
        
        if len(y_train) == 0:
            print(f"   ⚠️ No data available for {bet_type}")
            continue
        
        # Apply mask (exclude pushes)
        X_train_masked = X_train[mask_train]
        y_train_masked = y_train[mask_train]
        X_test_masked = X_test[mask_test]
        y_test_masked = y_test[mask_test]
        
        print(f"   Train: {len(y_train_masked)} games (excl. {(~mask_train).sum()} pushes)")
        print(f"   Test:  {len(y_test_masked)} games (excl. {(~mask_test).sum()} pushes)")
        
        # Train
        metrics, model = train_and_evaluate(
            X_train_masked, y_train_masked,
            X_test_masked, y_test_masked,
            bet_type,
        )
        results[bet_type] = metrics
        
        # Print results
        print(f"\n   Results on TEST SET (2023-2025 seasons):")
        print(f"   {'─' * 50}")
        print(f"   Accuracy:    {metrics['accuracy']:.3f}")
        print(f"   AUC-ROC:     {metrics['auc_roc']:.3f}")
        print(f"   Brier Score: {metrics['brier_score']:.4f}")
        print(f"   Log Loss:    {metrics['log_loss']:.4f}")
        
        # Baseline comparison
        baseline = max(metrics['test_positive_rate'], 1 - metrics['test_positive_rate'])
        improvement = metrics['accuracy'] - baseline
        print(f"\n   Baseline (always pick majority): {baseline:.3f}")
        print(f"   Improvement over baseline:        {improvement:+.3f}")
        
        # Top features
        print(f"\n   Top 5 features:")
        sorted_feat = sorted(metrics['feature_importance'].items(), key=lambda x: x[1], reverse=True)[:5]
        for name, imp in sorted_feat:
            print(f"     - {name}: {imp:.3f}")
        
        # Save model if output specified
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            model_path = args.output / f"{bet_type}_model.json"
            model.save_model(str(model_path))
            print(f"\n   💾 Model saved to: {model_path}")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n{'Bet Type':<15} {'Accuracy':>10} {'AUC-ROC':>10} {'Brier':>10}")
    print(f"{'─' * 50}")
    for bet_type, metrics in results.items():
        print(f"{bet_type:<15} {metrics['accuracy']:>10.3f} {metrics['auc_roc']:>10.3f} {metrics['brier_score']:>10.4f}")
    
    print("\n✅ Training complete!")


if __name__ == "__main__":
    main()
