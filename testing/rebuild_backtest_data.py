"""
Rebuild backtest data using ALL available sources properly.

Sources:
1. training_data_with_odds.csv - 11,763 games with SCORES (2023-2025)
2. odds_consolidated_canonical.csv - 17,096 games with ODDS
3. h1_games_all.csv - 7,467 games with H1 scores
4. games_all.csv - 7,465 games with scores (2018-2026)
"""
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

# Add parent for team resolver
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

def load_team_resolver():
    """Load the canonical team name resolver."""
    resolver_path = os.path.join(ROOT, 'services/prediction-service-python/training_data/team_aliases_db.json')
    if os.path.exists(resolver_path):
        import json
        with open(resolver_path, 'r') as f:
            data = json.load(f)
        # JSON is {alias: canonical} format
        lookup = {}
        for alias, canonical in data.items():
            lookup[alias.lower().strip()] = canonical
            # Also add the canonical itself
            lookup[canonical.lower().strip()] = canonical
        return lookup
    return {}

def normalize_team(name, resolver):
    """Normalize team name to canonical form."""
    if not name:
        return name
    key = name.strip().lower()
    return resolver.get(key, name.strip())

def make_game_key(date, home, away):
    """Create unique game key."""
    return f"{date}|{home}|{away}"

print("=" * 70)
print("REBUILDING BACKTEST DATA FROM ALL SOURCES")
print("=" * 70)

# Load team resolver
resolver = load_team_resolver()
print(f"Loaded {len(resolver)} team name mappings")

# ========================================
# SOURCE 1: Training data (11,763 games with scores)
# ========================================
print("\n📊 Loading training data (games with scores)...")
training_path = os.path.join(ROOT, 'services/prediction-service-python/training_data/training_data_with_odds.csv')
with open(training_path, 'r', encoding='utf-8') as f:
    training_raw = list(csv.DictReader(f))

# Also load older games from games_all.csv
games_all_path = os.path.join(BASE, 'data/historical/games_all.csv')
with open(games_all_path, 'r', encoding='utf-8') as f:
    games_all_raw = list(csv.DictReader(f))

# Build score lookup: game_key -> {home_score, away_score}
scores = {}
for r in training_raw:
    date = r.get('game_date', '')[:10]
    home = normalize_team(r.get('home_team', ''), resolver)
    away = normalize_team(r.get('away_team', ''), resolver)
    key = make_game_key(date, home, away)
    
    try:
        home_score = int(float(r['home_score']))
        away_score = int(float(r['away_score']))
        scores[key] = {'home_score': home_score, 'away_score': away_score}
    except:
        pass

# Add older games
for r in games_all_raw:
    date = r.get('date', '')[:10]
    home = normalize_team(r.get('home_team', ''), resolver)
    away = normalize_team(r.get('away_team', ''), resolver)
    key = make_game_key(date, home, away)
    
    if key not in scores:
        try:
            home_score = int(float(r['home_score']))
            away_score = int(float(r['away_score']))
            scores[key] = {'home_score': home_score, 'away_score': away_score}
        except:
            pass

print(f"  Loaded {len(scores):,} unique games with scores")

# ========================================
# SOURCE 2: H1 scores
# ========================================
print("\n📊 Loading H1 scores...")
h1_path = os.path.join(BASE, 'data/h1_historical/h1_games_all.csv')
h1_scores = {}
if os.path.exists(h1_path):
    with open(h1_path, 'r', encoding='utf-8') as f:
        h1_raw = list(csv.DictReader(f))
    
    for r in h1_raw:
        date = r.get('date', '')[:10]
        home = normalize_team(r.get('home_team', ''), resolver)
        away = normalize_team(r.get('away_team', ''), resolver)
        key = make_game_key(date, home, away)
        
        try:
            h1_home = float(r.get('home_h1', 0))
            h1_away = float(r.get('away_h1', 0))
            if h1_home > 0 and h1_away > 0:
                h1_scores[key] = {'h1_home_score': h1_home, 'h1_away_score': h1_away}
        except:
            pass
    
    print(f"  Loaded {len(h1_scores):,} games with H1 scores")

