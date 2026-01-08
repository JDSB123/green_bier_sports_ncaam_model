"""
TEAM CANONICALIZATION VALIDATION SCRIPT

This script validates that team names can be correctly matched between:
- The Odds API data (odds)
- ESPN Scoreboard data (scores)
- Barttorvik ratings

WITHOUT CORRECT CANONICALIZATION, BACKTESTING IS INVALID!

Usage:
    python testing/scripts/validate_team_canonicalization.py
"""

import pandas as pd
import json
from pathlib import Path
from collections import defaultdict
from difflib import get_close_matches
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from testing.data_paths import DATA_PATHS


def load_all_team_names():
    """Load team names from all data sources."""
    
    teams = {
        'odds_api': set(),      # The Odds API
        'espn': set(),          # ESPN Scoreboard (scores)
        'barttorvik': set(),    # Barttorvik ratings
    }
    
    # Load odds data
    spreads_file = DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv"
    if spreads_file.exists():
        df = pd.read_csv(spreads_file)
        teams['odds_api'] = set(df['home_team_canonical'].dropna().unique()) | \
                            set(df['away_team_canonical'].dropna().unique())
    
    # Load scores data
    scores_file = DATA_PATHS.scores_fg / "games_all.csv"
    if scores_file.exists():
        df = pd.read_csv(scores_file)
        teams['espn'] = set(df['home_team'].dropna().unique()) | \
                        set(df['away_team'].dropna().unique())
    
    # Load Barttorvik ratings (format: list of lists, team name at index 1)
    for json_file in DATA_PATHS.ratings_raw_barttorvik.glob("barttorvik_*.json"):
        with open(json_file) as f:
            data = json.load(f)
            for row in data:
                if isinstance(row, list) and len(row) > 1:
                    teams['barttorvik'].add(str(row[1]))
    
    return teams


def find_exact_matches(teams):
    """Find teams that match exactly across sources."""
    odds = teams['odds_api']
    espn = teams['espn']
    barttorvik = teams['barttorvik']
    
    return {
        'odds_espn': odds & espn,
        'odds_barttorvik': odds & barttorvik,
        'espn_barttorvik': espn & barttorvik,
        'all_three': odds & espn & barttorvik,
    }


def analyze_name_patterns(teams):
    """Analyze naming patterns in each source."""
    patterns = {}
    
    for source, team_set in teams.items():
        has_mascot = []
        no_mascot = []
        
        for team in team_set:
            words = team.split()
            # ESPN typically has mascots (2+ words)
            if len(words) >= 2:
                has_mascot.append(team)
            else:
                no_mascot.append(team)
        
        patterns[source] = {
            'total': len(team_set),
            'multi_word': len(has_mascot),
            'single_word': len(no_mascot),
            'sample_multi': sorted(has_mascot)[:5],
            'sample_single': sorted(no_mascot)[:5],
        }
    
    return patterns


def find_probable_matches(odds_teams, espn_teams):
    """Use fuzzy matching to find probable mappings."""
    
    mappings = {
        'high_confidence': [],   # Same first word, close match
        'medium_confidence': [], # Different first word but close match
        'no_match': [],         # No reasonable match found
    }
    
    for odds_team in sorted(odds_teams):
        matches = get_close_matches(odds_team, espn_teams, n=3, cutoff=0.4)
        
        if not matches:
            mappings['no_match'].append({
                'odds': odds_team,
                'espn': None,
                'issue': 'No fuzzy match found'
            })
            continue
        
        best_match = matches[0]
        odds_first = odds_team.split()[0].lower()
        espn_first = best_match.split()[0].lower()
        
        # Check if first word matches (high confidence)
        if odds_first == espn_first or odds_first.startswith(espn_first) or espn_first.startswith(odds_first):
            mappings['high_confidence'].append({
                'odds': odds_team,
                'espn': best_match,
                'alternatives': matches[1:] if len(matches) > 1 else []
            })
        else:
            # Potential mismatch - needs review
            mappings['medium_confidence'].append({
                'odds': odds_team,
                'espn': best_match,
                'alternatives': matches[1:] if len(matches) > 1 else [],
                'issue': f'First word mismatch: {odds_first} vs {espn_first}'
            })
    
    return mappings


