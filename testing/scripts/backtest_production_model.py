#!/usr/bin/env python3
"""
Backtest the ACTUAL PRODUCTION model (BarttorvikPredictor v33.1) against historical data.

This tests what's ACTUALLY DEPLOYED - not hypothetical independent models.
Uses the real predictor.py with all calibrations (HCA=4.7, Total=-4.6).

v33.1 Production Calibrations:
- HCA Spread: 4.7 (from 4194-game backtest)
- Total Calibration: -4.6 (fixes over-prediction)
- 1H Spread HCA: 2.35 (50% of FG)
- 1H Total Cal: -2.3 (50% of FG)
"""

import sys
import json
from pathlib import Path

# Add prediction service to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "prediction-service-python"))

from app.predictor import BarttorvikPredictor, PredictorOutput
from app.models import TeamRatings

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional


def load_historical_games() -> pd.DataFrame:
    """Load all historical game data."""
    data_dir = Path(__file__).parent.parent / "data" / "historical"
    all_games = []
    
    for year in range(2019, 2025):
        games_file = data_dir / f"games_{year}.csv"
        if games_file.exists():
            df = pd.read_csv(games_file)
            df['season'] = year
            all_games.append(df)
            print(f"Loaded {len(df)} games from {year}")
    
    if not all_games:
        raise FileNotFoundError(f"No game data found in {data_dir}")
    
    combined = pd.concat(all_games, ignore_index=True)
    print(f"\nTotal games loaded: {len(combined)}")
    return combined


def load_barttorvik_data() -> Dict[int, Dict[str, Dict]]:
    """Load all Barttorvik ratings indexed by year and team.
    
    Barttorvik JSON structure is a list of lists:
    Index 0: Rank
    Index 1: Team name
    Index 2: Conference
    Index 3: Record
    Index 4: AdjO (Adjusted Offensive Efficiency)
    Index 5: AdjO Rank
    Index 6: AdjD (Adjusted Defensive Efficiency)  
    Index 7: AdjD Rank
    Index 8: Barthag (Power Rating)
    ...
    Index 44: Tempo (if available)
    """
    data_dir = Path(__file__).parent.parent / "data" / "historical"
    all_ratings = {}
    
    for year in range(2019, 2025):
        ratings_file = data_dir / f"barttorvik_{year}.json"
        if ratings_file.exists():
            with open(ratings_file) as f:
                data = json.load(f)
            
            all_ratings[year] = {}
            for team_data in data:
                if not isinstance(team_data, list) or len(team_data) < 10:
                    continue
                
                team_name = str(team_data[1]).lower().strip()
                if not team_name:
                    continue
                
                # Convert positional list to dictionary
                all_ratings[year][team_name] = {
                    'team': team_data[1],
                    'conference': team_data[2],
                    'adj_o': float(team_data[4]),
                    'adj_d': float(team_data[6]),
                    'barthag': float(team_data[8]) if len(team_data) > 8 else 0.5,
                    'tempo': float(team_data[44]) if len(team_data) > 44 else 68.0,
                    # Four factors - use defaults if not available
                    'efg': float(team_data[18]) if len(team_data) > 18 else 50.0,
                    'efg_d': float(team_data[19]) if len(team_data) > 19 else 50.0,
                    'orb': float(team_data[21]) if len(team_data) > 21 else 28.0,
                    'drb': float(team_data[22]) if len(team_data) > 22 else 72.0,
                    'tor': float(team_data[16]) if len(team_data) > 16 else 18.0,
                    'tord': float(team_data[17]) if len(team_data) > 17 else 18.0,
                    'ftr': float(team_data[20]) if len(team_data) > 20 else 33.0,
                    'ftrd': 33.0,  # Not in standard data
                    'three_pt_rate': float(team_data[14]) if len(team_data) > 14 else 35.0,
                    'three_pt_pct': 34.0,  # Not in standard data
                    'three_pt_pct_d': 34.0,
                    'two_pt_pct': 50.0,
                    'two_pt_pct_d': 50.0,
                    'ft_pct': 72.0,
                    'blk_pct': 8.0,
                    'stl_pct': 8.0,
                    'ast_pct': 50.0,
                }
            print(f"Loaded {len(all_ratings[year])} teams from Barttorvik {year}")
    
    return all_ratings


