#!/usr/bin/env python3
"""
Analyze historical data to determine feature importance for NCAAM predictions.
Uses canonical data from Azure Blob Storage.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score, log_loss
import warnings
warnings.filterwarnings('ignore')

from testing.azure_io import read_csv, read_json, list_files

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Data paths (Azure-only)
BACKTEST_PREFIX = "backtest_datasets"
NCAAHOPR_PREFIX = "ncaahoopR_data-master"

def load_training_data():
    """Load the main training data with odds"""
    logger.info("Loading training data with odds...")
    df = read_csv(f"{BACKTEST_PREFIX}/training_data_with_odds.csv")
    logger.info(f"  Loaded {len(df)} games from {df.game_date.min()} to {df.game_date.max()}")
    
    # Convert date
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Calculate actual spreads and totals
    df['actual_spread'] = df['home_score'] - df['away_score']
    df['actual_total'] = df['home_score'] + df['away_score']
    
    # Calculate market errors
    df['spread_error'] = df['actual_spread'] - df['spread_open']
    df['total_error'] = df['actual_total'] - df['total_open']
    
    # Binary outcomes
    df['home_cover'] = (df['actual_spread'] > df['spread_open']).astype(int)
    df['over'] = (df['actual_total'] > df['total_open']).astype(int)
    df['home_win'] = (df['home_score'] > df['away_score']).astype(int)
    
    return df

def load_h1_data():
    """Load first half historical data"""
    logger.info("Loading first half data...")
    h1_blob = f"{BACKTEST_PREFIX}/h1_historical_odds.csv"
    if list_files(h1_blob):
        df = read_csv(h1_blob)
        logger.info(f"  Loaded {len(df)} first half records")
        return df
    else:
        logger.warning("  No first half data found")
        return pd.DataFrame()

def load_barttorvik_ratings():
    """Load Barttorvik ratings"""
    logger.info("Loading Barttorvik ratings...")
    df = read_csv(f"{BACKTEST_PREFIX}/barttorvik_ratings.csv")
    logger.info(f"  Loaded ratings for {len(df)} teams")
    logger.info(f"  Columns: {df.columns.tolist()}")
    return df

def load_team_aliases():
    """Load team alias mappings"""
    return read_json(f"{BACKTEST_PREFIX}/team_aliases_db.json")

def analyze_ncaahoopR_sample():
    """Sample analysis of ncaahoopR data structure"""
    logger.info("\n=== Analyzing ncaahoopR Data Structure ===")
    
    # Check a sample season
    season_prefix = f"{NCAAHOPR_PREFIX}/2023-24"
    
    # Play-by-play
    pbp_prefix = f"{season_prefix}/pbp_logs/"
    pbp_files = list_files(pbp_prefix, pattern="*.csv")
    if pbp_files:
        logger.info(f"  Found {len(pbp_files)} PBP files")
        sample_pbp = read_csv(pbp_files[0], nrows=5)
        logger.info(f"  Sample PBP columns: {sample_pbp.columns.tolist()[:10]}...")
        logger.info(f"  Sample PBP shape: {sample_pbp.shape}")
    
    # Box scores
    box_prefix = f"{season_prefix}/box_scores/"
    box_files = list_files(box_prefix, pattern="*.csv")
    if box_files:
        logger.info(f"  Found {len(box_files)} box score files")
        sample_box = read_csv(box_files[0], nrows=5)
        logger.info(f"  Sample box columns: {sample_box.columns.tolist()[:10]}...")
    
    # Rosters
    roster_prefix = f"{season_prefix}/rosters/"
    roster_files = list_files(roster_prefix, pattern="*.csv")
    if roster_files:
        logger.info(f"  Found {len(roster_files)} roster files")
    
    # Schedules
    schedule_prefix = f"{season_prefix}/schedules/"
    schedule_files = list_files(schedule_prefix, pattern="*.csv")
    if schedule_files:
        logger.info(f"  Found {len(schedule_files)} schedule files")

def extract_basic_features(games_df, ratings_df, aliases):
    """Extract basic features from available data"""
    logger.info("\n=== Extracting Basic Features ===")
    
    features_list = []
    
    for _, game in games_df.iterrows():
        features = {
            'game_id': game['game_id'],
            'game_date': game['game_date'],
            'home_team': game['home_team'],
            'away_team': game['away_team'],
            'spread_open': game['spread_open'],
            'total_open': game['total_open'],
            'home_score': game['home_score'],
            'away_score': game['away_score']
        }
        
        # Try to match teams with ratings
        home_rating = ratings_df[ratings_df['team'] == game['home_team']]
        away_rating = ratings_df[ratings_df['team'] == game['away_team']]
        
        # If exact match fails, try aliases
        if home_rating.empty and game['home_team'] in aliases:
            canonical = aliases[game['home_team']].get('canonical_name')
            if canonical:
                home_rating = ratings_df[ratings_df['team'] == canonical]
        
        if away_rating.empty and game['away_team'] in aliases:
            canonical = aliases[game['away_team']].get('canonical_name')
            if canonical:
                away_rating = ratings_df[ratings_df['team'] == canonical]
        
        # Add rating features if found
        if not home_rating.empty:
            for col in ['adj_o', 'adj_d', 'barthag', 'efg', 'efgd', 'ftrd', 'ppg', 'opp_ppg']:
                if col in home_rating.columns:
                    features[f'home_{col}'] = home_rating.iloc[0][col]
        
        if not away_rating.empty:
            for col in ['adj_o', 'adj_d', 'barthag', 'efg', 'efgd', 'ftrd', 'ppg', 'opp_ppg']:
                if col in away_rating.columns:
                    features[f'away_{col}'] = away_rating.iloc[0][col]
        
        # Calculate differentials if both teams have ratings
        if not home_rating.empty and not away_rating.empty:
            for col in ['adj_o', 'adj_d', 'barthag']:
                if col in home_rating.columns and col in away_rating.columns:
                    features[f'{col}_diff'] = home_rating.iloc[0][col] - away_rating.iloc[0][col]
        
        features_list.append(features)
    
    return pd.DataFrame(features_list)

def analyze_feature_importance(features_df):
    """Analyze feature importance for different betting markets"""
    logger.info("\n=== Feature Importance Analysis ===")
    
    # Prepare features and targets
    feature_cols = [col for col in features_df.columns if col not in [
        'game_id', 'game_date', 'home_team', 'away_team', 
        'home_score', 'away_score', 'spread_open', 'total_open'
    ]]
    
    # Remove rows with NaN in feature columns
    clean_df = features_df.dropna(subset=feature_cols)
    logger.info(f"  Clean samples: {len(clean_df)} out of {len(features_df)}")
    
    if len(clean_df) < 100:
        logger.warning("  Not enough clean samples for analysis")
        return
    
    X = clean_df[feature_cols]
    
    # Analyze spread prediction
    logger.info("\n  Spread Prediction:")
    y_spread = clean_df['home_score'] - clean_df['away_score']
    X_train, X_test, y_train, y_test = train_test_split(X, y_spread, test_size=0.2, random_state=42)
    
    rf_spread = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf_spread.fit(X_train, y_train)
    
    y_pred = rf_spread.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    logger.info(f"    MAE: {mae:.2f} points")
    logger.info(f"    RMSE: {rmse:.2f} points")
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf_spread.feature_importances_
    }).sort_values('importance', ascending=False)
    
    logger.info("    Top 10 features:")
    for _, row in importance.head(10).iterrows():
        logger.info(f"      {row['feature']}: {row['importance']:.4f}")
    
    # Analyze total prediction  
    logger.info("\n  Total Prediction:")
    y_total = clean_df['home_score'] + clean_df['away_score']
    X_train, X_test, y_train, y_test = train_test_split(X, y_total, test_size=0.2, random_state=42)
    
    rf_total = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf_total.fit(X_train, y_train)
    
    y_pred = rf_total.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    logger.info(f"    MAE: {mae:.2f} points")
    logger.info(f"    RMSE: {rmse:.2f} points")
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf_total.feature_importances_
    }).sort_values('importance', ascending=False)
    
    logger.info("    Top 10 features:")
    for _, row in importance.head(10).iterrows():
        logger.info(f"      {row['feature']}: {row['importance']:.4f}")
    
    # Analyze moneyline (win probability)
    logger.info("\n  Moneyline (Win Probability):")
    y_win = (clean_df['home_score'] > clean_df['away_score']).astype(int)
    X_train, X_test, y_train, y_test = train_test_split(X, y_win, test_size=0.2, random_state=42)
    
    rf_ml = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf_ml.fit(X_train, y_train)
    
    y_pred = rf_ml.predict(X_test)
    y_proba = rf_ml.predict_proba(X_test)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    logloss = log_loss(y_test, y_proba)
    
    logger.info(f"    Accuracy: {accuracy:.3f}")
    logger.info(f"    Log Loss: {logloss:.3f}")
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf_ml.feature_importances_
    }).sort_values('importance', ascending=False)
    
    logger.info("    Top 10 features:")
    for _, row in importance.head(10).iterrows():
        logger.info(f"      {row['feature']}: {row['importance']:.4f}")

def analyze_market_efficiency():
    """Analyze how efficient the betting markets are"""
    logger.info("\n=== Market Efficiency Analysis ===")
    
    games_df = load_training_data()
    
    # Spread market
    logger.info("\n  Spread Market:")
    logger.info(f"    Mean error: {games_df['spread_error'].mean():.2f}")
    logger.info(f"    Std error: {games_df['spread_error'].std():.2f}")
    logger.info(f"    MAE: {games_df['spread_error'].abs().mean():.2f}")
    logger.info(f"    Home cover rate: {games_df['home_cover'].mean():.3f}")
    
    # Total market
    logger.info("\n  Total Market:")
    logger.info(f"    Mean error: {games_df['total_error'].mean():.2f}")
    logger.info(f"    Std error: {games_df['total_error'].std():.2f}")
    logger.info(f"    MAE: {games_df['total_error'].abs().mean():.2f}")
    logger.info(f"    Over rate: {games_df['over'].mean():.3f}")
    
    # By season (if we can extract it)
    games_df['season'] = games_df['game_date'].dt.year
    games_df.loc[games_df['game_date'].dt.month < 6, 'season'] -= 1
    
    logger.info("\n  By Season:")
    season_stats = games_df.groupby('season').agg({
        'spread_error': ['mean', 'std'],
        'total_error': ['mean', 'std'],
        'home_cover': 'mean',
        'over': 'mean'
    }).round(3)
    print(season_stats)

def main():
    """Main analysis pipeline"""
    logger.info("="*80)
    logger.info("HISTORICAL DATA ANALYSIS FOR NCAAM PREDICTIONS")
    logger.info("="*80)
    
    # Load main data
    games_df = load_training_data()
    h1_df = load_h1_data()
    ratings_df = load_barttorvik_ratings()
    aliases = load_team_aliases()
    
    # Analyze data structure
    analyze_ncaahoopR_sample()
    
    # Extract features
    features_df = extract_basic_features(games_df, ratings_df, aliases)
    logger.info(f"\nExtracted features for {len(features_df)} games")
    logger.info(f"Feature columns: {features_df.columns.tolist()}")
    
    # Analyze feature importance
    analyze_feature_importance(features_df)
    
    # Analyze market efficiency
    analyze_market_efficiency()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("ANALYSIS SUMMARY")
    logger.info("="*80)
    logger.info("\nKey Findings:")
    logger.info("1. Available data spans multiple seasons with odds and scores")
    logger.info("2. Barttorvik ratings provide team strength metrics")
    logger.info("3. ncaahoopR has detailed PBP/box score data to explore")
    logger.info("4. Need to improve team name matching for better coverage")
    logger.info("5. Markets are relatively efficient but opportunities exist")
    
    logger.info("\nNext Steps:")
    logger.info("1. Implement better team name canonicalization")
    logger.info("2. Extract PBP features from ncaahoopR data")
    logger.info("3. Add more Barttorvik fields (46 available, using ~10)")
    logger.info("4. Fetch historical moneyline odds")
    logger.info("5. Build separate models for FG/H1 × spread/total/ML")

if __name__ == "__main__":
    main()