def check_known_problem_pairs():
    """Check for known problematic team name pairs."""
    
    # Teams that are commonly confused
    problem_pairs = [
        # State vs flagship
        ("Alabama", "Alabama St."),
        ("Arizona", "Arizona St."),
        ("Mississippi", "Mississippi St."),
        ("Georgia", "Georgia St."),
        ("Texas", "Texas St."),
        ("Florida", "Florida St."),
        ("Michigan", "Michigan St."),
        ("Ohio", "Ohio St."),
        ("Penn", "Penn St."),
        ("Indiana", "Indiana St."),
        ("Iowa", "Iowa St."),
        ("Washington", "Washington St."),
        ("Kansas", "Kansas St."),
        ("Oklahoma", "Oklahoma St."),
        ("Oregon", "Oregon St."),
        
        # Similar names
        ("North Carolina", "NC State"),
        ("North Carolina", "UNC"),
        ("UConn", "Connecticut"),
        ("Miami", "Miami Ohio"),
        ("Louisiana", "Louisiana Tech"),
        ("South Carolina", "USC"),
        ("Cal", "California"),
        ("Ole Miss", "Mississippi"),
        ("Pitt", "Pittsburgh"),
        ("SMU", "Southern Methodist"),
        ("TCU", "Texas Christian"),
        ("UNLV", "Nevada Las Vegas"),
        ("VCU", "Virginia Commonwealth"),
        ("UCF", "Central Florida"),
        ("LSU", "Louisiana State"),
    ]
    
    return problem_pairs


def validate_game_matching(sample_size=20):
    """Try to match actual games between odds and scores to validate."""
    
    spreads_file = DATA_PATHS.odds_canonical_spreads_fg / "spreads_fg_all.csv"
    scores_file = DATA_PATHS.scores_fg / "games_all.csv"
    
    if not spreads_file.exists() or not scores_file.exists():
        return None
    
    odds = pd.read_csv(spreads_file)
    scores = pd.read_csv(scores_file)
    
    # Normalize dates
    odds['date'] = pd.to_datetime(odds['game_date']).dt.date
    scores['date'] = pd.to_datetime(scores['date']).dt.date
    
    # Sample some games from odds and try to find in scores
    sample_odds = odds.sample(min(sample_size, len(odds)), random_state=42)
    
    results = []
    for _, row in sample_odds.iterrows():
        game_date = row['date']
        home_odds = row['home_team_canonical']
        away_odds = row['away_team_canonical']
        
        # Try to find matching game in scores
        same_date = scores[scores['date'] == game_date]
        
        # Look for any game involving these teams
        found_home = same_date[same_date['home_team'].str.contains(home_odds.split()[0], case=False, na=False)]
        found_away = same_date[same_date['away_team'].str.contains(away_odds.split()[0], case=False, na=False)]
        
        matched_game = None
        if len(found_home) > 0 and len(found_away) > 0:
            # Check if same game
            common = set(found_home.index) & set(found_away.index)
            if common:
                matched_game = scores.loc[list(common)[0]]
        
        results.append({
            'date': game_date,
            'odds_home': home_odds,
            'odds_away': away_odds,
            'spread': row.get('spread'),
            'matched': matched_game is not None,
            'scores_home': matched_game['home_team'] if matched_game is not None else None,
            'scores_away': matched_game['away_team'] if matched_game is not None else None,
        })
    
    return results


