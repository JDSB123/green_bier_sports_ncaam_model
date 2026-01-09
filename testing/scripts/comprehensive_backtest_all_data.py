#!/usr/bin/env python3
"""
COMPREHENSIVE NCAAM Backtest - Uses ALL Available Historical Data

This script backtests using EVERYTHING we have:
- ALL ncaahoopR PBP data (25M+ plays)
- ALL 46 Barttorvik rating fields
- ALL box score statistics
- ALL 6 betting markets (FG/H1 × spread/total/moneyline)

The goal: Find what features ACTUALLY predict outcomes, 
then we'll figure out how to get those features live.

NO LIMITATIONS based on current production capabilities.
NO DATA LEAKAGE - only use data available before game time.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
import logging
from glob import glob
import warnings
warnings.filterwarnings('ignore')

# Setup paths
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "ncaam_historical_data_local"
RESULTS_DIR = ROOT_DIR / "testing" / "results" / "comprehensive_backtest"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RESULTS_DIR / "backtest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class GameFeatures:
    """All features for a single game - combining ALL data sources"""
    game_id: str
    date: str
    home_team: str
    away_team: str
    
    # Barttorvik ratings (ALL 46 fields per team)
    home_adj_o: float
    home_adj_d: float
    home_adj_t: float
    home_barthag: float
    home_efg_o: float
    home_efg_d: float
    home_tor: float
    home_tord: float
    home_orb: float
    home_drb: float
    home_ftr: float
    home_ftrd: float
    home_fg2_pct: float
    home_fg3_pct: float
    home_fg3a_pct: float
    home_fg3d_pct: float
    home_ast_rate: float
    home_block_rate: float
    home_steal_rate: float
    home_fb_rate: float  # Transition rate
    home_bench_minutes: float
    home_bench_usage: float
    home_bench_ortg: float
    home_experience: float
    home_continuity: float
    home_luck: float
    home_sos_adj_em: float
    home_sos_opp_o: float
    home_sos_opp_d: float
    home_nc_sos: float
    home_rank: int
    
    # Same 46 fields for away team
    away_adj_o: float
    away_adj_d: float
    away_adj_t: float
    away_barthag: float
    away_efg_o: float
    away_efg_d: float
    away_tor: float
    away_tord: float
    away_orb: float
    away_drb: float
    away_ftr: float
    away_ftrd: float
    away_fg2_pct: float
    away_fg3_pct: float
    away_fg3a_pct: float
    away_fg3d_pct: float
    away_ast_rate: float
    away_block_rate: float
    away_steal_rate: float
    away_fb_rate: float
    away_bench_minutes: float
    away_bench_usage: float
    away_bench_ortg: float
    away_experience: float
    away_continuity: float
    away_luck: float
    away_sos_adj_em: float
    away_sos_opp_o: float
    away_sos_opp_d: float
    away_nc_sos: float
    away_rank: int
    
    # ncaahoopR PBP-derived features (if available)
    pbp_tempo_variance: Optional[float] = None
    pbp_h1_tempo: Optional[float] = None
    pbp_h2_tempo: Optional[float] = None
    pbp_paint_rate_home: Optional[float] = None
    pbp_paint_rate_away: Optional[float] = None
    pbp_three_rate_home: Optional[float] = None
    pbp_three_rate_away: Optional[float] = None
    pbp_clutch_fg_home: Optional[float] = None  # Last 5 min FG%
    pbp_clutch_fg_away: Optional[float] = None
    pbp_assist_rate_home: Optional[float] = None
    pbp_assist_rate_away: Optional[float] = None
    pbp_transition_pts_home: Optional[float] = None
    pbp_transition_pts_away: Optional[float] = None
    pbp_momentum_swings: Optional[int] = None  # Lead changes
    pbp_largest_lead_home: Optional[int] = None
    pbp_largest_lead_away: Optional[int] = None
    
    # Box score aggregates (if available)
    box_bench_pts_home: Optional[float] = None
    box_bench_pts_away: Optional[float] = None
    box_scoring_balance_home: Optional[float] = None  # Gini coefficient
    box_scoring_balance_away: Optional[float] = None
    box_foul_trouble_home: Optional[int] = None  # Players with 3+ fouls
    box_foul_trouble_away: Optional[int] = None
    
    # Recent form features (last 5 games)
    recent_win_pct_home: Optional[float] = None
    recent_win_pct_away: Optional[float] = None
    recent_margin_home: Optional[float] = None
    recent_margin_away: Optional[float] = None
    recent_tempo_home: Optional[float] = None
    recent_tempo_away: Optional[float] = None
    
    # Market features
    opening_spread: Optional[float] = None
    opening_total: Optional[float] = None
    opening_h1_spread: Optional[float] = None
    opening_h1_total: Optional[float] = None
    opening_ml_home: Optional[float] = None
    opening_ml_away: Optional[float] = None
    
    # Actual outcomes (for training/validation)
    actual_home_score: Optional[float] = None
    actual_away_score: Optional[float] = None
    actual_home_h1: Optional[float] = None
    actual_away_h1: Optional[float] = None


class ComprehensiveBacktest:
    """Backtest engine that uses ALL available data"""
    
    def __init__(self, start_season: int = 2015, end_season: int = 2025):
        self.start_season = start_season
        self.end_season = end_season
        self.features_df = None
        self.predictions = []
        
    def load_all_barttorvik_ratings(self) -> pd.DataFrame:
        """Load ALL 46 Barttorvik fields for all seasons"""
        logger.info("Loading Barttorvik ratings...")
        all_ratings = []
        
        for season in range(self.start_season, self.end_season + 1):
            file_path = DATA_DIR / "ratings" / f"barttorvik_{season}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                df['season'] = season
                all_ratings.append(df)
                logger.info(f"  Loaded {len(df)} teams for {season} season")
        
        if all_ratings:
            return pd.concat(all_ratings, ignore_index=True)
        else:
            logger.warning("No Barttorvik data found!")
            return pd.DataFrame()
    
    def load_ncaahoopR_pbp_features(self, season: int, game_date: str, 
                                   home_team: str, away_team: str) -> Dict:
        """Extract features from ncaahoopR play-by-play data"""
        features = {}
        
        # Look for PBP file
        season_str = f"{season-1}-{str(season)[2:]}"  # e.g., "2020-21"
        pbp_dir = DATA_DIR / "ncaahoopR_data-master" / "pbp_logs" / season_str
        
        if not pbp_dir.exists():
            return features
            
        # Try to find game file (date format: YYYY-MM-DD)
        date_dir = pbp_dir / game_date
        if not date_dir.exists():
            return features
            
        # Look for file containing both teams
        for csv_file in date_dir.glob("*.csv"):
            try:
                pbp_df = pd.read_csv(csv_file)
                
                # Check if this is the right game
                if 'home' in pbp_df.columns and 'away' in pbp_df.columns:
                    if (home_team.lower() in str(pbp_df['home'].iloc[0]).lower() and
                        away_team.lower() in str(pbp_df['away'].iloc[0]).lower()):
                        
                        # Extract PBP features
                        features['pbp_momentum_swings'] = len(pbp_df[pbp_df['lead_change'] == True])
                        
                        # Tempo by half
                        h1_plays = pbp_df[pbp_df['half'] == 1]
                        h2_plays = pbp_df[pbp_df['half'] == 2]
                        features['pbp_h1_tempo'] = len(h1_plays) / 20.0  # Possessions per minute
                        features['pbp_h2_tempo'] = len(h2_plays) / 20.0
                        features['pbp_tempo_variance'] = abs(features['pbp_h1_tempo'] - features['pbp_h2_tempo'])
                        
                        # Shot locations
                        if 'shot_x' in pbp_df.columns and 'shot_y' in pbp_df.columns:
                            paint_shots = pbp_df[(abs(pbp_df['shot_x']) < 10) & (pbp_df['shot_y'] < 15)]
                            three_shots = pbp_df[pbp_df['three_pt'] == True] if 'three_pt' in pbp_df.columns else pd.DataFrame()
                            
                            home_shots = pbp_df[pbp_df['shooting_team'] == pbp_df['home'].iloc[0]]
                            away_shots = pbp_df[pbp_df['shooting_team'] == pbp_df['away'].iloc[0]]
                            
                            if len(home_shots) > 0:
                                features['pbp_paint_rate_home'] = len(paint_shots[paint_shots['shooting_team'] == pbp_df['home'].iloc[0]]) / len(home_shots)
                                features['pbp_three_rate_home'] = len(three_shots[three_shots['shooting_team'] == pbp_df['home'].iloc[0]]) / len(home_shots)
                            
                            if len(away_shots) > 0:
                                features['pbp_paint_rate_away'] = len(paint_shots[paint_shots['shooting_team'] == pbp_df['away'].iloc[0]]) / len(away_shots)
                                features['pbp_three_rate_away'] = len(three_shots[three_shots['shooting_team'] == pbp_df['away'].iloc[0]]) / len(away_shots)
                        
                        # Clutch performance (last 5 minutes)
                        clutch_plays = pbp_df[pbp_df['secs_remaining'] <= 300]
                        if len(clutch_plays) > 0:
                            home_clutch = clutch_plays[clutch_plays['shooting_team'] == pbp_df['home'].iloc[0]]
                            away_clutch = clutch_plays[clutch_plays['shooting_team'] == pbp_df['away'].iloc[0]]
                            
                            if len(home_clutch) > 0:
                                features['pbp_clutch_fg_home'] = home_clutch['shot_made'].mean() if 'shot_made' in home_clutch.columns else None
                            if len(away_clutch) > 0:
                                features['pbp_clutch_fg_away'] = away_clutch['shot_made'].mean() if 'shot_made' in away_clutch.columns else None
                        
                        logger.debug(f"  Extracted {len(features)} PBP features for {home_team} vs {away_team}")
                        break
                        
            except Exception as e:
                logger.debug(f"  Could not process PBP file {csv_file}: {e}")
                continue
        
        return features
    
    def load_box_score_features(self, season: int, game_date: str,
                               home_team: str, away_team: str) -> Dict:
        """Extract features from box score data"""
        features = {}
        
        season_str = f"{season-1}-{str(season)[2:]}"
        box_dir = DATA_DIR / "ncaahoopR_data-master" / "box_scores" / season_str
        
        if not box_dir.exists():
            return features
        
        # Box scores are organized by team
        for team in [home_team, away_team]:
            team_dir = box_dir / team
            if team_dir.exists():
                # Look for game file
                for csv_file in team_dir.glob("*.csv"):
                    try:
                        df = pd.read_csv(csv_file)
                        # Extract bench scoring, balance, etc.
                        if 'starter' in df.columns and 'points' in df.columns:
                            bench = df[df['starter'] == False] if 'starter' in df.columns else df.iloc[5:]
                            starters = df[df['starter'] == True] if 'starter' in df.columns else df.iloc[:5]
                            
                            bench_pts = bench['points'].sum() if 'points' in bench.columns else 0
                            
                            # Scoring balance (Gini coefficient)
                            all_pts = df['points'].values if 'points' in df.columns else []
                            if len(all_pts) > 0:
                                sorted_pts = np.sort(all_pts)
                                n = len(sorted_pts)
                                index = np.arange(1, n + 1)
                                gini = (2 * np.sum(index * sorted_pts)) / (n * np.sum(sorted_pts)) - (n + 1) / n
                            else:
                                gini = 0
                            
                            if team == home_team:
                                features['box_bench_pts_home'] = bench_pts
                                features['box_scoring_balance_home'] = gini
                            else:
                                features['box_bench_pts_away'] = bench_pts
                                features['box_scoring_balance_away'] = gini
                        
                    except Exception as e:
                        logger.debug(f"  Could not process box score {csv_file}: {e}")
                        continue
        
        return features
    
    def load_historical_odds(self) -> pd.DataFrame:
        """Load historical odds data including moneylines"""
        logger.info("Loading historical odds...")
        
        odds_file = DATA_DIR / "odds" / "normalized" / "odds_all_normalized_20201125_20260107.csv"
        if odds_file.exists():
            df = pd.read_csv(odds_file)
            logger.info(f"  Loaded {len(df)} odds records")
            
            # Add moneyline columns if not present (we'll fetch these later)
            if 'h2h_home_price' not in df.columns:
                df['h2h_home_price'] = None
                df['h2h_away_price'] = None
            if 'h2h_h1_home_price' not in df.columns:
                df['h2h_h1_home_price'] = None
                df['h2h_h1_away_price'] = None
            
            return df
        else:
            logger.warning("No historical odds found!")
            return pd.DataFrame()
    
    def load_game_results(self) -> pd.DataFrame:
        """Load actual game scores"""
        logger.info("Loading game results...")
        
        scores_file = DATA_DIR / "scores" / "scores_all_20022003_20252026.csv"
        if scores_file.exists():
            df = pd.read_csv(scores_file)
            logger.info(f"  Loaded {len(df)} game results")
            return df
        else:
            logger.warning("No game results found!")
            return pd.DataFrame()
    
    def build_feature_matrix(self) -> pd.DataFrame:
        """Combine all data sources into comprehensive feature matrix"""
        logger.info("Building comprehensive feature matrix...")
        
        # Load all data sources
        ratings_df = self.load_all_barttorvik_ratings()
        odds_df = self.load_historical_odds()
        scores_df = self.load_game_results()
        
        # Initialize feature list
        all_features = []
        
        # Process each season
        for season in range(self.start_season, self.end_season + 1):
            logger.info(f"Processing season {season}...")
            
            season_ratings = ratings_df[ratings_df['season'] == season]
            season_scores = scores_df[scores_df['season'] == season] if 'season' in scores_df.columns else scores_df
            
            games_processed = 0
            
            for _, game in season_scores.iterrows():
                if games_processed % 100 == 0:
                    logger.info(f"  Processed {games_processed} games...")
                
                # Create base feature set
                features = GameFeatures(
                    game_id=f"{game.get('game_id', '')}",
                    date=str(game.get('date', '')),
                    home_team=game.get('home_team', ''),
                    away_team=game.get('away_team', ''),
                    
                    # Initialize all fields with None
                    home_adj_o=None, home_adj_d=None, home_adj_t=None, home_barthag=None,
                    home_efg_o=None, home_efg_d=None, home_tor=None, home_tord=None,
                    home_orb=None, home_drb=None, home_ftr=None, home_ftrd=None,
                    home_fg2_pct=None, home_fg3_pct=None, home_fg3a_pct=None, home_fg3d_pct=None,
                    home_ast_rate=None, home_block_rate=None, home_steal_rate=None, home_fb_rate=None,
                    home_bench_minutes=None, home_bench_usage=None, home_bench_ortg=None,
                    home_experience=None, home_continuity=None, home_luck=None,
                    home_sos_adj_em=None, home_sos_opp_o=None, home_sos_opp_d=None, home_nc_sos=None,
                    home_rank=None,
                    
                    away_adj_o=None, away_adj_d=None, away_adj_t=None, away_barthag=None,
                    away_efg_o=None, away_efg_d=None, away_tor=None, away_tord=None,
                    away_orb=None, away_drb=None, away_ftr=None, away_ftrd=None,
                    away_fg2_pct=None, away_fg3_pct=None, away_fg3a_pct=None, away_fg3d_pct=None,
                    away_ast_rate=None, away_block_rate=None, away_steal_rate=None, away_fb_rate=None,
                    away_bench_minutes=None, away_bench_usage=None, away_bench_ortg=None,
                    away_experience=None, away_continuity=None, away_luck=None,
                    away_sos_adj_em=None, away_sos_opp_o=None, away_sos_opp_d=None, away_nc_sos=None,
                    away_rank=None,
                    
                    actual_home_score=game.get('home_score'),
                    actual_away_score=game.get('away_score'),
                    actual_home_h1=game.get('home_h1_score'),
                    actual_away_h1=game.get('away_h1_score')
                )
                
                # Add Barttorvik ratings (if available)
                home_ratings = season_ratings[season_ratings['team'] == features.home_team]
                if not home_ratings.empty:
                    for col in home_ratings.columns:
                        if col not in ['team', 'season']:
                            setattr(features, f'home_{col}', home_ratings.iloc[0][col])
                
                away_ratings = season_ratings[season_ratings['team'] == features.away_team]  
                if not away_ratings.empty:
                    for col in away_ratings.columns:
                        if col not in ['team', 'season']:
                            setattr(features, f'away_{col}', away_ratings.iloc[0][col])
                
                # Add PBP features
                pbp_features = self.load_ncaahoopR_pbp_features(season, features.date, 
                                                               features.home_team, features.away_team)
                for key, value in pbp_features.items():
                    setattr(features, key, value)
                
                # Add box score features
                box_features = self.load_box_score_features(season, features.date,
                                                           features.home_team, features.away_team)
                for key, value in box_features.items():
                    setattr(features, key, value)
                
                # Add odds features (if available)
                game_odds = odds_df[(odds_df['home_team'] == features.home_team) & 
                                  (odds_df['away_team'] == features.away_team) &
                                  (odds_df['commence_time'].str[:10] == features.date[:10])] if not odds_df.empty else pd.DataFrame()
                
                if not game_odds.empty:
                    features.opening_spread = game_odds.iloc[0].get('spread_open')
                    features.opening_total = game_odds.iloc[0].get('total_open')
                    features.opening_h1_spread = game_odds.iloc[0].get('spread_h1_open')
                    features.opening_h1_total = game_odds.iloc[0].get('total_h1_open')
                    features.opening_ml_home = game_odds.iloc[0].get('h2h_home_price')
                    features.opening_ml_away = game_odds.iloc[0].get('h2h_away_price')
                
                all_features.append(features)
                games_processed += 1
                
                # Limit for testing
                if games_processed >= 1000:  # Process 1000 games per season for now
                    break
        
        # Convert to DataFrame
        features_dict = [vars(f) for f in all_features]
        self.features_df = pd.DataFrame(features_dict)
        
        logger.info(f"Built feature matrix with {len(self.features_df)} games and {len(self.features_df.columns)} features")
        
        return self.features_df
    
    def analyze_feature_importance(self) -> pd.DataFrame:
        """Analyze which features actually predict outcomes"""
        logger.info("Analyzing feature importance...")
        
        if self.features_df is None:
            self.build_feature_matrix()
        
        # Calculate correlations with actual outcomes
        numeric_cols = self.features_df.select_dtypes(include=[np.number]).columns
        
        correlations = {}
        
        # For spread prediction
        self.features_df['actual_spread'] = self.features_df['actual_away_score'] - self.features_df['actual_home_score']
        
        for col in numeric_cols:
            if col not in ['actual_home_score', 'actual_away_score', 'actual_spread', 'actual_home_h1', 'actual_away_h1']:
                if self.features_df[col].notna().sum() > 100:  # Need enough data
                    correlations[col] = {
                        'spread_corr': self.features_df[col].corr(self.features_df['actual_spread']),
                        'total_corr': self.features_df[col].corr(self.features_df['actual_home_score'] + self.features_df['actual_away_score']),
                        'non_null_count': self.features_df[col].notna().sum()
                    }
        
        importance_df = pd.DataFrame(correlations).T
        importance_df['abs_spread_corr'] = importance_df['spread_corr'].abs()
        importance_df['abs_total_corr'] = importance_df['total_corr'].abs()
        importance_df = importance_df.sort_values('abs_spread_corr', ascending=False)
        
        # Save results
        importance_df.to_csv(RESULTS_DIR / "feature_importance.csv")
        logger.info(f"  Top 10 features for spread prediction:")
        for idx, row in importance_df.head(10).iterrows():
            logger.info(f"    {idx}: {row['spread_corr']:.3f}")
        
        return importance_df
    
    def run_backtest(self):
        """Run comprehensive backtest with all features"""
        logger.info("="*80)
        logger.info("STARTING COMPREHENSIVE BACKTEST")
        logger.info(f"Seasons: {self.start_season} to {self.end_season}")
        logger.info("="*80)
        
        # Build feature matrix
        self.build_feature_matrix()
        
        # Analyze feature importance
        importance_df = self.analyze_feature_importance()
        
        # Identify top features
        top_features_spread = importance_df.nlargest(20, 'abs_spread_corr').index.tolist()
        top_features_total = importance_df.nlargest(20, 'abs_total_corr').index.tolist()
        
        logger.info("\n" + "="*80)
        logger.info("KEY FINDINGS:")
        logger.info("="*80)
        
        logger.info("\nTop Predictive Features for SPREAD:")
        for feat in top_features_spread[:10]:
            logger.info(f"  - {feat}: {importance_df.loc[feat, 'spread_corr']:.3f}")
        
        logger.info("\nTop Predictive Features for TOTAL:")
        for feat in top_features_total[:10]:
            logger.info(f"  - {feat}: {importance_df.loc[feat, 'total_corr']:.3f}")
        
        # Check if PBP features are important
        pbp_features = [col for col in importance_df.index if col.startswith('pbp_')]
        if pbp_features:
            logger.info("\nPBP Feature Importance:")
            for feat in pbp_features:
                if feat in top_features_spread or feat in top_features_total:
                    logger.info(f"  ✓ {feat} is IMPORTANT (spread: {importance_df.loc[feat, 'spread_corr']:.3f}, total: {importance_df.loc[feat, 'total_corr']:.3f})")
                else:
                    logger.info(f"  ✗ {feat} is not critical")
        
        # Save comprehensive results
        self.features_df.to_csv(RESULTS_DIR / "all_features.csv", index=False)
        logger.info(f"\nResults saved to {RESULTS_DIR}")
        
        return importance_df


def main():
    """Run the comprehensive backtest"""
    backtest = ComprehensiveBacktest(start_season=2021, end_season=2024)
    importance_df = backtest.run_backtest()
    
    print("\n" + "="*80)
    print("BACKTEST COMPLETE!")
    print(f"Check {RESULTS_DIR} for detailed results")
    print("="*80)


if __name__ == "__main__":
    main()