# ========================================
# SOURCE 3: Consolidated odds (17,096 games)
# ========================================
print("\n📊 Loading consolidated odds...")
odds_path = os.path.join(BASE, 'data/historical_odds/odds_consolidated_canonical.csv')
with open(odds_path, 'r', encoding='utf-8') as f:
    odds_raw = list(csv.DictReader(f))

print(f"  Loaded {len(odds_raw):,} games with odds")

# ========================================
# MERGE: Create complete backtest dataset
# ========================================
print("\n🔗 Merging all sources...")

backtest_data = []
matched = 0
unmatched = 0
by_season = defaultdict(lambda: {'total': 0, 'matched': 0})

for r in odds_raw:
    # Parse odds data
    date = r.get('game_date', r.get('commence_time', ''))[:10]
    # Use raw team names and normalize with OUR resolver - not the pre-computed canonical
    home = r.get('home_team', '')
    away = r.get('away_team', '')
    
    # Normalize
    home = normalize_team(home, resolver)
    away = normalize_team(away, resolver)
    
    key = make_game_key(date, home, away)
    
    # Season tracking
    if date:
        yr = int(date[:4])
        mo = int(date[5:7])
        season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
        by_season[season]['total'] += 1
    
    # Get odds
    try:
        spread = float(r.get('spread', 0)) if r.get('spread') else None
    except:
        spread = None
    
    try:
        total = float(r.get('total', 0)) if r.get('total') else None
    except:
        total = None
    
    try:
        h1_spread = float(r.get('h1_spread', 0)) if r.get('h1_spread') else None
    except:
        h1_spread = None
    
    try:
        h1_total = float(r.get('h1_total', 0)) if r.get('h1_total') else None
    except:
        h1_total = None
    
    # Look up scores (try both normal and swapped home/away)
    swapped_key = make_game_key(date, away, home)
    score_data = None
    was_swapped = False
    
    if key in scores:
        score_data = scores[key]
    elif swapped_key in scores:
        score_data = scores[swapped_key]
        was_swapped = True
    
    if score_data:
        matched += 1
        by_season[season]['matched'] += 1
        
        # Get H1 data (try both key orders)
        h1_data = h1_scores.get(key, {}) or h1_scores.get(swapped_key, {})
        
        # If home/away were swapped, we need to swap the scores back
        if was_swapped:
            home_score = score_data['away_score']
            away_score = score_data['home_score']
        else:
            home_score = score_data['home_score']
            away_score = score_data['away_score']
        
        # Calculate results
        spread_result = away_score - home_score  # positive = away won by X
        actual_total = home_score + away_score
        home_covered = spread_result < spread if spread else None
        went_over = actual_total > total if total else None
        
        # H1 calculations (also swap if needed)
        h1_home_raw = h1_data.get('h1_home_score')
        h1_away_raw = h1_data.get('h1_away_score')
        if was_swapped and h1_home_raw and h1_away_raw:
            h1_home = h1_away_raw
            h1_away = h1_home_raw
        else:
            h1_home = h1_home_raw
            h1_away = h1_away_raw
        h1_spread_result = (h1_away - h1_home) if (h1_home and h1_away) else None
        h1_total_result = (h1_home + h1_away) if (h1_home and h1_away) else None
        
        row = {
            'game_date': date,
            'home_team': home,
            'away_team': away,
            'spread': spread,
            'total': total,
            'h1_spread': h1_spread,
            'h1_total': h1_total,
            'home_score': home_score,
            'away_score': away_score,
            'spread_result': spread_result,
            'actual_total': actual_total,
            'home_covered': home_covered,
            'went_over': went_over,
            'h1_home_score': h1_home,
            'h1_away_score': h1_away,
            'h1_spread_result': h1_spread_result,
            'h1_actual_total': h1_total_result,
        }
        backtest_data.append(row)
    else:
        unmatched += 1

