"""Complete data integrity disaster report."""
import csv
import os
from collections import defaultdict

base = 'data'

print("=" * 60)
print("DATA INTEGRITY DISASTER REPORT")
print("=" * 60)

# 1. Consolidated odds
odds_file = 'data/historical_odds/odds_consolidated_canonical.csv'
if os.path.exists(odds_file):
    with open(odds_file, 'r') as f:
        odds = list(csv.DictReader(f))
    print(f"\n📊 CONSOLIDATED ODDS: {len(odds):,} games")
    
    # By season
    by_season = defaultdict(int)
    for r in odds:
        date = r.get('game_date', r.get('commence_time', ''))[:10]
        if date:
            yr = int(date[:4])
            mo = int(date[5:7]) if len(date) >= 7 else 1
            season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
            by_season[season] += 1
    
    print("  By Season:")
    for s in sorted(by_season.keys()):
        print(f"    {s}: {by_season[s]:,}")
else:
    print(f"❌ NO CONSOLIDATED ODDS FILE: {odds_file}")
    odds = []

# 2. Score data
print(f"\n📊 SCORE DATA:")
games_all = 'data/historical/games_all.csv'
if os.path.exists(games_all):
    with open(games_all, 'r') as f:
        reader = csv.DictReader(f)
        scores = list(reader)
    print(f"  Total: {len(scores):,} games in games_all.csv")
    
    # Check what columns exist
    if scores:
        print(f"  Columns: {list(scores[0].keys())[:8]}...")
        
    # By season
    score_seasons = defaultdict(int)
    for r in scores:
        date = r.get('date', r.get('game_date', ''))[:10]
        if date:
            try:
                yr = int(date[:4])
                mo = int(date[5:7]) if len(date) >= 7 else 1
                season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
                score_seasons[season] += 1
            except:
                pass
    
    print("  By Season:")
    for s in sorted(score_seasons.keys()):
        print(f"    {s}: {score_seasons[s]:,}")
else:
    print(f"  ❌ NO games_all.csv")
    scores = []

# 3. Backtest ready
print(f"\n📊 BACKTEST READY (merged):")
bt_file = 'data/backtest_ready.csv'
if os.path.exists(bt_file):
    with open(bt_file, 'r') as f:
        bt = list(csv.DictReader(f))
    print(f"  Total: {len(bt):,} games")
    
    bt_seasons = defaultdict(int)
    for r in bt:
        date = r.get('game_date', '')[:10]
        if date:
            yr = int(date[:4])
            mo = int(date[5:7])
            season = f"{yr}-{yr+1}" if mo >= 8 else f"{yr-1}-{yr}"
            bt_seasons[season] += 1
    
    print("  By Season:")
    for s in sorted(bt_seasons.keys()):
        print(f"    {s}: {bt_seasons[s]:,}")
else:
    print(f"  ❌ NO backtest_ready.csv")
    bt = []

# 4. The real problem
print("\n" + "=" * 60)
print("🚨 THE REAL PROBLEMS")
print("=" * 60)

if odds and bt:
    coverage = 100 * len(bt) / len(odds)
    print(f"\n1. COVERAGE: Only {coverage:.1f}% of odds have matching scores")
    print(f"   - {len(odds):,} odds games")
    print(f"   - {len(bt):,} matched with scores")
    print(f"   - {len(odds) - len(bt):,} games MISSING scores")

if odds:
    # Check which seasons have zero backtest coverage
    print(f"\n2. SEASON GAPS:")
    for s in sorted(by_season.keys()):
        bt_count = bt_seasons.get(s, 0)
        odds_count = by_season[s]
        pct = 100 * bt_count / odds_count if odds_count else 0
        status = "🔴" if bt_count == 0 else "🟡" if pct < 50 else "🟢"
        print(f"   {status} {s}: {bt_count:,}/{odds_count:,} ({pct:.0f}%)")

# 5. Data quality issues
print(f"\n3. DATA QUALITY:")
if bt:
    # Check for missing spreads
    missing_spread = sum(1 for r in bt if not r.get('spread'))
    missing_total = sum(1 for r in bt if not r.get('total'))
    missing_home = sum(1 for r in bt if not r.get('home_score'))
    missing_away = sum(1 for r in bt if not r.get('away_score'))
    
    print(f"   Missing spread: {missing_spread:,}")
    print(f"   Missing total: {missing_total:,}")
    print(f"   Missing home_score: {missing_home:,}")
    print(f"   Missing away_score: {missing_away:,}")

# 6. What we'd need for proper backtest
print("\n" + "=" * 60)
print("📋 WHAT'S NEEDED FOR PROPER BACKTEST")
print("=" * 60)
print("""
For a statistically valid backtest, you need:
- At least 1,000+ games (ideally 3,000+)
- Multiple seasons (to avoid overfitting to one year)
- Complete coverage (not just major conferences)
- Consistent data quality across all games

Current state:
""")

if odds:
    total_seasons = len(by_season)
    usable_seasons = sum(1 for s in by_season if bt_seasons.get(s, 0) > 100)
    print(f"  Seasons with data: {total_seasons}")
    print(f"  Seasons USABLE (>100 games): {usable_seasons}")
    print(f"  Total usable games: {len(bt):,}")
    
    if len(bt) >= 2000 and usable_seasons >= 2:
        print("\n  ✅ MINIMUM viable for backtest (but not ideal)")
    else:
        print("\n  ❌ NOT ENOUGH DATA for reliable backtest")

print("\n" + "=" * 60)
print("🔧 OPTIONS TO FIX")
print("=" * 60)
print("""
Option 1: Get complete score data
  - Source: Sports-Reference, ESPN API, or Kaggle datasets
  - Need: ALL D1 games, not just major conferences
  
Option 2: Use odds-only validation
  - CLV (Closing Line Value) analysis
  - Doesn't require game scores
  - Can validate edge detection

Option 3: Scrape historical scores
  - ESPN game results
  - Sports-Reference box scores
  - Would need to build scraper
""")
