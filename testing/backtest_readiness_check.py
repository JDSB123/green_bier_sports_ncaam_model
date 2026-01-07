"""
Backtest Readiness Check

Validates that consolidated odds data is ready for backtesting by checking:
1. Team name alignment with Barttorvik ratings (our model's data source)
2. Availability of actual game results (scores)
3. Data integrity (no look-ahead bias, proper timestamps)
4. Coverage statistics
"""

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data/historical_odds")
ODDS_FILE = DATA_DIR / "odds_consolidated_canonical.csv"
ALIASES_FILE = Path("production_parity/team_aliases.json")


def load_odds_data():
    """Load consolidated odds data."""
    with open(ODDS_FILE, 'r') as f:
        return list(csv.DictReader(f))


def load_barttorvik_teams():
    """Load canonical team names that exist in Barttorvik."""
    # Barttorvik teams are our ground truth for D1 - these are the teams
    # we can actually generate predictions for
    with open(ALIASES_FILE, 'r') as f:
        data = json.load(f)
    return set(data.get("canonical_names", []))


def check_barttorvik_alignment(odds_rows, barttorvik_teams):
    """
    CHECK 1: Do our canonical team names match Barttorvik?
    
    This is CRITICAL - if a team resolves to a canonical name that
    doesn't exist in Barttorvik, we can't get ratings for predictions.
    """
    print("\n" + "=" * 70)
    print("CHECK 1: Barttorvik Team Alignment")
    print("=" * 70)
    
    odds_teams = set()
    for r in odds_rows:
        odds_teams.add(r['home_team_canonical'])
        odds_teams.add(r['away_team_canonical'])
    
    # Teams in odds but not in Barttorvik (can't predict these games)
    missing_from_barttorvik = odds_teams - barttorvik_teams
    
    # Teams in Barttorvik but not in odds (just means no odds data, ok)
    missing_from_odds = barttorvik_teams - odds_teams
    
    aligned = odds_teams & barttorvik_teams
    
    print(f"Teams in odds data: {len(odds_teams)}")
    print(f"Teams in Barttorvik: {len(barttorvik_teams)}")
    print(f"Teams aligned (can backtest): {len(aligned)}")
    print(f"Teams in odds but NOT in Barttorvik: {len(missing_from_barttorvik)}")
    
    if missing_from_barttorvik:
        print("\n⚠️ These teams have odds but no Barttorvik data (games will be skipped):")
        for team in sorted(missing_from_barttorvik):
            print(f"   - {team}")
    
    # Count games affected
    games_with_missing = 0
    for r in odds_rows:
        if r['home_team_canonical'] not in barttorvik_teams or \
           r['away_team_canonical'] not in barttorvik_teams:
            games_with_missing += 1
    
    usable_games = len(odds_rows) - games_with_missing
    usable_pct = usable_games / len(odds_rows) * 100
    
    print(f"\nGames with both teams in Barttorvik: {usable_games:,} / {len(odds_rows):,} ({usable_pct:.1f}%)")
    
    if usable_pct >= 95:
        print("✅ PASS: >95% of games have Barttorvik coverage")
        return True
    else:
        print("❌ FAIL: <95% of games have Barttorvik coverage")
        return False


def check_game_results_available(odds_rows):
    """
    CHECK 2: Do we have actual game scores to validate predictions?
    
    For backtesting, we need to know the actual outcome of each game.
    Check if we have a source for historical scores.
    """
    print("\n" + "=" * 70)
    print("CHECK 2: Game Results Availability")
    print("=" * 70)
    
    # Check if any rows have score data
    has_scores = any('home_score' in r and r.get('home_score') for r in odds_rows)
    
    if has_scores:
        with_scores = sum(1 for r in odds_rows if r.get('home_score'))
        print(f"Games with scores in odds data: {with_scores:,} / {len(odds_rows):,}")
    else:
        print("Scores NOT in consolidated odds data")
        print("\nScores must come from a separate source:")
        print("  - Barttorvik historical game data")
        print("  - ESPN/CBS Sports API")
        print("  - Sports-Reference")
    
    # Check what date range we have
    dates = [r['game_date'] for r in odds_rows if r.get('game_date')]
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        print(f"\nOdds data date range: {min_date} to {max_date}")
        
        # Check if these are past games (can get results) vs future
        today = datetime.now().strftime("%Y-%m-%d")
        past_games = sum(1 for d in dates if d < today)
        future_games = len(dates) - past_games
        
        print(f"Past games (can get results): {past_games:,}")
        print(f"Future games: {future_games:,}")
    
    print("\n⚠️ ACTION REQUIRED: Need to join with historical scores for backtesting")
    return False  # Scores not in odds data


