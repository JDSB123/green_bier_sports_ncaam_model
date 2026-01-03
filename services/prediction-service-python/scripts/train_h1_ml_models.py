#!/usr/bin/env python3
"""
Train 1st Half ML Models using historical 1H odds and scores.

This script trains two models:
1. h1_spread: Predict home team covering 1H spread
2. h1_total: Predict 1H over hitting

Features include:
- Full game spread/total relationship to 1H lines
- Team matchup context from Barttorvik ratings
- Line value indicators

Usage:
    python scripts/train_h1_ml_models.py
    python scripts/train_h1_ml_models.py --data training_data/h1_training_data.csv
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss
from sklearn.model_selection import TimeSeriesSplit

try:
    import xgboost as xgb
except ImportError:
    print("[ERROR] xgboost required: pip install xgboost")
    sys.exit(1)


def load_barttorvik_ratings(filepath: Path) -> Dict:
    """Load Barttorvik ratings lookup."""
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        return json.load(f)


def load_team_aliases(filepath: Path) -> Dict[str, str]:
    """Load team aliases from export."""
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        return json.load(f)


def normalize_for_lookup(name: str, aliases: Dict[str, str]) -> str:
    """Normalize team name for Barttorvik lookup."""
    if not name:
        return ""
    
    key = name.lower().strip()
    
    # Try alias lookup first
    if key in aliases:
        canonical = aliases[key].lower().strip()
        # Normalize for Barttorvik format
        canonical = canonical.replace("state", "st").replace(".", "").strip()
        return canonical
    
    # Basic normalization
    key = key.replace("state", "st").replace(".", "").strip()
    return key


def get_team_ratings(team_name: str, season: str, ratings: Dict, aliases: Dict) -> Optional[Dict]:
    """Get Barttorvik ratings for a team in a season."""
    normalized = normalize_for_lookup(team_name, aliases)
    
    if not normalized:
        return None
    
    # Try exact key
    key = f"{normalized}_{season}"
    if key in ratings:
        return ratings[key]
    
    # Try variations
    variations = [
        normalized,
        normalized.replace(" st", " state"),
        normalized.replace("st ", "state "),
    ]
    
    for var in variations:
        key = f"{var}_{season}"
        if key in ratings:
            return ratings[key]
    
    return None


def load_training_data(filepath: Path) -> pd.DataFrame:
    """Load 1H training data CSV."""
    df = pd.read_csv(filepath)
    
    # Parse date
    df["date"] = pd.to_datetime(df["date"])
    
    # Sort by date for time-series split
    df = df.sort_values("date").reset_index(drop=True)
    
    print(f"Loaded {len(df)} games from {df['date'].min()} to {df['date'].max()}")
    
    return df


def build_h1_features(df: pd.DataFrame, ratings: Dict = None, aliases: Dict = None) -> pd.DataFrame:
    """
    Build features for 1H prediction.
    
    Features are designed to NOT use future information.
    Includes Barttorvik team ratings when available.
    """
    features = pd.DataFrame(index=df.index)
    
    if ratings is None:
        ratings = {}
    if aliases is None:
        aliases = {}
    
    # 1. Line-based features (available at prediction time)
    features["h1_spread"] = df["h1_spread"].astype(float)
    features["h1_total"] = df["h1_total"].astype(float)
    features["fg_spread"] = df["fg_spread"].astype(float)
    features["fg_total"] = df["fg_total"].astype(float)
    
    # 2. Relationship between 1H and FG lines
    features["h1_to_fg_spread_ratio"] = features["h1_spread"] / features["fg_spread"].replace(0, np.nan)
    features["h1_to_fg_total_ratio"] = features["h1_total"] / features["fg_total"].replace(0, np.nan)
    
    # Expected 1H total ratio (typically ~48% of FG total)
    features["expected_h1_total"] = features["fg_total"] * 0.48
    features["h1_total_deviation"] = features["h1_total"] - features["expected_h1_total"]
    
    # Expected 1H spread (typically ~50% of FG spread)
    features["expected_h1_spread"] = features["fg_spread"] * 0.50
    features["h1_spread_deviation"] = features["h1_spread"] - features["expected_h1_spread"]
    
    # 3. Categorical features
    features["is_home_favorite_fg"] = (features["fg_spread"] < 0).astype(int)
    features["is_home_favorite_h1"] = (features["h1_spread"] < 0).astype(int)
    features["favorite_flip"] = (features["is_home_favorite_fg"] != features["is_home_favorite_h1"]).astype(int)
    
    # 4. Line magnitude features
    features["abs_fg_spread"] = features["fg_spread"].abs()
    features["abs_h1_spread"] = features["h1_spread"].abs()
    features["fg_total_level"] = pd.cut(
        features["fg_total"],
        bins=[0, 130, 145, 160, 200],
        labels=[0, 1, 2, 3]
    ).astype(float)
    
    # 5. Date features (seasonality)
    features["month"] = df["date"].dt.month
    features["is_march"] = (features["month"] == 3).astype(int)  # Tournament month
    features["is_conference_season"] = ((features["month"] >= 1) & (features["month"] <= 3)).astype(int)
    
    # 6. Day of week (weekends have more casual bettors)
    features["day_of_week"] = df["date"].dt.dayofweek
    features["is_weekend"] = (features["day_of_week"] >= 5).astype(int)
    
    # 7. Barttorvik team strength features (if available)
    if ratings:
        home_adjoe = []
        home_adjde = []
        away_adjoe = []
        away_adjde = []
        home_tempo = []
        away_tempo = []
        
        for idx, row in df.iterrows():
            home = row.get("home_team", "")
            away = row.get("away_team", "")
            game_date = row.get("date")
            
            # Determine season (e.g., 2024-01 -> "2024", 2024-11 -> "2025")
            if game_date:
                month = game_date.month
                year = game_date.year
                season = str(year + 1) if month >= 10 else str(year)
            else:
                season = "2024"
            
            home_r = get_team_ratings(home, season, ratings, aliases)
            away_r = get_team_ratings(away, season, ratings, aliases)
            
            home_adjoe.append(home_r.get("adjoe", 100.0) if home_r else 100.0)
            home_adjde.append(home_r.get("adjde", 100.0) if home_r else 100.0)
            away_adjoe.append(away_r.get("adjoe", 100.0) if away_r else 100.0)
            away_adjde.append(away_r.get("adjde", 100.0) if away_r else 100.0)
            home_tempo.append(home_r.get("adj_tempo", 68.0) if home_r else 68.0)
            away_tempo.append(away_r.get("adj_tempo", 68.0) if away_r else 68.0)
        
        features["home_adjoe"] = home_adjoe
        features["home_adjde"] = home_adjde
        features["away_adjoe"] = away_adjoe
        features["away_adjde"] = away_adjde
        features["home_tempo"] = home_tempo
        features["away_tempo"] = away_tempo
        
        # Derived features
        features["home_net_rating"] = features["home_adjoe"] - features["home_adjde"]
        features["away_net_rating"] = features["away_adjoe"] - features["away_adjde"]
        features["rating_diff"] = features["home_net_rating"] - features["away_net_rating"]
        features["avg_tempo"] = (features["home_tempo"] + features["away_tempo"]) / 2
        features["tempo_diff"] = features["home_tempo"] - features["away_tempo"]
        
        # Expected total based on ratings
        features["expected_fg_total"] = (
            features["home_adjoe"] * features["away_adjde"] / 100 +
            features["away_adjoe"] * features["home_adjde"] / 100
        ) * features["avg_tempo"] / 68  # Tempo adjustment
        
        features["market_total_vs_expected"] = features["fg_total"] - features["expected_fg_total"]
    
    # Fill NaN values
    features = features.fillna(0)
    
    return features


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    model_type: str,
) -> xgb.XGBClassifier:
    """Train XGBoost classifier."""
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="logloss",
        early_stopping_rounds=10,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    
    return model


def evaluate_model(
    model: xgb.XGBClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_name: str,
) -> Dict[str, float]:
    """Evaluate model performance."""
    probs = model.predict_proba(X_test)[:, 1]
    preds = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, preds)
    
    try:
        auc = roc_auc_score(y_test, probs)
    except ValueError:
        auc = 0.5
    
    try:
        logloss = log_loss(y_test, probs)
    except ValueError:
        logloss = 1.0
    
    print(f"\n{model_name} Results:")
    print(f"  Accuracy: {accuracy:.1%}")
    print(f"  AUC: {auc:.3f}")
    print(f"  Log Loss: {logloss:.3f}")
    print(f"  Samples: {len(y_test)}")
    
    # Baseline comparison
    baseline = max(y_test.mean(), 1 - y_test.mean())
    print(f"  Baseline (always majority): {baseline:.1%}")
    print(f"  Improvement: {accuracy - baseline:+.1%}")
    
    return {"accuracy": accuracy, "auc": auc, "logloss": logloss}


def main():
    parser = argparse.ArgumentParser(description="Train 1H ML models")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).parent.parent / "training_data" / "h1_training_data.csv",
        help="Path to 1H training data CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "models",
        help="Directory to save trained models",
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("1st Half ML Model Training")
    print("=" * 70)
    
    if not args.data.exists():
        print(f"[ERROR] Training data not found: {args.data}")
        print("Run fetch_h1_training_data.py first!")
        return 1
    
    # Load data
    df = load_training_data(args.data)
    
    # Load Barttorvik ratings and aliases
    training_dir = Path(__file__).parent.parent / "training_data"
    ratings = load_barttorvik_ratings(training_dir / "barttorvik_lookup.json")
    aliases = load_team_aliases(training_dir / "team_aliases_db.json")
    
    print(f"Loaded {len(ratings)} Barttorvik ratings")
    print(f"Loaded {len(aliases)} team aliases")
    
    # Build features
    print("\nBuilding features...")
    features = build_h1_features(df, ratings, aliases)
    
    print(f"Feature columns: {list(features.columns)}")
    print(f"Feature matrix shape: {features.shape}")
    
    # Prepare labels
    y_spread = df["h1_spread_cover"].dropna().astype(int)
    y_total = df["h1_total_over"].dropna().astype(int)
    
    print(f"\n1H Spread samples: {len(y_spread)}")
    print(f"1H Total samples: {len(y_total)}")
    
    if len(y_spread) < 50:
        print("\n[WARNING] Very small sample size. Results may not be reliable.")
        print("          Consider fetching more historical data.")
    
    # Time-series split (train on past, test on future)
    # Use 80/20 split based on date
    train_size = int(len(df) * 0.8)
    
    X_train = features.iloc[:train_size]
    X_test = features.iloc[train_size:]
    
    # ========== Train 1H Spread Model ==========
    print("\n" + "=" * 70)
    print("Training 1H Spread Model")
    print("=" * 70)
    
    # Get valid indices for spread
    spread_valid = df["h1_spread_cover"].notna()
    y_spread_train = df.loc[spread_valid & (df.index < train_size), "h1_spread_cover"].astype(int)
    y_spread_test = df.loc[spread_valid & (df.index >= train_size), "h1_spread_cover"].astype(int)
    X_spread_train = features.loc[y_spread_train.index]
    X_spread_test = features.loc[y_spread_test.index]
    
    if len(y_spread_test) >= 10:
        # Use part of train for validation
        val_size = int(len(X_spread_train) * 0.2)
        X_val = X_spread_train.iloc[-val_size:]
        y_val = y_spread_train.iloc[-val_size:]
        X_train_sub = X_spread_train.iloc[:-val_size]
        y_train_sub = y_spread_train.iloc[:-val_size]
        
        if len(y_train_sub) >= 10:
            spread_model = train_model(X_train_sub, y_train_sub, X_val, y_val, "1H Spread")
            spread_results = evaluate_model(spread_model, X_spread_test, y_spread_test, "1H Spread")
            
            # Feature importance
            importance = pd.DataFrame({
                "feature": features.columns,
                "importance": spread_model.feature_importances_,
            }).sort_values("importance", ascending=False)
            
            print("\nTop Features (1H Spread):")
            for _, row in importance.head(5).iterrows():
                print(f"  {row['feature']}: {row['importance']:.3f}")
        else:
            print("[SKIP] Not enough training samples for 1H Spread")
            spread_model = None
    else:
        print("[SKIP] Not enough test samples for 1H Spread")
        spread_model = None
    
    # ========== Train 1H Total Model ==========
    print("\n" + "=" * 70)
    print("Training 1H Total Model")
    print("=" * 70)
    
    # Get valid indices for total
    total_valid = df["h1_total_over"].notna()
    y_total_train = df.loc[total_valid & (df.index < train_size), "h1_total_over"].astype(int)
    y_total_test = df.loc[total_valid & (df.index >= train_size), "h1_total_over"].astype(int)
    X_total_train = features.loc[y_total_train.index]
    X_total_test = features.loc[y_total_test.index]
    
    if len(y_total_test) >= 10:
        # Use part of train for validation
        val_size = int(len(X_total_train) * 0.2)
        X_val = X_total_train.iloc[-val_size:]
        y_val = y_total_train.iloc[-val_size:]
        X_train_sub = X_total_train.iloc[:-val_size]
        y_train_sub = y_total_train.iloc[:-val_size]
        
        if len(y_train_sub) >= 10:
            total_model = train_model(X_train_sub, y_train_sub, X_val, y_val, "1H Total")
            total_results = evaluate_model(total_model, X_total_test, y_total_test, "1H Total")
            
            # Feature importance
            importance = pd.DataFrame({
                "feature": features.columns,
                "importance": total_model.feature_importances_,
            }).sort_values("importance", ascending=False)
            
            print("\nTop Features (1H Total):")
            for _, row in importance.head(5).iterrows():
                print(f"  {row['feature']}: {row['importance']:.3f}")
        else:
            print("[SKIP] Not enough training samples for 1H Total")
            total_model = None
    else:
        print("[SKIP] Not enough test samples for 1H Total")
        total_model = None
    
    # Save models
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    if spread_model:
        spread_path = args.output_dir / "h1_spread_model.json"
        spread_model.save_model(spread_path)
        print(f"\nSaved 1H Spread model to {spread_path}")
    
    if total_model:
        total_path = args.output_dir / "h1_total_model.json"
        total_model.save_model(total_path)
        print(f"Saved 1H Total model to {total_path}")
    
    print("\n" + "=" * 70)
    print("Training Complete!")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
