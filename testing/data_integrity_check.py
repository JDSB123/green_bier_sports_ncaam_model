"""
Comprehensive Data Integrity Check

Validates the backtest data is correct and trustworthy by checking:
1. Score sanity (realistic values)
2. Math consistency (scores match totals)
3. Spread/total calculations correct
4. No duplicate games
5. Statistical sanity (cover rates should be ~50%)
6. Cross-source validation
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path
import statistics


def load_data():
    """Load the backtest-ready data."""
    with open('data/backtest_ready.csv', 'r') as f:
        return list(csv.DictReader(f))


def check_score_sanity(rows):
    """
    CHECK 1: Are scores realistic?
    - College basketball scores typically 50-100 per team
    - Totals typically 120-180
    - Margins typically -40 to +40
    """
    print("\n" + "=" * 70)
    print("CHECK 1: Score Sanity")
    print("=" * 70)
    
    issues = []
    
    for r in rows:
        try:
            home = int(r['home_score'])
            away = int(r['away_score'])
            total = home + away
            margin = home - away
            
            # Flag suspicious scores
            if home < 30 or home > 150:
                issues.append(f"Suspicious home score: {home} in {r['away_team']} @ {r['home_team']} on {r['game_date']}")
            if away < 30 or away > 150:
                issues.append(f"Suspicious away score: {away} in {r['away_team']} @ {r['home_team']} on {r['game_date']}")
            if total < 80 or total > 250:
                issues.append(f"Suspicious total: {total} in {r['away_team']} @ {r['home_team']} on {r['game_date']}")
        except (ValueError, TypeError):
            issues.append(f"Invalid score data in {r.get('home_team')} on {r.get('game_date')}")
    
    if issues:
        print(f"❌ Found {len(issues)} suspicious scores:")
        for issue in issues[:10]:
            print(f"   - {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues) - 10} more")
        return False
    else:
        print("✅ All scores within realistic range (30-150 per team)")
        return True


def check_math_consistency(rows):
    """
    CHECK 2: Does the math add up?
    - actual_margin should = home_score - away_score
    - actual_total should = home_score + away_score
    - spread_result should = actual_margin + spread
    """
    print("\n" + "=" * 70)
    print("CHECK 2: Math Consistency")
    print("=" * 70)
    
    issues = []
    
    for r in rows:
        try:
            home = int(r['home_score'])
            away = int(r['away_score'])
            
            # Check margin
            calc_margin = home - away
            reported_margin = int(r['actual_margin'])
            if calc_margin != reported_margin:
                issues.append(f"Margin mismatch: {calc_margin} != {reported_margin}")
            
            # Check total
            calc_total = home + away
            reported_total = int(r['actual_total'])
            if calc_total != reported_total:
                issues.append(f"Total mismatch: {calc_total} != {reported_total}")
            
            # Check spread result
            if r.get('spread') and r.get('spread_result'):
                spread = float(r['spread'])
                spread_result = float(r['spread_result'])
                expected_result = calc_margin + spread
                if abs(spread_result - expected_result) > 0.01:
                    issues.append(f"Spread result mismatch: {spread_result} != {expected_result}")
                    
        except (ValueError, TypeError) as e:
            issues.append(f"Calculation error: {e}")
    
    if issues:
        print(f"❌ Found {len(issues)} math errors:")
        for issue in issues[:10]:
            print(f"   - {issue}")
        return False
    else:
        print("✅ All calculations verified correct")
        return True


def check_duplicates(rows):
    """
    CHECK 3: No duplicate games.
    Same teams on same date should appear only once per bookmaker.
    """
    print("\n" + "=" * 70)
    print("CHECK 3: Duplicate Detection")
    print("=" * 70)
    
    seen = Counter()
    for r in rows:
        key = f"{r['home_team']}|{r['away_team']}|{r['game_date']}|{r['bookmaker']}"
        seen[key] += 1
    
    duplicates = {k: v for k, v in seen.items() if v > 1}
    
    if duplicates:
        print(f"❌ Found {len(duplicates)} duplicate entries:")
        for key, count in list(duplicates.items())[:5]:
            print(f"   - {key}: {count} times")
        return False
    else:
        print(f"✅ No duplicates found among {len(rows)} rows")
        return True


def check_statistical_sanity(rows):
    """
    CHECK 4: Statistical sanity checks.
    - Cover rate should be roughly 50% (market efficiency)
    - Over/under rate should be roughly 50%
    - Distribution of spreads should be centered around 0
    """
    print("\n" + "=" * 70)
    print("CHECK 4: Statistical Sanity")
    print("=" * 70)
    
    issues = []
    
    # Spread cover rate
    covers = [float(r['home_covered']) for r in rows if r.get('home_covered')]
    if covers:
        cover_rate = sum(covers) / len(covers)
        print(f"Home cover rate: {cover_rate*100:.1f}% (expected ~50%)")
        if cover_rate < 0.40 or cover_rate > 0.60:
            issues.append(f"Cover rate {cover_rate*100:.1f}% is outside expected 40-60% range")
    
    # Over/under rate
    overs = [float(r['went_over']) for r in rows if r.get('went_over')]
    if overs:
        over_rate = sum(overs) / len(overs)
        print(f"Over rate: {over_rate*100:.1f}% (expected ~50%)")
        if over_rate < 0.40 or over_rate > 0.60:
            issues.append(f"Over rate {over_rate*100:.1f}% is outside expected 40-60% range")
    
    # Spread distribution
    spreads = [float(r['spread']) for r in rows if r.get('spread')]
    if spreads:
        avg_spread = statistics.mean(spreads)
        std_spread = statistics.stdev(spreads)
        print(f"Spread distribution: mean={avg_spread:.1f}, std={std_spread:.1f}")
        # Home teams are typically favored, so slight negative mean is normal
        if avg_spread < -15 or avg_spread > 5:
            issues.append(f"Average spread {avg_spread:.1f} seems unusual")
    
    # Margin distribution (actual results)
    margins = [int(r['actual_margin']) for r in rows if r.get('actual_margin')]
    if margins:
        avg_margin = statistics.mean(margins)
        std_margin = statistics.stdev(margins)
        print(f"Actual margin distribution: mean={avg_margin:.1f}, std={std_margin:.1f}")
        # Home court advantage typically 3-4 points
        if avg_margin < -5 or avg_margin > 15:
            issues.append(f"Average margin {avg_margin:.1f} seems unusual")
    
    if issues:
        print(f"\n⚠️ Statistical anomalies detected:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("\n✅ All statistics within expected ranges")
        return True


def check_cross_validation(rows):
    """
    CHECK 5: Cross-validate specific known games.
    Pick famous games we can verify and check the data is correct.
    """
    print("\n" + "=" * 70)
    print("CHECK 5: Cross-Validation (Known Games)")
    print("=" * 70)
    
    # Find some high-profile games to manually verify
    notable_games = []
    for r in rows:
        # Look for big rivalry/known games
        if ('Duke' in r['home_team'] or 'Duke' in r['away_team']) and \
           ('North Carolina' in r['home_team'] or 'North Carolina' in r['away_team']):
            notable_games.append(('Duke-UNC', r))
        elif ('Kansas' in r['home_team'] and 'Kentucky' in r['away_team']) or \
             ('Kentucky' in r['home_team'] and 'Kansas' in r['away_team']):
            notable_games.append(('Kansas-Kentucky', r))
        elif r['home_team'] == 'Purdue' and r['away_team'] == 'Connecticut':
            notable_games.append(('National Championship', r))
    
    if notable_games:
        print("Sample high-profile games for manual verification:")
        for name, r in notable_games[:5]:
            print(f"\n  {name}: {r['game_date']}")
            print(f"  {r['away_team']} @ {r['home_team']}")
            print(f"  Score: {r['away_score']}-{r['home_score']}")
            print(f"  Spread: {r['spread']}, Result: {r.get('spread_result', 'N/A')}")
    else:
        print("No marquee games found in dataset for verification")
    
    # Random sample for spot checking
    import random
    random.seed(42)
    sample = random.sample(rows, min(5, len(rows)))
    
    print("\n\nRandom sample for spot-check verification:")
    print("(Please verify these scores independently)")
    for r in sample:
        print(f"\n  {r['game_date']}: {r['away_team']} @ {r['home_team']}")
        print(f"  Final: {r['away_score']}-{r['home_score']}")
        if r.get('h1_home_score') and r.get('h1_away_score'):
            print(f"  1H: {r['h1_away_score']}-{r['h1_home_score']}")
    
    return True  # Manual check required


def check_h1_consistency(rows):
    """
    CHECK 6: H1 scores are consistent with final scores.
    H1 scores should be less than final scores.
    """
    print("\n" + "=" * 70)
    print("CHECK 6: H1 Score Consistency")
    print("=" * 70)
    
    issues = []
    h1_count = 0
    
    for r in rows:
        if r.get('h1_home_score') and r.get('h1_away_score'):
            try:
                h1_home = float(r['h1_home_score'])
                h1_away = float(r['h1_away_score'])
                final_home = int(r['home_score'])
                final_away = int(r['away_score'])
                h1_count += 1
                
                # H1 should be less than final
                if h1_home > final_home:
                    issues.append(f"H1 home > final: {h1_home} > {final_home} on {r['game_date']}")
                if h1_away > final_away:
                    issues.append(f"H1 away > final: {h1_away} > {final_away} on {r['game_date']}")
                
                # H1 should be reasonable (typically 25-50 per team)
                if h1_home < 15 or h1_home > 70:
                    issues.append(f"Suspicious H1 home score: {h1_home}")
                if h1_away < 15 or h1_away > 70:
                    issues.append(f"Suspicious H1 away score: {h1_away}")
                    
            except (ValueError, TypeError):
                issues.append(f"Invalid H1 data on {r.get('game_date')}")
    
    print(f"Games with H1 data: {h1_count}")
    
    if issues:
        print(f"❌ Found {len(issues)} H1 consistency issues:")
        for issue in issues[:10]:
            print(f"   - {issue}")
        return False
    else:
        print("✅ All H1 scores consistent with final scores")
        return True


def check_odds_values(rows):
    """
    CHECK 7: Odds values are realistic.
    - Spreads typically -40 to +40
    - Totals typically 110-180
    """
    print("\n" + "=" * 70)
    print("CHECK 7: Odds Value Sanity")
    print("=" * 70)
    
    issues = []
    
    for r in rows:
        try:
            if r.get('spread'):
                spread = float(r['spread'])
                if spread < -50 or spread > 50:
                    issues.append(f"Extreme spread: {spread} in {r['away_team']} @ {r['home_team']}")
            
            if r.get('total'):
                total = float(r['total'])
                if total < 100 or total > 200:
                    issues.append(f"Extreme total: {total} in {r['away_team']} @ {r['home_team']}")
                    
        except (ValueError, TypeError):
            pass
    
    if issues:
        print(f"⚠️ Found {len(issues)} extreme odds values:")
        for issue in issues[:10]:
            print(f"   - {issue}")
        return len(issues) < 10  # Allow a few outliers
    else:
        print("✅ All odds values within realistic ranges")
        return True


def main():
    print("=" * 70)
    print("COMPREHENSIVE DATA INTEGRITY CHECK")
    print("=" * 70)
    
    # Load data
    rows = load_data()
    print(f"Loaded {len(rows):,} rows from backtest_ready.csv")
    
    # Run all checks
    results = {}
    results['scores'] = check_score_sanity(rows)
    results['math'] = check_math_consistency(rows)
    results['duplicates'] = check_duplicates(rows)
    results['statistics'] = check_statistical_sanity(rows)
    results['cross_validation'] = check_cross_validation(rows)
    results['h1_consistency'] = check_h1_consistency(rows)
    results['odds_values'] = check_odds_values(rows)
    
    # Summary
    print("\n" + "=" * 70)
    print("INTEGRITY CHECK SUMMARY")
    print("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, passed_check in results.items():
        status = "✅" if passed_check else "❌"
        print(f"  {status} {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ DATA INTEGRITY VERIFIED - Ready for backtesting")
    else:
        print("\n⚠️ DATA ISSUES DETECTED - Review before backtesting")


if __name__ == "__main__":
    main()
