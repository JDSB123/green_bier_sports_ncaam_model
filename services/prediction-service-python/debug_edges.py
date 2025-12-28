#!/usr/bin/env python3
"""Debug script to see actual edge values for today's games."""

import sys
from datetime import date
from sqlalchemy import create_engine

# Database connection
db_pass = open('/run/secrets/db_password').read().strip()
DATABASE_URL = f'postgresql://ncaam:{db_pass}@postgres:5432/ncaam'
engine = create_engine(DATABASE_URL)

# Fetch today's games and run predictions
from run_today import fetch_games_from_db, get_prediction

target_date = date.today()
games = fetch_games_from_db(target_date=target_date, engine=engine)

print(f"Found {len(games)} games for {target_date}")
print()
print("=== EDGE ANALYSIS (showing why picks pass/fail) ===")
print()

# Thresholds
FG_SPREAD_MIN = 2.0
FG_TOTAL_MIN = 3.0
H1_SPREAD_MIN = 3.5
H1_TOTAL_MIN = 2.0
MIN_CONFIDENCE = 0.65
FG_TOTAL_RANGE = (120.0, 170.0)
H1_TOTAL_RANGE = (55.0, 85.0)

for game in games[:15]:
    if not game.get('home_ratings') or not game.get('away_ratings'):
        print(f"{game.get('away', '?')} @ {game.get('home', '?')}: SKIPPED - missing ratings")
        continue
    if game.get('spread') is None and game.get('total') is None:
        print(f"{game.get('away', '?')} @ {game.get('home', '?')}: SKIPPED - missing odds")
        continue
    
    market_odds = {
        'spread': game.get('spread'),
        'total': game.get('total'),
        'spread_1h': game.get('spread_1h'),
        'total_1h': game.get('total_1h'),
    }
    
    try:
        result = get_prediction(
            home_team=game['home'],
            away_team=game['away'],
            home_ratings=game['home_ratings'],
            away_ratings=game['away_ratings'],
            market_odds=market_odds,
            is_neutral=game.get('is_neutral', False),
            game_id=game.get('game_id'),
            commence_time=game.get('commence_time'),
            engine=None,
            persist=False,
        )
        
        pred = result['prediction']
        recs = result['recommendations']
        
        away = game['away']
        home = game['home']
        print(f"{'='*60}")
        print(f"{away} @ {home}")
        print(f"{'='*60}")
        
        # FG Spread analysis
        fg_spread_edge = pred['spread_edge']
        fg_spread_conf = pred['spread_confidence']
        fg_spread_pass_edge = fg_spread_edge >= FG_SPREAD_MIN
        fg_spread_pass_conf = fg_spread_conf >= MIN_CONFIDENCE
        fg_spread_status = "PASS" if (fg_spread_pass_edge and fg_spread_pass_conf) else "FAIL"
        print(f"  FG Spread: edge={fg_spread_edge:.1f} (min={FG_SPREAD_MIN}) conf={fg_spread_conf:.2f} (min={MIN_CONFIDENCE}) -> {fg_spread_status}")
        if not fg_spread_pass_edge:
            print(f"    BLOCKED: edge {fg_spread_edge:.1f} < {FG_SPREAD_MIN}")
        if not fg_spread_pass_conf:
            print(f"    BLOCKED: conf {fg_spread_conf:.2f} < {MIN_CONFIDENCE}")
        
        # FG Total analysis
        fg_total = pred['predicted_total']
        fg_total_edge = pred['total_edge']
        fg_total_conf = pred['total_confidence']
        fg_total_in_range = FG_TOTAL_RANGE[0] <= fg_total <= FG_TOTAL_RANGE[1]
        fg_total_pass_edge = fg_total_edge >= FG_TOTAL_MIN
        fg_total_pass_conf = fg_total_conf >= MIN_CONFIDENCE
        fg_total_status = "PASS" if (fg_total_pass_edge and fg_total_pass_conf and fg_total_in_range) else "FAIL"
        print(f"  FG Total:  pred={fg_total:.1f} edge={fg_total_edge:.1f} (min={FG_TOTAL_MIN}) conf={fg_total_conf:.2f} -> {fg_total_status}")
        if not fg_total_in_range:
            print(f"    BLOCKED: pred {fg_total:.1f} outside range {FG_TOTAL_RANGE}")
        if not fg_total_pass_edge:
            print(f"    BLOCKED: edge {fg_total_edge:.1f} < {FG_TOTAL_MIN}")
        if not fg_total_pass_conf:
            print(f"    BLOCKED: conf {fg_total_conf:.2f} < {MIN_CONFIDENCE}")
        
        # 1H Spread analysis
        if game.get('spread_1h') is not None:
            h1_spread_edge = pred['spread_edge_1h']
            h1_spread_conf = pred['spread_confidence_1h']
            h1_spread_pass_edge = h1_spread_edge >= H1_SPREAD_MIN
            h1_spread_pass_conf = h1_spread_conf >= MIN_CONFIDENCE
            h1_spread_status = "PASS" if (h1_spread_pass_edge and h1_spread_pass_conf) else "FAIL"
            print(f"  1H Spread: edge={h1_spread_edge:.1f} (min={H1_SPREAD_MIN}) conf={h1_spread_conf:.2f} -> {h1_spread_status}")
            if not h1_spread_pass_edge:
                print(f"    BLOCKED: edge {h1_spread_edge:.1f} < {H1_SPREAD_MIN}")
            if not h1_spread_pass_conf:
                print(f"    BLOCKED: conf {h1_spread_conf:.2f} < {MIN_CONFIDENCE}")
        
        # 1H Total analysis
        if game.get('total_1h') is not None:
            h1_total = pred['predicted_total_1h']
            h1_total_edge = pred['total_edge_1h']
            h1_total_conf = pred['total_confidence_1h']
            h1_total_in_range = H1_TOTAL_RANGE[0] <= h1_total <= H1_TOTAL_RANGE[1]
            h1_total_pass_edge = h1_total_edge >= H1_TOTAL_MIN
            h1_total_pass_conf = h1_total_conf >= MIN_CONFIDENCE
            h1_total_status = "PASS" if (h1_total_pass_edge and h1_total_pass_conf and h1_total_in_range) else "FAIL"
            print(f"  1H Total:  pred={h1_total:.1f} edge={h1_total_edge:.1f} (min={H1_TOTAL_MIN}) conf={h1_total_conf:.2f} -> {h1_total_status}")
            if not h1_total_in_range:
                print(f"    BLOCKED: pred {h1_total:.1f} outside range {H1_TOTAL_RANGE}")
            if not h1_total_pass_edge:
                print(f"    BLOCKED: edge {h1_total_edge:.1f} < {H1_TOTAL_MIN}")
            if not h1_total_pass_conf:
                print(f"    BLOCKED: conf {h1_total_conf:.2f} < {MIN_CONFIDENCE}")
        
        print(f"  => Recommendations generated: {len(recs)}")
        print()
        
    except Exception as e:
        print(f"{game.get('away', '?')} @ {game.get('home', '?')}: ERROR - {e}")
        print()
