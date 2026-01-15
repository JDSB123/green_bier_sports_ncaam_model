#!/usr/bin/env python3
"""
AUDIT NCAAR COVERAGE

Fact-checks why NCAAR canonicalization rate is ~37%.
Analyzes unmatched games to determine if issues are:
1. Missing NCAAR data (coverage)
2. Canonicalization problems (aliases)
3. Date mismatches (time zones, etc.)

Output: Detailed breakdown of match rates and suggestions.
"""

import sys
from pathlib import Path
from collections import Counter

import pandas as pd

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_data_reader import get_azure_reader
from testing.azure_io import read_json


def load_data():
    """Load canonical master and NCAAR features."""
    reader = get_azure_reader()

    print("Loading canonical backtest master...")
    master_df = reader.read_backtest_master()
    master_df["game_date"] = pd.to_datetime(master_df["game_date"])
    print(f"  {len(master_df):,} games")

    print("Loading NCAAR features...")
    ncaar_df = reader.read_csv("backtest_datasets/ncaahoopR_features.csv", data_type=None)
    ncaar_df["game_date"] = pd.to_datetime(ncaar_df["game_date"])
    print(f"  {len(ncaar_df):,} team-game records")

    print("Loading team aliases...")
    aliases = read_json("backtest_datasets/team_aliases_db.json")
    print(f"  {len(aliases):,} aliases")

    return master_df, ncaar_df, aliases


def resolve_team_name(name: str, aliases: dict) -> str:
    """Resolve team name to canonical form."""
    if pd.isna(name):
        return name
    key = name.lower().strip()
    return aliases.get(key, name)


def audit_matches(master_df: pd.DataFrame, ncaar_df: pd.DataFrame, aliases: dict):
    """Audit match rates with detailed breakdown."""

    # Canonicalize NCAAR team names
    ncaar_df["canonical_team"] = ncaar_df["team"].apply(lambda x: resolve_team_name(x, aliases))

    # Create lookup: (date, canonical_team) -> exists
    ncaar_lookup = set()
    for _, row in ncaar_df.iterrows():
        ncaar_lookup.add((row["game_date"].date(), row["canonical_team"]))

    print(f"NCAAR lookup has {len(ncaar_lookup):,} unique (date, team) entries")

    # Stats
    total_games = len(master_df)
    exact_matches = 0
    near_misses = 0  # +/- 1 day
    unmatched = 0
    unresolved_teams = Counter()
    date_mismatches = []

    for _, game in master_df.iterrows():
        game_date = game["game_date"].date()
        home_team = game["home_team"]
        away_team = game["away_team"]

        # Check exact matches
        home_match = (game_date, home_team) in ncaar_lookup
        away_match = (game_date, away_team) in ncaar_lookup

        if home_match or away_match:
            exact_matches += 1
            continue

        # Check near misses (+/- 1 day)
        near_match = False
        for delta in [-1, 1]:
            check_date = game_date + pd.Timedelta(days=delta)
            if (check_date, home_team) in ncaar_lookup or (check_date, away_team) in ncaar_lookup:
                near_match = True
                date_mismatches.append((game_date, check_date, home_team, away_team))
                break

        if near_match:
            near_misses += 1
        else:
            unmatched += 1
            # Check if teams are unresolved
            if home_team not in aliases.values():
                unresolved_teams[home_team] += 1
            if away_team not in aliases.values():
                unresolved_teams[away_team] += 1

    return {
        "total_games": total_games,
        "exact_matches": exact_matches,
        "near_misses": near_misses,
        "unmatched": unmatched,
        "unresolved_teams": unresolved_teams,
        "date_mismatches": date_mismatches[:10]  # Sample
    }


def main():
    print("=" * 80)
    print("NCAAR COVERAGE AUDIT")
    print("=" * 80)

    master_df, ncaar_df, aliases = load_data()

    print("\nAuditing matches...")
    stats = audit_matches(master_df, ncaar_df, aliases)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    total = stats["total_games"]
    exact = stats["exact_matches"]
    near = stats["near_misses"]
    unmatched = stats["unmatched"]

    print(f"Total games in master: {total:,}")
    print(f"Exact matches (same date): {exact:,} ({exact/total*100:.1f}%)")
    print(f"Near misses (+/- 1 day): {near:,} ({near/total*100:.1f}%)")
    print(f"Total potential matches: {exact + near:,} ({(exact + near)/total*100:.1f}%)")
    print(f"Completely unmatched: {unmatched:,} ({unmatched/total*100:.1f}%)")

    print(f"\nUnresolved team variants (top 10):")
    for team, count in stats["unresolved_teams"].most_common(10):
        print(f"  {team}: {count}")

    if stats["date_mismatches"]:
        print(f"\nSample date mismatches (showing {len(stats['date_mismatches'])}):")
        for orig, near_date, home, away in stats["date_mismatches"]:
            print(f"  {orig} → {near_date}: {home} vs {away}")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    unmatched_rate = unmatched / total
    near_rate = near / total

    # Check master coverage (ncaahoopR features)
    ncaar_cols = [c for c in master_df.columns if c.startswith("home_box_") or c.startswith("away_box_")]
    if ncaar_cols and "home_box_efg" in master_df.columns:
        ncaar_coverage = master_df["home_box_efg"].notna().sum() / len(master_df) * 100
        print(f"? BACKTEST MASTER COVERAGE: {ncaar_coverage:.1f}% (with +/- 1 day tolerance)")
    else:
        print("??  BACKTEST MASTER: ncaahoopR features not merged - run augment_backtest_master.py")

    if unmatched_rate > 0.5:
        print("❌ HIGH UNMATCHED RATE: Likely NCAAR data coverage issue, not canonicalization.")
    elif near_rate > 0.1:
        print("⚠️  DATE MISMATCHES: Check time zone handling or date formats.")
    else:
        print("✅ LOW UNMATCHED RATE: Canonicalization working well; coverage is the limiter.")


if __name__ == "__main__":
    main()
