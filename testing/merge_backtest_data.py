"""
Merge odds and scores into a single backtest-ready dataset.

This creates the final dataset needed for backtesting:
- Canonical team names
- Opening/closing spreads and totals
- Actual game results (final and H1)
- Season classification
"""

import csv
from collections import defaultdict
from pathlib import Path
from production_parity.team_resolver import ProductionTeamResolver


def load_odds():
    """Load consolidated odds data."""
    path = Path(__file__).parent / 'data/historical_odds/odds_consolidated_canonical.csv'
    with open(path, 'r') as f:
        return list(csv.DictReader(f))


def load_scores(resolver):
    """Load all game scores and canonicalize team names."""
    scores = []
    base_dir = Path(__file__).parent / 'data/historical'
    for f in sorted(base_dir.glob('games_20*.csv')):
        with open(f, 'r') as file:
            for row in csv.DictReader(file):
                # Canonicalize team names
                home_result = resolver.resolve(row['home_team'])
                away_result = resolver.resolve(row['away_team'])
                
                if home_result.resolved and away_result.resolved:
                    row['home_canonical'] = home_result.canonical_name
                    row['away_canonical'] = away_result.canonical_name
                    scores.append(row)
    
    return scores


def build_score_lookup(scores):
    """Build lookup: (home_canonical, away_canonical, date) -> score row."""
    lookup = {}
    for row in scores:
        key = (row['home_canonical'], row['away_canonical'], row['date'])
        lookup[key] = row
    return lookup


def merge_data(odds, score_lookup):
    """Merge odds with scores."""
    merged = []
    matched = 0
    unmatched = 0
    
    for odd in odds:
        key = (odd['home_team_canonical'], odd['away_team_canonical'], odd['game_date'])
        
        if key in score_lookup:
            score = score_lookup[key]
            merged.append({
                # Game identification
                'game_date': odd['game_date'],
                'season': odd['season'],
                'home_team': odd['home_team_canonical'],
                'away_team': odd['away_team_canonical'],
                'bookmaker': odd['bookmaker'],
                
                # Odds data
                'spread': odd['spread'],  # Home team spread
                'total': odd['total'],
                'h1_spread': odd.get('h1_spread', ''),
                'h1_total': odd.get('h1_total', ''),
                
                # Actual results
                'home_score': score['home_score'],
                'away_score': score['away_score'],
                'h1_home_score': score.get('h1_home', ''),
                'h1_away_score': score.get('h1_away', ''),
                
                # Calculated fields for validation
                'actual_margin': int(score['home_score']) - int(score['away_score']),
                'actual_total': int(score['home_score']) + int(score['away_score']),
                'venue': score.get('venue', ''),
                'neutral': score.get('neutral', ''),
            })
            matched += 1
        else:
            unmatched += 1
    
    return merged, matched, unmatched


def calculate_backtest_fields(row):
    """Add fields needed for backtesting."""
    try:
        spread = float(row['spread']) if row['spread'] else None
        total = float(row['total']) if row['total'] else None
        actual_margin = int(row['actual_margin'])
        actual_total = int(row['actual_total'])
        
        # Spread result: Did home team cover?
        # Spread is home team spread, so if spread is -7 and home wins by 10, they covered
        if spread is not None:
            row['spread_result'] = actual_margin + spread  # Positive = home covered
            row['home_covered'] = 1 if row['spread_result'] > 0 else (0 if row['spread_result'] < 0 else 0.5)
        
        # Total result: Over or under?
        if total is not None:
            row['total_result'] = actual_total - total  # Positive = over
            row['went_over'] = 1 if row['total_result'] > 0 else (0 if row['total_result'] < 0 else 0.5)
        
        # H1 calculations if available
        h1_spread = float(row['h1_spread']) if row.get('h1_spread') else None
        h1_total = float(row['h1_total']) if row.get('h1_total') else None
        h1_home = float(row['h1_home_score']) if row.get('h1_home_score') else None
        h1_away = float(row['h1_away_score']) if row.get('h1_away_score') else None
        
        if h1_home is not None and h1_away is not None:
            h1_margin = h1_home - h1_away
            h1_actual_total = h1_home + h1_away
            
            if h1_spread is not None:
                row['h1_spread_result'] = h1_margin + h1_spread
                row['h1_home_covered'] = 1 if row['h1_spread_result'] > 0 else (0 if row['h1_spread_result'] < 0 else 0.5)
            
            if h1_total is not None:
                row['h1_total_result'] = h1_actual_total - h1_total
                row['h1_went_over'] = 1 if row['h1_total_result'] > 0 else (0 if row['h1_total_result'] < 0 else 0.5)
    
    except (ValueError, TypeError) as e:
        pass  # Skip rows with invalid data
    
    return row


def main():
    print("=" * 70)
    print("BACKTEST DATA MERGER")
    print("=" * 70)
    
    # Load data
    resolver = ProductionTeamResolver()
    
    print("\nLoading odds data...")
    odds = load_odds()
    print(f"  Loaded {len(odds):,} odds rows")
    
    print("\nLoading score data...")
    scores = load_scores(resolver)
    print(f"  Loaded {len(scores):,} score rows with canonical names")
    
    # Build lookup
    score_lookup = build_score_lookup(scores)
    print(f"  Built lookup with {len(score_lookup):,} unique games")
    
    # Merge
    print("\nMerging datasets...")
    merged, matched, unmatched = merge_data(odds, score_lookup)
    print(f"  Matched: {matched:,}")
    print(f"  Unmatched: {unmatched:,}")
    print(f"  Match rate: {matched / len(odds) * 100:.1f}%")
    
    # Calculate backtest fields
    print("\nCalculating backtest fields...")
    for row in merged:
        calculate_backtest_fields(row)
    
    # Write output
    output_file = Path(__file__).parent / 'data/backtest_ready.csv'
    
    fieldnames = [
        'game_date', 'season', 'home_team', 'away_team', 'bookmaker',
        'spread', 'total', 'h1_spread', 'h1_total',
        'home_score', 'away_score', 'h1_home_score', 'h1_away_score',
        'actual_margin', 'actual_total',
        'spread_result', 'home_covered', 'total_result', 'went_over',
        'h1_spread_result', 'h1_home_covered', 'h1_total_result', 'h1_went_over',
        'venue', 'neutral'
    ]
    
    print(f"\nWriting to {output_file}...")
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(merged)
    
    print(f"  Wrote {len(merged):,} rows")
    
    # Summary stats
    print("\n" + "=" * 70)
    print("BACKTEST DATA SUMMARY")
    print("=" * 70)
    
    # By season
    by_season = defaultdict(int)
    for row in merged:
        by_season[row['season']] += 1
    
    print("\nGames by season:")
    for season in sorted(by_season.keys()):
        print(f"  {int(season)-1}-{str(season)[2:]}: {by_season[season]:,}")
    
    # H1 coverage
    h1_spread_count = sum(1 for r in merged if r.get('h1_spread'))
    h1_result_count = sum(1 for r in merged if r.get('h1_spread_result'))
    
    print(f"\nH1 data coverage:")
    print(f"  Games with H1 spread: {h1_spread_count:,}")
    print(f"  Games with H1 result: {h1_result_count:,}")
    
    # Sample games
    print("\nSample backtest rows:")
    for row in merged[:5]:
        print(f"  {row['game_date']}: {row['away_team']} @ {row['home_team']}")
        print(f"    Spread: {row['spread']}, Result: {row.get('spread_result', 'N/A')}")
        print(f"    Score: {row['away_score']}-{row['home_score']}, Covered: {row.get('home_covered', 'N/A')}")


if __name__ == "__main__":
    main()