def main():
    print("=" * 80)
    print("TEAM CANONICALIZATION VALIDATION REPORT")
    print("=" * 80)
    print()
    
    # Load all team names
    print("Loading team names from all sources...")
    teams = load_all_team_names()
    
    print(f"\nTeam counts by source:")
    print(f"  The Odds API:  {len(teams['odds_api']):,} teams")
    print(f"  ESPN Scores:   {len(teams['espn']):,} teams")
    print(f"  Barttorvik:    {len(teams['barttorvik']):,} teams")
    
    # Check exact matches
    print("\n" + "-" * 80)
    print("EXACT MATCH ANALYSIS")
    print("-" * 80)
    
    matches = find_exact_matches(teams)
    print(f"\nExact matches:")
    print(f"  Odds ∩ ESPN:       {len(matches['odds_espn']):,} teams")
    print(f"  Odds ∩ Barttorvik: {len(matches['odds_barttorvik']):,} teams")
    print(f"  ESPN ∩ Barttorvik: {len(matches['espn_barttorvik']):,} teams")
    print(f"  All three:         {len(matches['all_three']):,} teams")
    
    if len(matches['odds_espn']) == 0:
        print("\n⚠️  CRITICAL: ZERO exact matches between Odds and ESPN!")
        print("    Team names are in DIFFERENT FORMATS - canonicalization NOT complete!")
    
    # Analyze naming patterns
    print("\n" + "-" * 80)
    print("NAMING PATTERN ANALYSIS")
    print("-" * 80)
    
    patterns = analyze_name_patterns(teams)
    for source, info in patterns.items():
        print(f"\n{source.upper()}:")
        print(f"  Total: {info['total']}, Multi-word: {info['multi_word']}, Single-word: {info['single_word']}")
        print(f"  Sample multi-word: {info['sample_multi']}")
    
    # Find probable matches
    print("\n" + "-" * 80)
    print("FUZZY MATCHING RESULTS (Odds -> ESPN)")
    print("-" * 80)
    
    mappings = find_probable_matches(teams['odds_api'], teams['espn'])
    
    print(f"\nHigh confidence matches:   {len(mappings['high_confidence']):,}")
    print(f"Medium confidence (REVIEW): {len(mappings['medium_confidence']):,}")
    print(f"No match found:            {len(mappings['no_match']):,}")
    
    # Show medium confidence (potential problems)
    if mappings['medium_confidence']:
        print("\n⚠️  POTENTIAL MISMATCHES (need manual review):")
        for m in mappings['medium_confidence'][:25]:
            print(f"  {m['odds']:30} -> {m['espn']}")
            print(f"    Issue: {m['issue']}")
            if m['alternatives']:
                print(f"    Alternatives: {m['alternatives']}")
    
    # Show no matches
    if mappings['no_match']:
        print(f"\n❌ NO MATCH FOUND ({len(mappings['no_match'])} teams):")
        for m in mappings['no_match'][:15]:
            print(f"  {m['odds']}")
    
    # Validate actual game matching
    print("\n" + "-" * 80)
    print("GAME MATCHING VALIDATION (sample)")
    print("-" * 80)
    
    game_results = validate_game_matching(30)
    if game_results:
        matched_count = sum(1 for r in game_results if r['matched'])
        print(f"\nSampled {len(game_results)} games from odds data:")
        print(f"  Successfully matched to scores: {matched_count}")
        print(f"  Failed to match:                {len(game_results) - matched_count}")
        print(f"  Match rate: {100 * matched_count / len(game_results):.1f}%")
        
        print("\nFailed matches (sample):")
        for r in game_results:
            if not r['matched']:
                print(f"  {r['date']}: {r['odds_away']} @ {r['odds_home']} (spread: {r['spread']})")
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    issues = []
    if len(matches['odds_espn']) == 0:
        issues.append("❌ NO exact team name matches between Odds and ESPN")
    if len(mappings['medium_confidence']) > 20:
        issues.append(f"⚠️  {len(mappings['medium_confidence'])} teams need manual mapping review")
    if len(mappings['no_match']) > 10:
        issues.append(f"❌ {len(mappings['no_match'])} teams have no match in ESPN data")
    if game_results and sum(1 for r in game_results if r['matched']) < len(game_results) * 0.8:
        issues.append("❌ Less than 80% of sampled games could be matched")
    
    if issues:
        print("\n🚨 CANONICALIZATION IS NOT COMPLETE!")
        print("\nIssues found:")
        for issue in issues:
            print(f"  {issue}")
        print("\n📋 NEXT STEPS:")
        print("  1. Create a master team name mapping table")
        print("  2. Map: Odds API name -> ESPN name -> Barttorvik name")
        print("  3. Apply mapping to create truly canonical data")
        print("  4. Re-run this validation to confirm")
    else:
        print("\n✅ Canonicalization appears complete!")
    
    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
