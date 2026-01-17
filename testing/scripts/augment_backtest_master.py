#!/usr/bin/env python3
"""
Augment canonical backtest master with ncaahoopR features.

Merges:
1. Canonical backtest master (scores + odds + ratings)
2. ncaahoopR game-by-game features (rolling Four Factors, depth, splits)

Output: backtest_master.csv (single source of truth)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Ensure project root is on sys.path so `testing` package imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_io import read_csv, read_json, write_csv, write_json

ALIASES_BLOB = "backtest_datasets/team_aliases_db.json"

# Input files
BACKTEST_MASTER = "backtest_datasets/backtest_master.csv"
NCAAHOOPR_FEATURES = "backtest_datasets/ncaahoopR_features.csv"
OUTPUT_BLOB = BACKTEST_MASTER
SUMMARY_BLOB = "backtest_datasets/backtest_master_summary.json"


def load_team_aliases() -> dict[str, str]:
    """Load team name aliases."""
    try:
        return read_json(ALIASES_BLOB)
    except FileNotFoundError:
        return {}


def resolve_team_name(name: str, aliases: dict[str, str]) -> str:
    """Resolve team name to canonical form."""
    if pd.isna(name):
        return name
    key = name.lower().strip()
    return aliases.get(key, name)


def load_backtest_master() -> pd.DataFrame:
    """Load the existing backtest master with scores, odds, and Barttorvik."""
    try:
        df = read_csv(BACKTEST_MASTER)
    except FileNotFoundError:
        print(f"[ERROR] Backtest master not found: {BACKTEST_MASTER}")
        sys.exit(1)
    df["game_date"] = pd.to_datetime(df["game_date"])

    print(f"[OK] Loaded backtest master: {len(df):,} games")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")

    return df


def load_ncaahoopR_features() -> pd.DataFrame:
    """Load ncaahoopR extracted features."""
    try:
        df = read_csv(NCAAHOOPR_FEATURES)
    except FileNotFoundError:
        print(f"[WARN] ncaahoopR features not found: {NCAAHOOPR_FEATURES}")
        return pd.DataFrame()
    df["game_date"] = pd.to_datetime(df["game_date"])

    # Standardize dates to CST/CDT as per governance
    if df["game_date"].dt.tz is None:
        # Assume naive dates are already in CST (not UTC)
        df["game_date"] = df["game_date"].dt.tz_localize('America/Chicago')
    else:
        # If already timezone-aware, ensure it's in CST
        df["game_date"] = df["game_date"].dt.tz_convert('America/Chicago')

    # Convert back to date for consistency with master
    df["game_date"] = df["game_date"].dt.date
    df["game_date"] = pd.to_datetime(df["game_date"])

    print(f"[OK] Loaded ncaahoopR features: {len(df):,} team-game records")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")

    return df


def create_team_features_lookup(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a lookup table of team features by game_date + team.

    This allows us to look up any team's rolling stats for any game date.
    """
    if features_df.empty:
        return pd.DataFrame()

    # Columns to include (exclude metadata columns)
    exclude_cols = ["game_id", "game_date", "season", "team", "team_raw",
                    "opponent", "opponent_raw", "is_home"]
    feature_cols = [c for c in features_df.columns if c not in exclude_cols]

    # Keep game_date, team, and all feature columns
    # Use the rolling features which represent the team's stats GOING INTO the game
    keep_cols = ["game_date", "team"] + feature_cols
    lookup = features_df[[c for c in keep_cols if c in features_df.columns]].copy()

    # Remove duplicates (same team may have multiple entries for same game)
    lookup = lookup.drop_duplicates(subset=["game_date", "team"], keep="first")

    print(f"   Team-date lookup entries: {len(lookup):,}")

    return lookup


