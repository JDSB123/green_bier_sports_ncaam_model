"""Validate the consolidated odds file for accuracy."""
import csv
from collections import Counter
from pathlib import Path

DATA_FILE = Path("data/historical_odds/odds_consolidated_canonical.csv")

def main():
    with open(DATA_FILE, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total games: {len(rows):,}")
    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # CHECK 1: Any team playing itself? (mapping collision)
    # ═══════════════════════════════════════════════════════════════════════════
    self_plays = [(r['home_team'], r['away_team'], r['home_team_canonical'], r['game_date']) 
                  for r in rows if r['home_team_canonical'] == r['away_team_canonical']]
    print(f"❌ Games where team plays itself: {len(self_plays)}")
    if self_plays:
        print("   ERRORS - These need investigation:")
        for h, a, canon, d in self_plays[:10]:
            print(f"   '{h}' vs '{a}' -> both mapped to '{canon}' on {d}")
    else:
        print("   ✓ None found")
    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # CHECK 2: Reasonable team distribution
    # ═══════════════════════════════════════════════════════════════════════════
    all_teams = [r['home_team_canonical'] for r in rows] + [r['away_team_canonical'] for r in rows]
    team_counts = Counter(all_teams)
    print(f"Unique canonical teams: {len(team_counts)}")
    
    # Expected: ~360 D1 teams, each plays ~30 games/season, we have ~4 seasons
    # So expect ~100-150 games per team for major conference, less for small schools
    print(f"\nTop 15 most frequent (expect major conference teams):")
    for team, count in team_counts.most_common(15):
        print(f"  {team}: {count}")
    
    print(f"\nBottom 15 least frequent (expect small conference/transitional teams):")
    for team, count in team_counts.most_common()[-15:]:
        print(f"  {team}: {count}")
    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # CHECK 3: Sample raw->canonical mappings for manual review
    # ═══════════════════════════════════════════════════════════════════════════
    print("Sample mappings for manual verification:")
    print("-" * 70)
    
    # Get unique raw->canonical mappings
    home_mappings = {(r['home_team'], r['home_team_canonical']) for r in rows}
    away_mappings = {(r['away_team'], r['away_team_canonical']) for r in rows}
    all_mappings = home_mappings | away_mappings
    
    # Group by canonical to see what raw names map to each
    canonical_to_raw = {}
    for raw, canon in all_mappings:
        if canon not in canonical_to_raw:
            canonical_to_raw[canon] = set()
        canonical_to_raw[canon].add(raw)
    
    # Show teams with multiple raw name variants (most likely to have errors)
    multi_variant = [(canon, raws) for canon, raws in canonical_to_raw.items() if len(raws) > 2]
    multi_variant.sort(key=lambda x: -len(x[1]))
    
    print(f"\nTeams with 3+ raw name variants ({len(multi_variant)} teams):")
    for canon, raws in multi_variant[:20]:
        print(f"\n  {canon}:")
        for raw in sorted(raws):
            print(f"    - {raw}")
    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # CHECK 4: Look for suspicious patterns
    # ═══════════════════════════════════════════════════════════════════════════
    print("Checking for suspicious patterns...")
    
    # State schools that might be confused
    suspicious_pairs = [
        ("Tennessee", "Tennessee St."),
        ("Mississippi", "Mississippi St."),
        ("Georgia", "Georgia St."),
        ("Texas", "Texas St."),
        ("North Carolina", "NC State"),
        ("Indiana", "Indiana St."),
        ("Penn St.", "Pittsburgh"),
        ("Michigan", "Michigan St."),
    ]
    
    for team1, team2 in suspicious_pairs:
        if team1 in canonical_to_raw and team2 in canonical_to_raw:
            raw1 = canonical_to_raw[team1]
            raw2 = canonical_to_raw[team2]
            # Check for overlap (would be bad)
            overlap = raw1 & raw2
            if overlap:
                print(f"  ⚠️ OVERLAP between {team1} and {team2}: {overlap}")
            else:
                print(f"  ✓ {team1} ({len(raw1)} variants) and {team2} ({len(raw2)} variants) are distinct")
    print()

    # ═══════════════════════════════════════════════════════════════════════════
    # CHECK 5: Random sample of actual games
    # ═══════════════════════════════════════════════════════════════════════════
    import random
    random.seed(42)
    sample = random.sample(rows, min(10, len(rows)))
    
    print("Random sample of 10 games for manual spot-check:")
    print("-" * 90)
    for r in sample:
        print(f"{r['game_date']}: {r['away_team']} @ {r['home_team']}")
        print(f"         → {r['away_team_canonical']} @ {r['home_team_canonical']}")
        print(f"         Spread: {r['spread']}, Total: {r['total']}")
        print()

if __name__ == "__main__":
    main()