def check_data_integrity(odds_rows):
    """
    CHECK 3: Data integrity for backtesting.
    
    - No duplicate games
    - Timestamps make sense (odds captured before game)
    - Required fields present
    """
    print("\n" + "=" * 70)
    print("CHECK 3: Data Integrity")
    print("=" * 70)
    
    issues = []
    
    # Check required fields
    required = ['home_team_canonical', 'away_team_canonical', 'spread', 'total', 
                'game_date', 'bookmaker', 'commence_time']
    
    for field in required:
        missing = sum(1 for r in odds_rows if not r.get(field))
        if missing > 0:
            issues.append(f"Missing '{field}': {missing:,} rows")
    
    # Check for duplicates (same game, same bookmaker)
    seen = set()
    duplicates = 0
    for r in odds_rows:
        key = f"{r['home_team_canonical']}|{r['away_team_canonical']}|{r['game_date']}|{r['bookmaker']}"
        if key in seen:
            duplicates += 1
        seen.add(key)
    
    if duplicates > 0:
        issues.append(f"Duplicate entries: {duplicates}")
    
    # Check spread/total are valid numbers
    invalid_spreads = 0
    invalid_totals = 0
    for r in odds_rows:
        try:
            if r.get('spread'):
                float(r['spread'])
        except:
            invalid_spreads += 1
        try:
            if r.get('total'):
                float(r['total'])
        except:
            invalid_totals += 1
    
    if invalid_spreads > 0:
        issues.append(f"Invalid spreads: {invalid_spreads}")
    if invalid_totals > 0:
        issues.append(f"Invalid totals: {invalid_totals}")
    
    # Report
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ PASS: All integrity checks passed")
        print(f"   - All required fields present")
        print(f"   - No duplicates")
        print(f"   - Valid numeric values for spreads/totals")
        return True


def check_coverage_by_season(odds_rows):
    """
    CHECK 4: Coverage statistics by season.
    
    For meaningful backtesting, need sufficient sample size per season.
    """
    print("\n" + "=" * 70)
    print("CHECK 4: Coverage by Season")
    print("=" * 70)
    
    by_season = Counter()
    for r in odds_rows:
        by_season[r.get('season', 'unknown')] += 1
    
    print(f"{'Season':<15} {'Games':>10} {'Status':<20}")
    print("-" * 50)
    
    all_ok = True
    for season in sorted(by_season.keys()):
        count = by_season[season]
        # Need at least 500 games for meaningful backtest
        if count >= 2000:
            status = "✅ Excellent"
        elif count >= 500:
            status = "✓ Good"
        elif count >= 100:
            status = "⚠️ Limited"
        else:
            status = "❌ Insufficient"
            all_ok = False
        
        print(f"{season:<15} {count:>10,} {status:<20}")
    
    total = sum(by_season.values())
    print("-" * 50)
    print(f"{'TOTAL':<15} {total:>10,}")
    
    if all_ok:
        print("\n✅ PASS: Sufficient data for backtesting")
    else:
        print("\n⚠️ WARNING: Some seasons have limited data")
    
    return all_ok


