#!/usr/bin/env python3
"""
NCAAM Model Backtest with REAL ODDS

Uses actual historical odds from DraftKings/FanDuel - NOT assumed -110 juice.
This is the ONLY valid way to measure true betting ROI.

Data Sources:
- Game results: testing/data/historical/games_2024.csv (930 games)
- Odds data: testing/data/historical_odds/odds_combined_2024.csv (2,088 odds records)
- Barttorvik ratings: testing/data/historical/barttorvik_2024.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

import pandas as pd
import numpy as np

# Add prediction service to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "prediction-service-python"))

from app.predictor import BarttorvikPredictor
from app.models import TeamRatings


@dataclass
class BetResult:
    """Single bet result with actual odds."""
    game_id: str
    date: str
    home_team: str
    away_team: str
    market: str
    bet_side: str
    line: float
    prediction: float
    edge: float
    actual: float
    won: bool
    push: bool
    profit: float
    bookmaker: str


# Comprehensive mascot list for normalization
MASCOTS = [
    'golden griffins', 'blue devils', 'jayhawks', 'wildcats', 'wolverines',
    'buckeyes', 'spartans', 'hoosiers', 'boilermakers', 'stags', 'eagles',
    'bears', 'tigers', 'cardinals', 'bulldogs', 'huskies', 'bruins', 'trojans',
    'ducks', 'beavers', 'crimson', 'saints', 'purple eagles', 'seahawks',
    'skyhawks', 'golden eagles', 'dukes', 'musketeers', 'bearcats', 'blue jays',
    'friars', 'pirates', 'commodores', 'volunteers', 'gators', 'seminoles',
    'hurricanes', 'cavaliers', 'hokies', 'demon deacons', 'tar heels',
    'wolfpack', 'yellow jackets', 'orange', 'fighting irish', 'terrapins',
    'nittany lions', 'hawkeyes', 'cornhuskers', 'badgers', 'gophers',
    'illini', 'fighting illini', 'scarlet knights', 'mountaineers', 'red raiders',
    'horned frogs', 'longhorns', 'sooners', 'cyclones', 'cowboys', 'red storm',
    'bluejays', 'phoenix', 'braves', 'gaels', 'zags', 'toreros', 'aztecs',
    'dons', 'lions', 'waves', 'pilots', 'lumberjacks', 'antelopes', 'aggies',
    'miners', 'rebels', 'lobos', 'falcons', 'rams', 'buffaloes', 'utes',
    'cougars', 'sun devils', 'cardinal', 'owls', 'shockers', 'hilltoppers',
    'panthers', 'raiders', 'mean green', 'roadrunners', 'monarchs', 'flames',
    'thundering herd', 'golden flashes', 'rockets', 'chippewas', 'broncos',
    'redhawks', 'bobcats', 'zips', 'penguins', 'bulls', 'colonials', 'explorers',
    'hawks', 'jaspers', 'peacocks', 'bonnies', 'billikens', 'flyers', 'crusaders',
    'redbirds', 'sycamores', 'jaguars', 'leathernecks', 'mastodons', 'roos',
    'golden grizzlies', 'titans', 'norse', 'crimson tide', 'razorbacks',
    'gamecocks', 'big green', 'big red', 'great danes', 'seawolves', 'terriers',
    'catamounts', 'retrievers', 'blue hose', 'chanticleers', 'paladins',
    'keydets', 'midshipmen', 'black bears', 'river hawks', 'minutemen',
    'hawks', 'blue hens', 'spiders', 'tribe', 'phoenix', 'highlanders',
]


def normalize_team(name: str) -> str:
    """Normalize team name for matching."""
    if not name:
        return ""
    name = name.lower().strip()
    
    # Remove mascots
    for mascot in MASCOTS:
        if name.endswith(' ' + mascot):
            name = name[:-len(' ' + mascot)]
            break
    
    # Clean up
    name = name.replace('state', 'st').replace('-', ' ').replace("'", "").strip()
    return name


def teams_match(name1: str, name2: str) -> bool:
    """Check if two team names refer to the same team."""
    n1 = normalize_team(name1)
    n2 = normalize_team(name2)
    
    if not n1 or not n2:
        return False
    
    # Exact match
    if n1 == n2:
        return True
    
    # One contains the other
    if n1 in n2 or n2 in n1:
        return True
    
    return False


def load_barttorvik(year: int) -> Dict[str, Dict]:
    """Load Barttorvik ratings."""
    path = Path(__file__).parent.parent / "data" / "historical" / f"barttorvik_{year}.json"
    
    with open(path) as f:
        data = json.load(f)
    
    ratings = {}
    for row in data:
        if not isinstance(row, list) or len(row) < 10:
            continue
        
        team_name = str(row[1]).lower().strip()
        ratings[team_name] = {
            'team': row[1],
            'adj_o': float(row[4]),
            'adj_d': float(row[6]),
            'tempo': float(row[44]) if len(row) > 44 else 68.0,
            'orb': float(row[21]) if len(row) > 21 else 28.0,
            'drb': float(row[22]) if len(row) > 22 else 72.0,
        }
    
    return ratings


def find_rating(team_name: str, ratings: Dict) -> Optional[Dict]:
    """Find rating with fuzzy match."""
    lower = team_name.lower().strip()
    
    # Direct match
    if lower in ratings:
        return ratings[lower]
    
    # Normalized match
    normalized = normalize_team(team_name)
    for key, val in ratings.items():
        if normalized in key or key in normalized:
            return val
        key_norm = normalize_team(key)
        if normalized == key_norm or normalized in key_norm or key_norm in normalized:
            return val
    
    return None


def make_team_ratings(data: Dict) -> TeamRatings:
    """Create TeamRatings from dict."""
    return TeamRatings(
        team_name=data.get('team', 'Unknown'),
        adj_o=float(data['adj_o']),
        adj_d=float(data['adj_d']),
        tempo=float(data.get('tempo', 68.0)),
        rank=1,  # Not used in prediction
        efg=50.0,
        efgd=50.0,
        orb=float(data.get('orb', 28.0)),
        drb=float(data.get('drb', 72.0)),
        tor=18.0,
        tord=18.0,
        ftr=33.0,
        ftrd=33.0,
        two_pt_pct=50.0,
        two_pt_pct_d=50.0,
        three_pt_pct=34.0,
        three_pt_pct_d=34.0,
        three_pt_rate=35.0,
        three_pt_rate_d=35.0,
        barthag=0.5,
        wab=0.0,
    )


def calculate_profit(won: bool, push: bool, stake: float = 100.0) -> float:
    """Calculate profit at -110 odds."""
    if push:
        return 0.0
    return stake * 0.909 if won else -stake


def run_backtest():
    """Run backtest with real odds."""
    print("=" * 80)
    print("NCAAM MODEL BACKTEST - REAL ODDS")
    print("=" * 80)
    print()
    
    data_dir = Path(__file__).parent.parent / "data"
    
    # Load data
    games_df = pd.read_csv(data_dir / "historical" / "games_2024.csv")
    odds_df = pd.read_csv(data_dir / "historical_odds" / "odds_combined_2024.csv")
    ratings = load_barttorvik(2024)
    
    print(f"Games: {len(games_df)}")
    print(f"Odds records: {len(odds_df)}")
    print(f"Teams with ratings: {len(ratings)}")
    
    # Initialize predictor
    predictor = BarttorvikPredictor()
    print(f"\nProduction Model: HCA={predictor.hca_spread}, TotalCal={predictor.total_calibration}")
    print()
    
    # Prepare dataframes
    odds_df['date'] = pd.to_datetime(odds_df['commence_time']).dt.date.astype(str)
    games_df['date_str'] = pd.to_datetime(games_df['date']).dt.date.astype(str)
    
    # Dedup odds (one per game)
    odds_df = odds_df.sort_values(['event_id', 'bookmaker']).groupby('event_id').first().reset_index()
    
    # Match and predict
    results: List[BetResult] = []
    matched = 0
    no_game = 0
    no_rating = 0
    
    for _, orow in odds_df.iterrows():
        o_home = orow['home_team']
        o_away = orow['away_team']
        o_date = orow['date']
        market_spread = orow['spread']
        market_total = orow['total']
        
        if pd.isna(market_spread) or pd.isna(market_total):
            continue
        
        # Find matching game
        game = None
        for _, grow in games_df[games_df['date_str'] == o_date].iterrows():
            if teams_match(o_home, grow['home_team']) and teams_match(o_away, grow['away_team']):
                game = grow
                break
        
        if game is None:
            no_game += 1
            continue
        
        # Find ratings
        home_r = find_rating(game['home_team'], ratings)
        away_r = find_rating(game['away_team'], ratings)
        
        if not home_r or not away_r:
            no_rating += 1
            continue
        
        # Make prediction
        home_tr = make_team_ratings(home_r)
        away_tr = make_team_ratings(away_r)
        pred = predictor.predict(home_tr, away_tr, is_neutral=game.get('neutral', False))
        
        # Actual outcomes
        actual_spread = float(game['away_score']) - float(game['home_score'])
        actual_total = float(game['home_score']) + float(game['away_score'])
        
        # SPREAD bet
        spread_edge = abs(pred.spread - market_spread)
        if pred.spread < market_spread:
            bet_side = 'home'
            won = actual_spread < market_spread
        else:
            bet_side = 'away'
            won = actual_spread > market_spread
        push = abs(actual_spread - market_spread) < 0.5
        
        results.append(BetResult(
            game_id=str(game['game_id']),
            date=o_date,
            home_team=game['home_team'],
            away_team=game['away_team'],
            market='spread',
            bet_side=bet_side,
            line=market_spread,
            prediction=pred.spread,
            edge=spread_edge,
            actual=actual_spread,
            won=won and not push,
            push=push,
            profit=calculate_profit(won and not push, push),
            bookmaker=orow['bookmaker'],
        ))
        
        # TOTAL bet
        total_edge = abs(pred.total - market_total)
        if pred.total > market_total:
            bet_side = 'over'
            won = actual_total > market_total
        else:
            bet_side = 'under'
            won = actual_total < market_total
        push = abs(actual_total - market_total) < 0.5
        
        results.append(BetResult(
            game_id=str(game['game_id']),
            date=o_date,
            home_team=game['home_team'],
            away_team=game['away_team'],
            market='total',
            bet_side=bet_side,
            line=market_total,
            prediction=pred.total,
            edge=total_edge,
            actual=actual_total,
            won=won and not push,
            push=push,
            profit=calculate_profit(won and not push, push),
            bookmaker=orow['bookmaker'],
        ))
        
        matched += 1
    
    print(f"Matched games: {matched}")
    print(f"No game result: {no_game}")
    print(f"No ratings: {no_rating}")
    print()
    
    # Results by edge threshold
    print("=" * 80)
    print("BETTING PERFORMANCE BY EDGE THRESHOLD")
    print("=" * 80)
    
    for market in ['spread', 'total']:
        print(f"\n{'='*60}")
        print(f"{market.upper()}")
        print(f"{'='*60}")
        
        market_bets = [r for r in results if r.market == market]
        
        for min_edge in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15]:
            filtered = [b for b in market_bets if b.edge >= min_edge]
            if len(filtered) < 20:
                continue
            
            wins = sum(1 for b in filtered if b.won)
            losses = sum(1 for b in filtered if not b.won and not b.push)
            pushes = sum(1 for b in filtered if b.push)
            total_bets = wins + losses
            
            if total_bets == 0:
                continue
            
            win_rate = wins / total_bets * 100
            profit = sum(b.profit for b in filtered)
            roi = profit / (len(filtered) * 100) * 100
            
            # Z-score for significance
            z = (wins - total_bets * 0.5) / (total_bets * 0.25) ** 0.5 if total_bets > 0 else 0
            sig = "***" if z > 2.58 else "**" if z > 1.96 else "*" if z > 1.65 else ""
            
            print(f"Edge >= {min_edge:2d}: {len(filtered):4d} bets | "
                  f"{wins:3d}W-{losses:3d}L ({pushes}P) | "
                  f"{win_rate:5.1f}% | "
                  f"${profit:+7.0f} | "
                  f"ROI: {roi:+6.1f}% {sig}")
    
    # MAE Analysis
    print("\n" + "=" * 80)
    print("PREDICTION ACCURACY vs MARKET")
    print("=" * 80)
    
    for market in ['spread', 'total']:
        bets = [r for r in results if r.market == market]
        if not bets:
            continue
        
        model_errors = [b.prediction - b.actual for b in bets]
        market_errors = [b.line - b.actual for b in bets]
        
        model_mae = np.mean([abs(e) for e in model_errors])
        market_mae = np.mean([abs(e) for e in market_errors])
        bias = np.mean(model_errors)
        
        print(f"\n{market.upper()} ({len(bets)} games):")
        print(f"  Model MAE:  {model_mae:.2f}")
        print(f"  Market MAE: {market_mae:.2f}")
        print(f"  Difference: {model_mae - market_mae:+.2f} (- is better)")
        print(f"  Model Bias: {bias:+.2f}")
    
    # Optimal thresholds
    print("\n" + "=" * 80)
    print("OPTIMAL EDGE THRESHOLDS")
    print("=" * 80)
    
    for market in ['spread', 'total']:
        bets = [r for r in results if r.market == market]
        
        best_roi = -100
        best_edge = 0
        best_stats = {}
        
        for edge in range(0, 20):
            filtered = [b for b in bets if b.edge >= edge]
            if len(filtered) < 30:
                continue
            
            profit = sum(b.profit for b in filtered)
            roi = profit / (len(filtered) * 100) * 100
            
            if roi > best_roi:
                best_roi = roi
                best_edge = edge
                wins = sum(1 for b in filtered if b.won)
                losses = sum(1 for b in filtered if not b.won and not b.push)
                best_stats = {'bets': len(filtered), 'wins': wins, 'losses': losses}
        
        print(f"\n{market.upper()}: Optimal threshold = {best_edge} pts")
        if best_stats:
            win_rate = best_stats['wins'] / (best_stats['wins'] + best_stats['losses']) * 100
            print(f"  Bets: {best_stats['bets']}")
            print(f"  Record: {best_stats['wins']}-{best_stats['losses']}")
            print(f"  Win Rate: {win_rate:.1f}%")
            print(f"  ROI: {best_roi:+.1f}%")
    
    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_backtest()