def merge_all_sources(master_df: pd.DataFrame, ncaahoopR_df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    """Merge ncaahoopR features into the backtest master."""

    if ncaahoopR_df.empty:
        print("[WARN] No ncaahoopR features to merge")
        return master_df

    # Ensure ncaahoopR team names are fully canonical before any merge
    # This guarantees the backtest master never introduces alternate
    # representations that could conflict with canonical team columns.
    if "team" in ncaahoopR_df.columns:
        ncaahoopR_df["team"] = ncaahoopR_df["team"].apply(lambda x: resolve_team_name(x, aliases))
    if "opponent" in ncaahoopR_df.columns:
        ncaahoopR_df["opponent"] = ncaahoopR_df["opponent"].apply(lambda x: resolve_team_name(x, aliases))

    # Create team features lookup
    print("\nCreating team features lookup...")
    lookup = create_team_features_lookup(ncaahoopR_df)

    if lookup.empty:
        print("[WARN] No lookup created from ncaahoopR")
        return master_df

    # Get feature columns (exclude game_date and team)
    feature_cols = [c for c in lookup.columns if c not in ["game_date", "team"]]

    # Merge HOME team features with +/-1 day tolerance
    print("\nMerging HOME team ncaahoopR features...")
    home_features_list = []

    for idx, row in master_df.iterrows():
        game_date = row["game_date"]
        home_team = row["home_team"]

        # Try exact match first
        home_match = lookup[(lookup["game_date"] == game_date) & (lookup["team"] == home_team)]

        # If no exact match, try +/-1 day
        if home_match.empty:
            date_minus_1 = game_date - pd.Timedelta(days=1)
            home_match = lookup[(lookup["game_date"] == date_minus_1) & (lookup["team"] == home_team)]

        if home_match.empty:
            date_plus_1 = game_date + pd.Timedelta(days=1)
            home_match = lookup[(lookup["game_date"] == date_plus_1) & (lookup["team"] == home_team)]

        if not home_match.empty:
            # Take the first match if multiple
            features = home_match.iloc[0][feature_cols].to_dict()
            home_features_list.append({f"home_box_{k}": v for k, v in features.items()})
        else:
            home_features_list.append({f"home_box_{col}": None for col in feature_cols})

    # Add home features to master
    home_features_df = pd.DataFrame(home_features_list)
    merged = pd.concat([master_df.reset_index(drop=True), home_features_df], axis=1)

    home_matched = merged["home_box_efg"].notna().sum() if "home_box_efg" in merged.columns else 0
    print(f"   Home team matches: {home_matched:,}/{len(merged):,} ({home_matched/len(merged)*100:.1f}%)")

    # Merge AWAY team features with +/-1 day tolerance
    print("Merging AWAY team ncaahoopR features...")
    away_features_list = []

    for idx, row in merged.iterrows():
        game_date = row["game_date"]
        away_team = row["away_team"]

        # Try exact match first
        away_match = lookup[(lookup["game_date"] == game_date) & (lookup["team"] == away_team)]

        # If no exact match, try +/-1 day
        if away_match.empty:
            date_minus_1 = game_date - pd.Timedelta(days=1)
            away_match = lookup[(lookup["game_date"] == date_minus_1) & (lookup["team"] == away_team)]

        if away_match.empty:
            date_plus_1 = game_date + pd.Timedelta(days=1)
            away_match = lookup[(lookup["game_date"] == date_plus_1) & (lookup["team"] == away_team)]

        if not away_match.empty:
            # Take the first match if multiple
            features = away_match.iloc[0][feature_cols].to_dict()
            away_features_list.append({f"away_box_{k}": v for k, v in features.items()})
        else:
            away_features_list.append({f"away_box_{col}": None for col in feature_cols})

    # Add away features to merged
    away_features_df = pd.DataFrame(away_features_list)
    merged = pd.concat([merged, away_features_df], axis=1)

    away_matched = merged["away_box_efg"].notna().sum() if "away_box_efg" in merged.columns else 0
    print(f"   Away team matches: {away_matched:,}/{len(merged):,} ({away_matched/len(merged)*100:.1f}%)")

    # Combined match (both home AND away have data)
    if "home_box_efg" in merged.columns and "away_box_efg" in merged.columns:
        both_matched = (merged["home_box_efg"].notna() & merged["away_box_efg"].notna()).sum()
        print(f"   Both teams matched: {both_matched:,}/{len(merged):,} ({both_matched/len(merged)*100:.1f}%)")

    return merged


def calculate_differential_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate differential features between home and away teams."""

    # Find matching home/away columns
    home_cols = [c for c in df.columns if c.startswith("home_box_") and "_last" in c]

    for home_col in home_cols:
        away_col = home_col.replace("home_box_", "away_box_")
        if away_col in df.columns:
            # Create differential (home - away)
            diff_col = home_col.replace("home_box_", "diff_box_")
            df[diff_col] = df[home_col] - df[away_col]

    diff_cols = [c for c in df.columns if c.startswith("diff_box_")]
    print(f"   Created {len(diff_cols)} differential features")

    return df


def main():
    parser = argparse.ArgumentParser(description="Augment backtest master with ncaahoopR features")
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_BLOB,
        help="Output blob path (default: backtest_datasets/backtest_master.csv)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if ncaahoopR features already exist in the master",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("AUGMENTING BACKTEST MASTER WITH NCAAHOOPR")
    print("=" * 70)

    # Load aliases
    aliases = load_team_aliases()
    print(f"Loaded {len(aliases):,} team aliases\n")

    # Load data sources
    print("--- Loading Data Sources ---")
    master_df = load_backtest_master()
    ncaahoopR_df = load_ncaahoopR_features()

    # Skip if already enriched unless forced
    if not args.force and any(col.startswith("home_box_") for col in master_df.columns):
        print("[SKIP] backtest_master.csv already includes ncaahoopR features")
        print("       Use --force to rebuild.")
        return

    # Merge all sources
    print("\n--- Merging All Sources ---")
    consolidated = merge_all_sources(master_df, ncaahoopR_df, aliases)

    # Calculate differential features
    print("\n--- Calculating Differential Features ---")
    consolidated = calculate_differential_features(consolidated)

    # Ensure both game_date and date are available for downstream validation.
    if "game_date" in consolidated.columns and "date" not in consolidated.columns:
        consolidated["date"] = consolidated["game_date"]

    # Save output
    print("\n--- Saving Backtest Master ---")
    write_csv(args.output, consolidated)
    print(f"[OK] Saved {len(consolidated):,} games to {args.output}")

    # Summary
    print("\n" + "=" * 70)
    print("BACKTEST MASTER SUMMARY")
    print("=" * 70)
    print(f"Total games: {len(consolidated):,}")
    print(f"Total columns: {len(consolidated.columns)}")
    print(f"Date range: {consolidated['game_date'].min().date()} to {consolidated['game_date'].max().date()}")

    # Feature categories
    barttorvik_cols = [c for c in consolidated.columns if any(x in c for x in ["adj_o", "adj_d", "barthag", "efg", "tor", "orb", "ftr", "wab", "tempo", "conf"]) and "box" not in c]
    box_cols = [c for c in consolidated.columns if "_box_" in c]
    odds_cols = [c for c in consolidated.columns if "spread" in c or "total" in c or "price" in c]
    score_cols = [c for c in consolidated.columns if "score" in c or "margin" in c or "h1" in c.lower()]

    print("\nFeature breakdown:")
    print(f"  Barttorvik season ratings: {len(barttorvik_cols)}")
    print(f"  ncaahoopR box score features: {len(box_cols)}")
    print(f"  Odds/prices: {len(odds_cols)}")
    print(f"  Scores/results: {len(score_cols)}")

    # Coverage check
    print("\nCoverage:")
    for col_name, check_col in [
        ("FG Spread", "fg_spread"),
        ("FG Spread Price", "fg_spread_home_price"),
        ("H1 Spread", "h1_spread"),
        ("H1 Spread Price", "h1_spread_home_price"),
        ("Barttorvik", "home_adj_o"),
        ("ncaahoopR", "home_box_efg"),
    ]:
        if check_col in consolidated.columns:
            count = consolidated[check_col].notna().sum()
            pct = count / len(consolidated) * 100
            print(f"  {col_name}: {count:,} ({pct:.1f}%)")

    # Save summary
    summary = {
        "build_time": datetime.now().isoformat(),
        "total_games": len(consolidated),
        "total_columns": len(consolidated.columns),
        "date_range": {
            "min": str(consolidated["game_date"].min().date()),
            "max": str(consolidated["game_date"].max().date()),
        },
        "feature_counts": {
            "barttorvik": len(barttorvik_cols),
            "ncaahoopR_box": len(box_cols),
            "odds": len(odds_cols),
            "scores": len(score_cols),
        },
        "columns": list(consolidated.columns),
    }

    write_json(SUMMARY_BLOB, summary, indent=2)
    print(f"\n[OK] Saved summary to {SUMMARY_BLOB}")

    print("\n" + "=" * 70)
    print("[DONE] BACKTEST MASTER UPDATED")
    print("=" * 70)


if __name__ == "__main__":
    main()