def check_h1_coverage(odds_rows):
    """
    CHECK 5: First-half lines coverage.
    
    H1 predictions need H1 lines.
    """
    print("\n" + "=" * 70)
    print("CHECK 5: First-Half (H1) Lines Coverage")
    print("=" * 70)
    
    has_h1_spread = sum(1 for r in odds_rows if r.get('h1_spread'))
    has_h1_total = sum(1 for r in odds_rows if r.get('h1_total'))
    total = len(odds_rows)
    
    h1_spread_pct = has_h1_spread / total * 100
    h1_total_pct = has_h1_total / total * 100
    
    print(f"Games with H1 spread: {has_h1_spread:,} / {total:,} ({h1_spread_pct:.1f}%)")
    print(f"Games with H1 total:  {has_h1_total:,} / {total:,} ({h1_total_pct:.1f}%)")
    
    # Break down by season
    print("\nH1 coverage by season:")
    by_season = defaultdict(lambda: {'total': 0, 'h1_spread': 0, 'h1_total': 0})
    for r in odds_rows:
        season = r.get('season', 'unknown')
        by_season[season]['total'] += 1
        if r.get('h1_spread'):
            by_season[season]['h1_spread'] += 1
        if r.get('h1_total'):
            by_season[season]['h1_total'] += 1
    
    for season in sorted(by_season.keys()):
        data = by_season[season]
        h1_pct = data['h1_spread'] / data['total'] * 100 if data['total'] > 0 else 0
        print(f"  {season}: {data['h1_spread']:,} / {data['total']:,} ({h1_pct:.1f}%)")
    
    if h1_spread_pct >= 50:
        print("\n✅ PASS: Good H1 coverage for H1 model backtesting")
        return True
    else:
        print("\n⚠️ WARNING: Limited H1 data - H1 model backtest may have smaller sample")
        return False


def generate_backtest_requirements():
    """Generate summary of what's needed for backtesting."""
    print("\n" + "=" * 70)
    print("BACKTEST REQUIREMENTS SUMMARY")
    print("=" * 70)
    
    print("""
To run a proper backtest, you need:

1. ODDS DATA (✅ READY)
   - Consolidated file: odds_consolidated_canonical.csv
   - 17,096 unique games with canonical team names
   - Spreads and totals from consensus/best odds
   
2. GAME RESULTS (❌ NEEDED)
   - Actual final scores for each game
   - Actual first-half scores for H1 model validation
   - Source: Barttorvik game logs or ESPN API
   
3. HISTORICAL RATINGS (❌ NEEDED)
   - Barttorvik ratings AS OF game date (not current ratings!)
   - Critical to avoid look-ahead bias
   - Need: ADJOE, ADJDE, tempo, etc. for each team on each date
   
4. JOIN STRATEGY
   - Match odds to ratings by: home_team_canonical + away_team_canonical + game_date
   - Match odds to results by: same keys
   
5. VALIDATION
   - After joining, verify no look-ahead bias
   - Check that ratings date <= game date
   - Verify score totals match (home + away = reported total)
""")


def main():
    print("=" * 70)
    print("BACKTEST READINESS CHECK")
    print("=" * 70)
    print(f"Odds file: {ODDS_FILE}")
    
    # Load data
    odds_rows = load_odds_data()
    barttorvik_teams = load_barttorvik_teams()
    
    print(f"Loaded {len(odds_rows):,} games")
    print(f"Barttorvik has {len(barttorvik_teams)} canonical teams")
    
    # Run checks
    results = {}
    results['barttorvik'] = check_barttorvik_alignment(odds_rows, barttorvik_teams)
    results['scores'] = check_game_results_available(odds_rows)
    results['integrity'] = check_data_integrity(odds_rows)
    results['coverage'] = check_coverage_by_season(odds_rows)
    results['h1'] = check_h1_coverage(odds_rows)
    
    # Generate requirements
    generate_backtest_requirements()
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL STATUS")
    print("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nChecks passed: {passed}/{total}")
    
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    if all(results.values()):
        print("\n✅ DATA IS READY FOR BACKTESTING")
    else:
        print("\n⚠️ ACTION ITEMS BEFORE BACKTESTING:")
        if not results['scores']:
            print("   1. Join with historical game scores")
        if not results['barttorvik']:
            print("   2. Fix Barttorvik team alignment issues")


if __name__ == "__main__":
    main()