def create_team_ratings(rating_data: Dict) -> Optional[TeamRatings]:
    """Create TeamRatings from Barttorvik data - ALL 22 fields required."""
    try:
        return TeamRatings(
            team_name=rating_data.get('team', 'Unknown'),
            adj_o=float(rating_data.get('adj_o', rating_data.get('adjoe', 0))),
            adj_d=float(rating_data.get('adj_d', rating_data.get('adjde', 0))),
            tempo=float(rating_data.get('tempo', rating_data.get('adj_tempo', 68.0))),
            # Four Factors
            efg=float(rating_data.get('efg', rating_data.get('efg_o', 50.0))),
            efg_d=float(rating_data.get('efg_d', 50.0)),
            orb=float(rating_data.get('orb', rating_data.get('off_reb', 28.0))),
            drb=float(rating_data.get('drb', rating_data.get('def_reb', 72.0))),
            tor=float(rating_data.get('tor', rating_data.get('tov', 18.0))),
            tord=float(rating_data.get('tord', rating_data.get('tov_d', 18.0))),
            ftr=float(rating_data.get('ftr', rating_data.get('ft_rate', 33.0))),
            ftrd=float(rating_data.get('ftrd', rating_data.get('ft_rate_d', 33.0))),
            # 3PT
            three_pt_rate=float(rating_data.get('three_pt_rate', rating_data.get('three_rate', 35.0))),
            three_pt_pct=float(rating_data.get('three_pt_pct', rating_data.get('three_pct', 34.0))),
            three_pt_pct_d=float(rating_data.get('three_pt_pct_d', rating_data.get('three_pct_d', 34.0))),
            # Extra
            two_pt_pct=float(rating_data.get('two_pt_pct', rating_data.get('two_pct', 50.0))),
            two_pt_pct_d=float(rating_data.get('two_pt_pct_d', rating_data.get('two_pct_d', 50.0))),
            ft_pct=float(rating_data.get('ft_pct', rating_data.get('ft_pct_o', 72.0))),
            blk_pct=float(rating_data.get('blk_pct', rating_data.get('blk', 8.0))),
            stl_pct=float(rating_data.get('stl_pct', rating_data.get('stl', 8.0))),
            ast_pct=float(rating_data.get('ast_pct', rating_data.get('ast', 50.0))),
            conference=rating_data.get('conf', rating_data.get('conference', 'Unknown'))
        )
    except Exception as e:
        return None


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    if not name:
        return ""
    name = name.lower().strip()
    # Common abbreviations
    replacements = {
        'st.': 'state',
        'st ': 'state ',
        'u.': 'university',
        'n.': 'north',
        's.': 'south',
        'e.': 'east',
        'w.': 'west',
        '-': ' ',
        "'": "",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def find_team_rating(team_name: str, year: int, all_ratings: Dict) -> Optional[Dict]:
    """Find team rating with fuzzy matching."""
    if year not in all_ratings:
        return None
    
    normalized = normalize_team_name(team_name)
    ratings = all_ratings[year]
    
    # Exact match
    if normalized in ratings:
        return ratings[normalized]
    
    # Partial match
    for key, data in ratings.items():
        if normalized in key or key in normalized:
            return data
    
    return None


def run_backtest():
    """Run backtest of production model."""
    print("=" * 80)
    print("PRODUCTION MODEL BACKTEST - BarttorvikPredictor v33.1")
    print("=" * 80)
    print()
    
    # Initialize the ACTUAL production predictor
    predictor = BarttorvikPredictor()
    print(f"Production HCA Spread: {predictor.hca_spread}")
    print(f"Production HCA Total: {predictor.hca_total}")
    print(f"Production Total Calibration: {predictor.total_calibration}")
    print()
    
    # Load data
    games_df = load_historical_games()
    all_ratings = load_barttorvik_data()
    
    # Results storage
    results = {
        'fg_spread': {'predictions': [], 'actuals': []},
        'fg_total': {'predictions': [], 'actuals': []},
        'h1_spread': {'predictions': [], 'actuals': []},
        'h1_total': {'predictions': [], 'actuals': []},
    }
    
    matched = 0
    skipped_ratings = 0
    skipped_data = 0
    
    for idx, row in games_df.iterrows():
        try:
            season = row.get('season', 2024)
            
            # Get team names
            home_team = str(row.get('home_team', '')).strip()
            away_team = str(row.get('away_team', '')).strip()
            
            if not home_team or not away_team:
                skipped_data += 1
                continue
            
            # Get actual scores
            home_score = row.get('home_score', row.get('home_pts'))
            away_score = row.get('away_score', row.get('away_pts'))
            
            if pd.isna(home_score) or pd.isna(away_score):
                skipped_data += 1
                continue
            
            home_score = float(home_score)
            away_score = float(away_score)
            
            # Calculate actuals
            actual_spread = away_score - home_score  # Convention: spread is from home perspective
            actual_total = home_score + away_score
            
            # Get 1H scores if available
            h1_home = row.get('home_h1', row.get('h1_home'))
            h1_away = row.get('away_h1', row.get('h1_away'))
            
            # Find ratings
            home_rating = find_team_rating(home_team, season, all_ratings)
            away_rating = find_team_rating(away_team, season, all_ratings)
            
            if not home_rating or not away_rating:
                skipped_ratings += 1
                continue
            
            # Create TeamRatings objects
            home_ratings = create_team_ratings(home_rating)
            away_ratings = create_team_ratings(away_rating)
            
            if not home_ratings or not away_ratings:
                skipped_ratings += 1
                continue
            
            # Determine if neutral site
            is_neutral = row.get('is_neutral', False)
            if isinstance(is_neutral, str):
                is_neutral = is_neutral.lower() == 'true'
            
            # Run production model prediction
            pred = predictor.predict(
                home_ratings=home_ratings,
                away_ratings=away_ratings,
                is_neutral=is_neutral,
            )
            
            # Store results
            results['fg_spread']['predictions'].append(pred.spread)
            results['fg_spread']['actuals'].append(actual_spread)
            results['fg_total']['predictions'].append(pred.total)
            results['fg_total']['actuals'].append(actual_total)
            
            # 1H if available
            if not pd.isna(h1_home) and not pd.isna(h1_away):
                actual_h1_spread = float(h1_away) - float(h1_home)
                actual_h1_total = float(h1_home) + float(h1_away)
                results['h1_spread']['predictions'].append(pred.spread_1h)
                results['h1_spread']['actuals'].append(actual_h1_spread)
                results['h1_total']['predictions'].append(pred.total_1h)
                results['h1_total']['actuals'].append(actual_h1_total)
            
            matched += 1
            
        except Exception as e:
            skipped_data += 1
            continue
    
    print()
    print("=" * 80)
    print("BACKTEST RESULTS - PRODUCTION MODEL v33.1")
    print("=" * 80)
    print(f"Games matched: {matched}")
    print(f"Skipped (no ratings): {skipped_ratings}")
    print(f"Skipped (missing data): {skipped_data}")
    print()
    
    for market, data in results.items():
        if not data['predictions']:
            continue
        
        preds = np.array(data['predictions'])
        actuals = np.array(data['actuals'])
        
        errors = preds - actuals
        mae = np.mean(np.abs(errors))
        bias = np.mean(errors)
        rmse = np.sqrt(np.mean(errors**2))
        corr = np.corrcoef(preds, actuals)[0, 1] if len(preds) > 1 else 0
        
        print(f"{market.upper()}:")
        print(f"  Games: {len(preds)}")
        print(f"  MAE: {mae:.2f}")
        print(f"  Bias: {bias:+.2f}")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  Correlation: {corr:.3f}")
        print()
    
    # Betting simulation - CORRECTED LOGIC
    print("=" * 80)
    print("BETTING SIMULATION (5pt+ edge threshold)")
    print("=" * 80)
    
    fg_preds = np.array(results['fg_spread']['predictions'])
    fg_actuals = np.array(results['fg_spread']['actuals'])
    
    if len(fg_preds) > 0:
        # Simulate with assumed market line (rough estimate)
        # Our spread = -X means home favored by X
        # ATS Win: If we predict home wins by more than they actually do
        
        wins = 0
        losses = 0
        pushes = 0
        bets = 0
        
        for pred, actual in zip(fg_preds, fg_actuals):
            # Edge = how much better than 0 (pick'em) we think home will do
            edge = abs(pred)
            
            if edge >= 5.0:  # 5+ point edge
                bets += 1
                
                # If we predict home favored (pred < 0), we bet home
                # Home covers if actual < pred (they beat the spread)
                if pred < 0:  # We're betting home
                    if actual < pred:
                        wins += 1
                    elif actual > pred:
                        losses += 1
                    else:
                        pushes += 1
                else:  # pred > 0, we're betting away
                    if actual > pred:
                        wins += 1
                    elif actual < pred:
                        losses += 1
                    else:
                        pushes += 1
        
        if bets > 0:
            win_rate = wins / bets * 100
            roi = (wins * 0.91 - losses) / bets * 100  # -110 juice
            print(f"  Bets placed: {bets}")
            print(f"  Wins: {wins}, Losses: {losses}, Pushes: {pushes}")
            print(f"  Win Rate: {win_rate:.1f}%")
            print(f"  Est. ROI @ -110: {roi:+.1f}%")
    
    print()
    print("=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_backtest()
