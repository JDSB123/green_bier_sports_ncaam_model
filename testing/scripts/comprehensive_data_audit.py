#!/usr/bin/env python3
"""
COMPREHENSIVE DATA AUDIT - Run BEFORE any backtesting

This script validates:
1. ALL raw data sources are present and properly formatted
2. Team names are 100% canonicalized across ALL sources
3. Sign conventions are correct (home favorites = negative spreads)
4. Date/time formats are consistent
5. No duplicate or conflicting records
6. Data merges produce clean results

DO NOT RUN BACKTESTS UNTIL ALL CHECKS PASS.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"
ALIASES_FILE = DATA / "backtest_datasets" / "team_aliases_db.json"

# Track all issues
ISSUES: List[str] = []
WARNINGS: List[str] = []


def load_team_aliases() -> Dict[str, str]:
    """Load team name aliases."""
    if not ALIASES_FILE.exists():
        ISSUES.append(f"CRITICAL: Team aliases file not found: {ALIASES_FILE}")
        return {}
    
    with open(ALIASES_FILE) as f:
        return json.load(f)


def resolve_team_name(name: str, aliases: Dict[str, str]) -> str:
    """Resolve a team name to canonical form."""
    if pd.isna(name):
        return name
    key = name.lower().strip()
    return aliases.get(key, name)


def audit_raw_data_sources():
    """Audit all raw data sources exist and are properly formatted."""
    print("\n" + "=" * 70)
    print("1. RAW DATA SOURCES AUDIT")
    print("=" * 70)
    
    sources = {
        "Scores FG": DATA / "scores" / "fg",
        "Scores H1": DATA / "scores" / "h1",
        "Odds Consolidated": DATA / "odds" / "normalized" / "odds_consolidated_canonical.csv",
        "Odds Canonical Spreads FG": DATA / "odds" / "canonical" / "spreads" / "fg",
        "Odds Canonical Totals FG": DATA / "odds" / "canonical" / "totals" / "fg",
        "Ratings Barttorvik": DATA / "ratings" / "barttorvik",
        "Team Aliases": ALIASES_FILE,
    }
    
    for name, path in sources.items():
        if path.exists():
            if path.is_file():
                size = path.stat().st_size
                print(f"  [OK] {name}: {path.name} ({size:,} bytes)")
            else:
                files = list(path.glob("*"))
                print(f"  [OK] {name}: {len(files)} files")
        else:
            ISSUES.append(f"MISSING: {name} at {path}")
            print(f"  [ERROR] {name}: NOT FOUND")
    
    return len(ISSUES) == 0


def audit_scores_data(aliases: Dict[str, str]):
    """Audit scores data for completeness and consistency."""
    print("\n" + "=" * 70)
    print("2. SCORES DATA AUDIT")
    print("=" * 70)
    
    scores_dir = DATA / "scores" / "fg"
    all_teams = set()
    unresolved_teams = set()
    
    # Check each year file
    for year in range(2019, 2027):
        year_file = scores_dir / f"games_{year}.csv"
        if not year_file.exists():
            print(f"  [SKIP] {year}: No file")
            continue
        
        df = pd.read_csv(year_file)
        
        # Check required columns
        required = ["home_team", "away_team", "home_score", "away_score"]
        date_col = "date" if "date" in df.columns else "game_date"
        required.append(date_col)
        
        missing_cols = [c for c in required if c not in df.columns]
        if missing_cols:
            ISSUES.append(f"SCORES {year}: Missing columns {missing_cols}")
            print(f"  [ERROR] {year}: Missing columns {missing_cols}")
            continue
        
        # Check for null values
        null_counts = df[required].isnull().sum()
        has_nulls = null_counts[null_counts > 0]
        if len(has_nulls) > 0:
            WARNINGS.append(f"SCORES {year}: Null values in {has_nulls.to_dict()}")
            print(f"  [WARN] {year}: Null values in {has_nulls.to_dict()}")
        
        # Track team names
        for team in df["home_team"].dropna().unique():
            all_teams.add(team)
            resolved = resolve_team_name(team, aliases)
            if resolved == team and team.lower() not in aliases:
                unresolved_teams.add(team)
        
        for team in df["away_team"].dropna().unique():
            all_teams.add(team)
            resolved = resolve_team_name(team, aliases)
            if resolved == team and team.lower() not in aliases:
                unresolved_teams.add(team)
        
        # Check date parsing
        try:
            dates = pd.to_datetime(df[date_col])
            print(f"  [OK] {year}: {len(df):,} games, {dates.min().date()} to {dates.max().date()}")
        except Exception as e:
            ISSUES.append(f"SCORES {year}: Date parsing error: {e}")
            print(f"  [ERROR] {year}: Date parsing error")
    
    print(f"\n  Total unique teams in scores: {len(all_teams)}")
    print(f"  Teams not in aliases: {len(unresolved_teams)}")
    
    if unresolved_teams:
        WARNINGS.append(f"SCORES: {len(unresolved_teams)} teams not in aliases")
        # Show sample
        sample = list(unresolved_teams)[:10]
        print(f"  Sample unresolved: {sample}")
    
    return len([i for i in ISSUES if "SCORES" in i]) == 0


def audit_odds_data(aliases: Dict[str, str]):
    """Audit odds data for completeness and sign conventions."""
    print("\n" + "=" * 70)
    print("3. ODDS DATA AUDIT")
    print("=" * 70)
    
    odds_file = DATA / "odds" / "normalized" / "odds_consolidated_canonical.csv"
    if not odds_file.exists():
        ISSUES.append("ODDS: Consolidated file not found")
        print("  [ERROR] Consolidated odds file not found")
        return False
    
    df = pd.read_csv(odds_file)
    print(f"  Total rows: {len(df):,}")
    
    # Check required columns
    required = ["home_team", "away_team", "spread", "game_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        ISSUES.append(f"ODDS: Missing columns {missing}")
        print(f"  [ERROR] Missing columns: {missing}")
        return False
    
    # Parse dates
    df["game_date"] = pd.to_datetime(df["game_date"])
    print(f"  Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    
    # Check price columns
    price_cols = [c for c in df.columns if "price" in c.lower()]
    print(f"  Price columns: {price_cols}")
    
    for col in price_cols:
        non_null = df[col].notna().sum()
        pct = non_null / len(df) * 100
        print(f"    {col}: {non_null:,} ({pct:.1f}%)")
    
    # CRITICAL: Check sign convention
    # Negative spread = home team favored
    # If spread is -5, home is favored by 5 points
    print("\n  Sign Convention Check:")
    
    # Sample games with large spreads
    large_neg = df[df["spread"] < -15]
    large_pos = df[df["spread"] > 15]
    
    print(f"    Games with spread < -15 (strong home favorite): {len(large_neg):,}")
    print(f"    Games with spread > +15 (strong away favorite): {len(large_pos):,}")
    
    if len(large_neg) < len(large_pos):
        WARNINGS.append("ODDS: More positive spreads than negative - verify sign convention")
        print("    [WARN] More away favorites than home favorites - unusual")
    
    # Check for duplicate games
    dup_check = df.groupby(["game_date", "home_team", "away_team", "bookmaker"]).size()
    dups = dup_check[dup_check > 1]
    if len(dups) > 0:
        WARNINGS.append(f"ODDS: {len(dups)} duplicate game-bookmaker combinations")
        print(f"    [WARN] {len(dups)} duplicate records")
    
    # Check team canonicalization
    unresolved_home = set()
    unresolved_away = set()
    
    for team in df["home_team"].dropna().unique():
        resolved = resolve_team_name(team, aliases)
        if resolved == team and team.lower() not in aliases:
            unresolved_home.add(team)
    
    for team in df["away_team"].dropna().unique():
        resolved = resolve_team_name(team, aliases)
        if resolved == team and team.lower() not in aliases:
            unresolved_away.add(team)
    
    all_unresolved = unresolved_home | unresolved_away
    print(f"\n  Team canonicalization:")
    print(f"    Unique teams: {len(df['home_team'].dropna().unique())}")
    print(f"    Teams not in aliases: {len(all_unresolved)}")
    
    if all_unresolved:
        WARNINGS.append(f"ODDS: {len(all_unresolved)} teams not in aliases")
        sample = list(all_unresolved)[:10]
        print(f"    Sample: {sample}")
    
    return True


def audit_ratings_data(aliases: Dict[str, str]):
    """Audit Barttorvik ratings data."""
    print("\n" + "=" * 70)
    print("4. RATINGS DATA AUDIT")
    print("=" * 70)
    
    ratings_dir = DATA / "ratings" / "barttorvik"
    if not ratings_dir.exists():
        ISSUES.append("RATINGS: Directory not found")
        print("  [ERROR] Ratings directory not found")
        return False
    
    all_teams = set()
    unresolved = set()
    
    for year in range(2019, 2027):
        ratings_file = ratings_dir / f"ratings_{year}.json"
        if not ratings_file.exists():
            print(f"  [SKIP] {year}: No file")
            continue
        
        with open(ratings_file) as f:
            data = json.load(f)
        
        if isinstance(data, list):
            # Parse Barttorvik format
            teams = []
            for entry in data:
                if isinstance(entry, list) and len(entry) > 6:
                    team_name = entry[1] if len(entry) > 1 else None
                    if team_name:
                        teams.append(team_name)
                        all_teams.add(team_name)
                        
                        resolved = resolve_team_name(team_name, aliases)
                        if resolved == team_name and team_name.lower() not in aliases:
                            unresolved.add(team_name)
            
            print(f"  [OK] {year}: {len(teams)} teams")
        else:
            WARNINGS.append(f"RATINGS {year}: Unexpected format")
            print(f"  [WARN] {year}: Unexpected format")
    
    print(f"\n  Total unique teams in ratings: {len(all_teams)}")
    print(f"  Teams not in aliases: {len(unresolved)}")
    
    if unresolved:
        WARNINGS.append(f"RATINGS: {len(unresolved)} teams not in aliases")
        sample = list(unresolved)[:10]
        print(f"    Sample: {sample}")
    
    return True


def audit_h1_data(aliases: Dict[str, str]):
    """Audit first-half scores data."""
    print("\n" + "=" * 70)
    print("5. FIRST-HALF SCORES AUDIT")
    print("=" * 70)
    
    h1_file = DATA / "scores" / "h1" / "h1_games_all.csv"
    h1_canonical = DATA / "canonicalized" / "scores" / "h1" / "h1_games_all_canonical.csv"
    
    # Check which file exists
    if h1_canonical.exists():
        print(f"  Using canonical file: {h1_canonical.name}")
        df = pd.read_csv(h1_canonical)
    elif h1_file.exists():
        print(f"  Using raw file: {h1_file.name}")
        df = pd.read_csv(h1_file)
    else:
        WARNINGS.append("H1: No H1 scores file found")
        print("  [WARN] No H1 scores file found")
        return True  # Not critical
    
    print(f"  Total H1 games: {len(df):,}")
    
    # Check required columns
    required_h1 = ["home_h1", "away_h1"]
    alt_required = ["home_score_1h", "away_score_1h"]
    
    if all(c in df.columns for c in required_h1):
        h1_cols = required_h1
    elif all(c in df.columns for c in alt_required):
        h1_cols = alt_required
    else:
        WARNINGS.append("H1: Missing H1 score columns")
        print("  [WARN] Missing H1 score columns")
        return True
    
    # Check for valid scores
    null_h1 = df[h1_cols[0]].isna().sum()
    if null_h1 > 0:
        print(f"  [INFO] {null_h1} games with null H1 scores")
    
    # Date check
    date_col = "date" if "date" in df.columns else "game_date"
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        print(f"  Date range: {df[date_col].min().date()} to {df[date_col].max().date()}")
    
    print(f"  [OK] H1 data validated")
    return True


def audit_data_merge(aliases: Dict[str, str]):
    """Audit that data sources can be cleanly merged."""
    print("\n" + "=" * 70)
    print("6. DATA MERGE AUDIT")
    print("=" * 70)
    
    # Load scores (sample)
    scores_file = DATA / "scores" / "fg" / "games_2023.csv"
    if not scores_file.exists():
        print("  [SKIP] No 2023 scores to test merge")
        return True
    
    scores = pd.read_csv(scores_file)
    date_col = "date" if "date" in scores.columns else "game_date"
    scores[date_col] = pd.to_datetime(scores[date_col])
    scores["home_canonical"] = scores["home_team"].apply(lambda x: resolve_team_name(x, aliases))
    scores["away_canonical"] = scores["away_team"].apply(lambda x: resolve_team_name(x, aliases))
    
    print(f"  Scores sample: {len(scores):,} games")
    
    # Load odds
    odds_file = DATA / "odds" / "normalized" / "odds_consolidated_canonical.csv"
    if not odds_file.exists():
        print("  [SKIP] No odds to test merge")
        return True
    
    odds = pd.read_csv(odds_file)
    odds["game_date"] = pd.to_datetime(odds["game_date"])
    odds["home_canonical"] = odds["home_team"].apply(lambda x: resolve_team_name(x, aliases))
    odds["away_canonical"] = odds["away_team"].apply(lambda x: resolve_team_name(x, aliases))
    
    # Filter odds to 2023 season
    odds_2023 = odds[(odds["game_date"] >= "2022-11-01") & (odds["game_date"] <= "2023-04-30")]
    print(f"  Odds 2023 season: {len(odds_2023):,} rows")
    
    # Get consensus odds
    consensus = odds_2023.groupby(["game_date", "home_canonical", "away_canonical"]).agg({
        "spread": "median"
    }).reset_index()
    print(f"  Consensus odds: {len(consensus):,} games")
    
    # Attempt merge
    scores = scores.rename(columns={date_col: "game_date"})
    merged = scores.merge(
        consensus,
        on=["game_date", "home_canonical", "away_canonical"],
        how="left"
    )
    
    matched = merged["spread"].notna().sum()
    match_pct = matched / len(merged) * 100
    print(f"\n  Merge results:")
    print(f"    Scores: {len(scores):,}")
    print(f"    Matched with odds: {matched:,} ({match_pct:.1f}%)")
    
    if match_pct < 50:
        WARNINGS.append(f"MERGE: Only {match_pct:.1f}% of games matched odds")
        print(f"    [WARN] Low match rate - check team name resolution")
        
        # Debug unmatched
        unmatched = merged[merged["spread"].isna()].head(5)
        print("\n    Sample unmatched games:")
        for _, row in unmatched.iterrows():
            print(f"      {row['game_date'].date()} {row['home_canonical']} vs {row['away_canonical']}")
    else:
        print(f"    [OK] Good match rate")
    
    return True


def print_summary():
    """Print final summary."""
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    
    if ISSUES:
        print(f"\n[ERROR] CRITICAL ISSUES ({len(ISSUES)}):")
        for issue in ISSUES:
            print(f"   - {issue}")
    else:
        print("\n[OK] No critical issues found")
    
    if WARNINGS:
        print(f"\n[WARN] WARNINGS ({len(WARNINGS)}):")
        for warn in WARNINGS:
            print(f"   - {warn}")
    else:
        print("\n[OK] No warnings")
    
    print("\n" + "=" * 70)
    if ISSUES:
        print("[FAIL] DATA AUDIT FAILED - DO NOT RUN BACKTESTS")
        print("   Fix critical issues before proceeding.")
        return False
    elif WARNINGS:
        print("[WARN] DATA AUDIT PASSED WITH WARNINGS")
        print("   Review warnings before running backtests.")
        return True
    else:
        print("[OK] DATA AUDIT PASSED - OK TO PROCEED WITH BACKTESTS")
        return True


def main():
    print("=" * 70)
    print("COMPREHENSIVE DATA AUDIT")
    print("Run this BEFORE any backtesting!")
    print("=" * 70)
    
    # Load aliases
    aliases = load_team_aliases()
    print(f"\nLoaded {len(aliases):,} team aliases")
    
    # Run audits
    audit_raw_data_sources()
    audit_scores_data(aliases)
    audit_odds_data(aliases)
    audit_ratings_data(aliases)
    audit_h1_data(aliases)
    audit_data_merge(aliases)
    
    # Summary
    passed = print_summary()
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
