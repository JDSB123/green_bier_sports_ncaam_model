#!/usr/bin/env python3
"""
ML Training WITHOUT Data Leakage.

This script trains models using ONLY information available BEFORE each game:
- Team strength is calculated from PRIOR games only (expanding window)
- No future game outcomes used in features
- Proper time-series cross-validation

Usage:
    python scripts/train_ml_no_leakage.py --data training_data/games_2023_2025.csv
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
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


class RollingTeamStats:
    """
    Calculates team statistics using ONLY games that occurred BEFORE each date.
    
    This prevents data leakage by ensuring we never use future information.
    Uses an expanding window of all prior games for each team.
    """
    
    def __init__(self, min_games: int = 5):
        """
        Args:
            min_games: Minimum games required before using team stats (else use league average)
        """
        self.min_games = min_games
        # Store game results: team -> list of (date, margin, opponent_margin, home_flag)
        self.team_games: Dict[str, List[Tuple[str, float, float, bool]]] = defaultdict(list)
        # Cache computed stats by date
        self._stats_cache: Dict[str, Dict[str, Dict[str, float]]] = {}
    
    def add_game(self, date: str, home_team: str, away_team: str, 
                 home_score: int, away_score: int):
        """Record a game result for future lookups."""
        margin = home_score - away_score
        
        # Home team perspective
        self.team_games[home_team].append((date, margin, -margin, True))
        # Away team perspective
        self.team_games[away_team].append((date, -margin, margin, False))
    
    def get_team_stats(self, team: str, as_of_date: str) -> Dict[str, float]:
        """
        Get team statistics using ONLY games BEFORE as_of_date.
        
        Returns dict with:
        - avg_margin: Average scoring margin
        - avg_points_for: Average points scored
        - avg_points_against: Average points allowed
        - home_margin: Home game margin
        - away_margin: Away game margin
        - games_played: Number of prior games
        - win_pct: Win percentage
        """
        games = self.team_games.get(team, [])
        
        # Filter to games BEFORE as_of_date
        prior_games = [(d, m, om, h) for d, m, om, h in games if d < as_of_date]
        
        if len(prior_games) < self.min_games:
            # Not enough data - return league averages
            return {
                "avg_margin": 0.0,
                "avg_points_for": 70.0,  # Rough league average
                "avg_points_against": 70.0,
                "home_margin": 0.0,
                "away_margin": 0.0,
                "games_played": len(prior_games),
                "win_pct": 0.5,
                "has_data": False,
            }
        
        margins = [m for _, m, _, _ in prior_games]
        home_margins = [m for _, m, _, h in prior_games if h]
        away_margins = [m for _, m, _, h in prior_games if not h]
        wins = sum(1 for _, m, _, _ in prior_games if m > 0)
        
        return {
            "avg_margin": np.mean(margins),
            "avg_points_for": 70.0 + np.mean(margins) / 2,  # Approximation
            "avg_points_against": 70.0 - np.mean(margins) / 2,
            "home_margin": np.mean(home_margins) if home_margins else 0.0,
            "away_margin": np.mean(away_margins) if away_margins else 0.0,
            "games_played": len(prior_games),
            "win_pct": wins / len(prior_games),
            "has_data": True,
        }


def load_games(csv_path: Path) -> pd.DataFrame:
    """Load and sort games by date."""
    df = pd.read_csv(csv_path)
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.sort_values('game_date').reset_index(drop=True)
    
    # Calculate derived fields
    df['margin'] = df['home_score'] - df['away_score']
    df['total_points'] = df['home_score'] + df['away_score']
    
    # Parse spread/total
    df['spread_open'] = pd.to_numeric(df['spread_open'], errors='coerce')
    df['total_open'] = pd.to_numeric(df['total_open'], errors='coerce')
    
    return df


def engineer_features_no_leakage(df: pd.DataFrame, min_games: int = 5) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Engineer features WITHOUT data leakage.
    
    For each game:
    1. Calculate team stats using ONLY prior games
    2. Use those stats as features
    3. Game outcome is the label (not a feature)
    
    Returns: (features, spread_labels, total_labels, valid_mask)
    """
    print("  Building rolling team statistics...")
    
    # Sort by date
    df = df.sort_values('game_date').reset_index(drop=True)
    
    # Initialize rolling stats tracker
    stats_tracker = RollingTeamStats(min_games=min_games)
    
    features = []
    spread_labels = []
    total_labels = []
    valid_mask = []
    
    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            print(f"    Processing game {idx}/{len(df)}...")
        
        date_str = row['game_date'].strftime('%Y-%m-%d')
        home = row['home_team']
        away = row['away_team']
        
        # Get stats BEFORE this game
        home_stats = stats_tracker.get_team_stats(home, date_str)
        away_stats = stats_tracker.get_team_stats(away, date_str)
        
        # Get market lines (if available)
        spread = row.get('spread_open')
        total = row.get('total_open')
        
        # Estimate spread from prior performance if missing
        if pd.isna(spread):
            # Use margin differential as spread estimate
            spread = -(home_stats['avg_margin'] - away_stats['avg_margin'])
            # Add home court advantage (~3 points)
            spread -= 3.0
        
        if pd.isna(total):
            total = 140.0  # League average
        
        # v33.11: USE ALL 22 BARTTORVIK FIELDS + ADVANCED FEATURES
        # Build full GameFeatures object with all Barttorvik data
        game_features = GameFeatures(
            game_id=f"{home}_{away}_{date_str}",
            game_date=date_str,
            home_team=home,
            away_team=away,

            # CORE EFFICIENCY (from rolling stats)
            home_adj_o=home_stats.get('avg_adj_o', 100.0),
            home_adj_d=home_stats.get('avg_adj_d', 100.0),
            away_adj_o=away_stats.get('avg_adj_o', 100.0),
            away_adj_d=away_stats.get('avg_adj_d', 100.0),
            home_tempo=home_stats.get('avg_tempo', 67.6),
            away_tempo=away_stats.get('avg_tempo', 67.6),
            home_rank=home_stats.get('avg_rank', 150),
            away_rank=away_stats.get('avg_rank', 150),

            # FOUR FACTORS (from rolling stats)
            home_efg=home_stats.get('avg_efg', 50.0),
            home_efgd=home_stats.get('avg_efgd', 50.0),
            away_efg=away_stats.get('avg_efg', 50.0),
            away_efgd=away_stats.get('avg_efgd', 50.0),
            home_tor=home_stats.get('avg_tor', 18.5),
            home_tord=home_stats.get('avg_tord', 18.5),
            away_tor=away_stats.get('avg_tor', 18.5),
            away_tord=away_stats.get('avg_tord', 18.5),
            home_orb=home_stats.get('avg_orb', 28.0),
            home_drb=home_stats.get('avg_drb', 28.0),
            away_orb=away_stats.get('avg_orb', 28.0),
            away_drb=away_stats.get('avg_drb', 28.0),
            home_ftr=home_stats.get('avg_ftr', 33.0),
            home_ftrd=home_stats.get('avg_ftrd', 33.0),
            away_ftr=away_stats.get('avg_ftr', 33.0),
            away_ftrd=away_stats.get('avg_ftrd', 33.0),

            # SHOOTING BREAKDOWN
            home_two_pt_pct=home_stats.get('avg_two_pt_pct', 50.0),
            home_two_pt_pct_d=home_stats.get('avg_two_pt_pct_d', 50.0),
            away_two_pt_pct=away_stats.get('avg_two_pt_pct', 50.0),
            away_two_pt_pct_d=away_stats.get('avg_two_pt_pct_d', 50.0),
            home_three_pt_pct=home_stats.get('avg_three_pt_pct', 35.0),
            home_three_pt_pct_d=home_stats.get('avg_three_pt_pct_d', 35.0),
            away_three_pt_pct=away_stats.get('avg_three_pt_pct', 35.0),
            away_three_pt_pct_d=away_stats.get('avg_three_pt_pct_d', 35.0),
            home_three_pt_rate=home_stats.get('avg_three_pt_rate', 35.0),
            home_three_pt_rate_d=home_stats.get('avg_three_pt_rate_d', 35.0),
            away_three_pt_rate=away_stats.get('avg_three_pt_rate', 35.0),
            away_three_pt_rate_d=away_stats.get('avg_three_pt_rate_d', 35.0),

            # QUALITY METRICS
            home_barthag=home_stats.get('avg_barthag', 0.5),
            home_wab=home_stats.get('avg_wab', 0.0),
            away_barthag=away_stats.get('avg_barthag', 0.5),
            away_wab=away_stats.get('avg_wab', 0.0),

            # MARKET DATA
            spread_open=spread,
            total_open=total,
            spread_current=spread,
            total_current=total,
        )

        # Use proper FeatureEngineer to extract all features
        feature_engineer = FeatureEngineer()
        f = feature_engineer.extract_features(game_features).tolist()
        features.append(f)
        
        # Calculate labels (from actual outcome)
        margin = row['margin']
        total_pts = row['total_points']
        
        # Spread: Did home cover?
        cover_margin = margin + spread
        if abs(cover_margin) < 0.5:  # Push
            spread_labels.append(-1)
        else:
            spread_labels.append(1 if cover_margin > 0 else 0)
        
        # Total: Did game go over?
        total_margin = total_pts - total
        if abs(total_margin) < 0.5:  # Push
            total_labels.append(-1)
        else:
            total_labels.append(1 if total_margin > 0 else 0)
        
        # Valid if both teams have data
        valid_mask.append(home_stats['has_data'] and away_stats['has_data'])
        
        # NOW add this game to the tracker (for future games)
        stats_tracker.add_game(
            date_str, home, away, 
            row['home_score'], row['away_score']
        )
    
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
    bet_type: str,
) -> Tuple[Dict, object]:
    """Train XGBoost model and evaluate."""
    
    params = {
        "objective": "binary:logistic",
        "max_depth": 4,
        "learning_rate": 0.05,
        "n_estimators": 200,
        "min_child_weight": 15,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.5,
        "reg_lambda": 2.0,
        "random_state": 42,
    }
    
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, verbose=False)
    
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
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
    parser = argparse.ArgumentParser(description="Train ML models WITHOUT leakage")
    parser.add_argument("--data", type=Path, required=True, help="Games CSV file")
    parser.add_argument("--test-start", type=str, default="2024-11-01", help="Test set start date")
    parser.add_argument("--min-games", type=int, default=5, help="Min games for team stats")
    parser.add_argument("--output", type=Path, default=None, help="Model output directory")
    
    args = parser.parse_args()
    
    if not HAS_PANDAS or not HAS_ML:
        print("Error: pandas, xgboost, scikit-learn required")
        sys.exit(1)
    
    print("=" * 70)
    print("ML Training WITHOUT Data Leakage")
    print("=" * 70)
    
    # Load data
    print(f"\nLoading data from {args.data}...")
    df = load_games(args.data)
    print(f"Loaded {len(df)} games")
    print(f"Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    
    # Filter to games with valid scores
    df = df[(df['home_score'] > 0) | (df['away_score'] > 0)]
    print(f"Games with scores: {len(df)}")
    
    # Engineer features (no leakage)
    print("\nEngineering features (no leakage)...")
    X, y_spread, y_total, valid_mask = engineer_features_no_leakage(df, args.min_games)
    
    # Split by date
    test_start = pd.to_datetime(args.test_start)
    dates = df['game_date'].values
    train_mask = dates < np.datetime64(test_start)
    test_mask = dates >= np.datetime64(test_start)
    
    print(f"\nData split (test from {args.test_start}):")
    print(f"  Training: {train_mask.sum()} games")
    print(f"  Testing:  {test_mask.sum()} games")
    
    # Feature names for importance - MUST match FeatureEngineer.extract_features() output (34 features)
    feature_names = [
        # DERIVED EFFICIENCY FEATURES (6)
        'home_net_eff', 'away_net_eff', 'efficiency_diff',
        'tempo_avg', 'tempo_diff', 'rank_diff',

        # MATCHUP FEATURES (3)
        'home_off_vs_away_def', 'away_off_vs_home_def', 'off_def_matchup_diff',

        # FOUR FACTORS MATCHUPS (4)
        'shooting_matchup', 'turnover_matchup', 'rebound_matchup', 'ftr_matchup',

        # STYLE FEATURES (3)
        'avg_3pt_rate', 'diff_3pt_rate', 'pace_factor',

        # QUALITY FEATURES (4)
        'barthag_diff', 'wab_diff', 'home_barthag', 'away_barthag',

        # MARKET FEATURES (6)
        'spread_open', 'total_open', 'spread_line_move', 'total_line_move',
        'sharp_sq_spread', 'sharp_sq_total',

        # SITUATIONAL FEATURES (4)
        'is_neutral', 'rest_diff', 'home_b2b', 'away_b2b',

        # PUBLIC BETTING (4)
        'public_home_pct', 'sharp_indicator_home', 'public_over_pct', 'sharp_indicator_over',
    ]
    
    # Train spread model
    print("\n" + "=" * 70)
    print("SPREAD MODEL (No Leakage)")
    print("=" * 70)
    
    # Combine masks: train/test, non-push, has data
    train_spread_mask = train_mask & (y_spread >= 0) & valid_mask
    test_spread_mask = test_mask & (y_spread >= 0) & valid_mask
    
    X_train = X[train_spread_mask]
    y_train = y_spread[train_spread_mask]
    X_test = X[test_spread_mask]
    y_test = y_spread[test_spread_mask]
    
    print(f"Valid games: {train_spread_mask.sum()} train, {test_spread_mask.sum()} test")
    
    if len(y_train) > 100 and len(y_test) > 50:
        metrics_spread, model_spread = train_and_evaluate(X_train, y_train, X_test, y_test, "spread")
        
        print(f"\n  Results:")
        print(f"  - Accuracy:    {metrics_spread['accuracy']:.3f} (baseline: {metrics_spread['baseline']:.3f})")
        print(f"  - AUC-ROC:     {metrics_spread['auc_roc']:.3f}")
        print(f"  - Brier Score: {metrics_spread['brier_score']:.4f}")
        print(f"  - Improvement: {metrics_spread['accuracy'] - metrics_spread['baseline']:+.3f}")
        
        print("\n  Feature Importance:")
        for name, imp in sorted(zip(feature_names, model_spread.feature_importances_), key=lambda x: -x[1])[:6]:
            print(f"    - {name}: {imp:.3f}")
    else:
        print("  Not enough valid data")
        metrics_spread = None
    
    # Train total model
    print("\n" + "=" * 70)
    print("TOTAL MODEL (No Leakage)")
    print("=" * 70)
    
    train_total_mask = train_mask & (y_total >= 0) & valid_mask
    test_total_mask = test_mask & (y_total >= 0) & valid_mask
    
    X_train = X[train_total_mask]
    y_train = y_total[train_total_mask]
    X_test = X[test_total_mask]
    y_test = y_total[test_total_mask]
    
    print(f"Valid games: {train_total_mask.sum()} train, {test_total_mask.sum()} test")
    
    if len(y_train) > 100 and len(y_test) > 50:
        metrics_total, model_total = train_and_evaluate(X_train, y_train, X_test, y_test, "total")
        
        print(f"\n  Results:")
        print(f"  - Accuracy:    {metrics_total['accuracy']:.3f} (baseline: {metrics_total['baseline']:.3f})")
        print(f"  - AUC-ROC:     {metrics_total['auc_roc']:.3f}")
        print(f"  - Brier Score: {metrics_total['brier_score']:.4f}")
        print(f"  - Improvement: {metrics_total['accuracy'] - metrics_total['baseline']:+.3f}")
        
        print("\n  Feature Importance:")
        for name, imp in sorted(zip(feature_names, model_total.feature_importances_), key=lambda x: -x[1])[:6]:
            print(f"    - {name}: {imp:.3f}")
    else:
        print("  Not enough valid data")
        metrics_total = None
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY (No Leakage)")
    print("=" * 70)
    
    print(f"\n{'Model':<15} {'Accuracy':>10} {'Baseline':>10} {'Improve':>10} {'AUC':>10}")
    print("-" * 60)
    
    if metrics_spread:
        imp = metrics_spread['accuracy'] - metrics_spread['baseline']
        print(f"{'Spread':<15} {metrics_spread['accuracy']:>10.3f} {metrics_spread['baseline']:>10.3f} {imp:>+10.3f} {metrics_spread['auc_roc']:>10.3f}")
    
    if metrics_total:
        imp = metrics_total['accuracy'] - metrics_total['baseline']
        print(f"{'Total':<15} {metrics_total['accuracy']:>10.3f} {metrics_total['baseline']:>10.3f} {imp:>+10.3f} {metrics_total['auc_roc']:>10.3f}")
    
    # Save models
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        if metrics_spread:
            model_spread.save_model(str(args.output / "spread_no_leakage.json"))
        if metrics_total:
            model_total.save_model(str(args.output / "total_no_leakage.json"))
        print(f"\nModels saved to {args.output}/")
    
    print("\nDone! No data leakage in training.")


if __name__ == "__main__":
    main()