# ========================================
# ALSO: Add games from training data that have scores but aren't in odds
# We can still validate model predictions even without odds
# ========================================
print("\n📊 Checking for additional games in training data without odds...")
games_with_scores_only = 0
for r in training_raw:
    date = r.get('game_date', '')[:10]
    home = normalize_team(r.get('home_team', ''), resolver)
    away = normalize_team(r.get('away_team', ''), resolver)
    key = make_game_key(date, home, away)
    
    # Check if already in backtest_data
    already_have = any(
        g['game_date'] == date and g['home_team'] == home and g['away_team'] == away
        for g in backtest_data
    )
    
    if not already_have and key in scores:
        games_with_scores_only += 1
        score_data = scores[key]
        h1_data = h1_scores.get(key, {})
        
        row = {
            'game_date': date,
            'home_team': home,
            'away_team': away,
            'spread': None,
            'total': None,
            'h1_spread': None,
            'h1_total': None,
            'home_score': score_data['home_score'],
            'away_score': score_data['away_score'],
            'spread_result': score_data['away_score'] - score_data['home_score'],
            'actual_total': score_data['home_score'] + score_data['away_score'],
            'home_covered': None,
            'went_over': None,
            'h1_home_score': h1_data.get('h1_home_score'),
            'h1_away_score': h1_data.get('h1_away_score'),
            'h1_spread_result': None,
            'h1_actual_total': None,
        }
        backtest_data.append(row)

print(f"  Added {games_with_scores_only:,} games with scores but no odds")

# Sort by date
backtest_data.sort(key=lambda x: x['game_date'])

# ========================================
# OUTPUT
# ========================================
output_path = os.path.join(BASE, 'data/backtest_complete.csv')
fieldnames = [
    'game_date', 'home_team', 'away_team',
    'spread', 'total', 'h1_spread', 'h1_total',
    'home_score', 'away_score', 'spread_result', 'actual_total',
    'home_covered', 'went_over',
    'h1_home_score', 'h1_away_score', 'h1_spread_result', 'h1_actual_total'
]

with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(backtest_data)

print(f"\n✅ Wrote {len(backtest_data):,} games to {output_path}")

# ========================================
# SUMMARY
# ========================================
print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

# Count games with odds
with_odds = sum(1 for g in backtest_data if g['spread'] is not None)
with_scores = sum(1 for g in backtest_data if g['home_score'] is not None)
with_h1 = sum(1 for g in backtest_data if g['h1_home_score'] is not None)

print(f"\nTotal games: {len(backtest_data):,}")
print(f"  With odds (spread): {with_odds:,}")
print(f"  With scores: {with_scores:,}")
print(f"  With H1 scores: {with_h1:,}")

print("\nBy Season:")
# Recalculate by season for final data
final_seasons = defaultdict(lambda: {'total': 0, 'with_odds': 0, 'with_h1': 0})
for g in backtest_data:
    date = g['game_date']
    yr = int(date[:4])
    mo = int(date[5:7])
    season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
    final_seasons[season]['total'] += 1
    if g['spread']:
        final_seasons[season]['with_odds'] += 1
    if g['h1_home_score']:
        final_seasons[season]['with_h1'] += 1

for s in sorted(final_seasons.keys()):
    d = final_seasons[s]
    odds_pct = 100 * d['with_odds'] / d['total'] if d['total'] else 0
    h1_pct = 100 * d['with_h1'] / d['total'] if d['total'] else 0
    status = "🟢" if odds_pct > 50 else "🟡" if odds_pct > 10 else "🔴"
    print(f"  {status} {s}: {d['total']:,} games, {d['with_odds']:,} with odds ({odds_pct:.0f}%), {d['with_h1']:,} with H1 ({h1_pct:.0f}%)")

print("\nMatch rate from odds to scores:")
print(f"  {matched:,}/{matched+unmatched:,} ({100*matched/(matched+unmatched):.1f}%)")
