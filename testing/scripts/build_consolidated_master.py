#!/usr/bin/env python3
"""
Build CONSOLIDATED SINGLE SOURCE OF TRUTH backtest master.

Merges ALL data sources:
1. Game scores (FG + H1)
2. Odds with ACTUAL prices (FG + H1)
3. Barttorvik season ratings
4. ncaahoopR game-by-game features (rolling Four Factors, depth, splits)

Output: backtest_master_consolidated.csv - THE SINGLE SOURCE OF TRUTH
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict

import pandas as pd
import numpy as np

from testing.azure_io import read_csv, read_json, write_csv, write_json

ALIASES_BLOB = "backtest_datasets/team_aliases_db.json"

# Input files
BACKTEST_MASTER = "backtest_datasets/backtest_master.csv"
NCAAHOOPR_FEATURES = "backtest_datasets/ncaahoopR_features.csv"
OUTPUT_BLOB = "backtest_datasets/backtest_master_consolidated.csv"
SUMMARY_BLOB = "backtest_datasets/backtest_master_consolidated_summary.json"


def load_team_aliases() -> Dict[str, str]:
    """Load team name aliases."""
    try:
        return read_json(ALIASES_BLOB)
    except FileNotFoundError:
        return {}


def resolve_team_name(name: str, aliases: Dict[str, str]) -> str:
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


def merge_all_sources(master_df: pd.DataFrame, ncaahoopR_df: pd.DataFrame, aliases: Dict[str, str]) -> pd.DataFrame:
    """Merge all data sources into consolidated master."""
    
    if ncaahoopR_df.empty:
        print("[WARN] No ncaahoopR features to merge")
        return master_df
    
    # Create team features lookup
    print("\nCreating team features lookup...")
    lookup = create_team_features_lookup(ncaahoopR_df)
    
    if lookup.empty:
        print("[WARN] No lookup created from ncaahoopR")
        return master_df
    
    # Get feature columns (exclude game_date and team)
    feature_cols = [c for c in lookup.columns if c not in ["game_date", "team"]]
    
    # Merge HOME team features
    print("\nMerging HOME team ncaahoopR features...")
    home_lookup = lookup.copy()
    home_rename = {col: f"home_box_{col}" for col in feature_cols}
    home_rename["team"] = "home_team_canonical"
    home_lookup = home_lookup.rename(columns=home_rename)
    
    merged = master_df.merge(
        home_lookup,
        on=["game_date", "home_team_canonical"],
        how="left"
    )
    
    home_matched = merged["home_box_efg"].notna().sum() if "home_box_efg" in merged.columns else 0
    print(f"   Home team matches: {home_matched:,}/{len(merged):,} ({home_matched/len(merged)*100:.1f}%)")
    
    # Merge AWAY team features
    print("Merging AWAY team ncaahoopR features...")
    away_lookup = lookup.copy()
    away_rename = {col: f"away_box_{col}" for col in feature_cols}
    away_rename["team"] = "away_team_canonical"
    away_lookup = away_lookup.rename(columns=away_rename)
    
    merged = merged.merge(
        away_lookup,
        on=["game_date", "away_team_canonical"],
        how="left"
    )
    
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
    print("=" * 70)
    print("BUILDING CONSOLIDATED SINGLE SOURCE OF TRUTH")
    print("=" * 70)
    
    # Load aliases
    aliases = load_team_aliases()
    print(f"Loaded {len(aliases):,} team aliases\n")
    
    # Load data sources
    print("--- Loading Data Sources ---")
    master_df = load_backtest_master()
    ncaahoopR_df = load_ncaahoopR_features()
    
    # Merge all sources
    print("\n--- Merging All Sources ---")
    consolidated = merge_all_sources(master_df, ncaahoopR_df, aliases)
    
    # Calculate differential features
    print("\n--- Calculating Differential Features ---")
    consolidated = calculate_differential_features(consolidated)
    
    # Save output
    print("\n--- Saving Consolidated Master ---")
    write_csv(OUTPUT_BLOB, consolidated)
    print(f"[OK] Saved {len(consolidated):,} games to {OUTPUT_BLOB}")
    
    # Summary
    print("\n" + "=" * 70)
    print("CONSOLIDATED MASTER SUMMARY")
    print("=" * 70)
    print(f"Total games: {len(consolidated):,}")
    print(f"Total columns: {len(consolidated.columns)}")
    print(f"Date range: {consolidated['game_date'].min().date()} to {consolidated['game_date'].max().date()}")
    
    # Feature categories
    barttorvik_cols = [c for c in consolidated.columns if any(x in c for x in ["adj_o", "adj_d", "barthag", "efg", "tor", "orb", "ftr", "wab", "tempo", "conf"]) and "box" not in c]
    box_cols = [c for c in consolidated.columns if "_box_" in c]
    odds_cols = [c for c in consolidated.columns if "spread" in c or "total" in c or "price" in c]
    score_cols = [c for c in consolidated.columns if "score" in c or "margin" in c or "h1" in c.lower()]
    
    print(f"\nFeature breakdown:")
    print(f"  Barttorvik season ratings: {len(barttorvik_cols)}")
    print(f"  ncaahoopR box score features: {len(box_cols)}")
    print(f"  Odds/prices: {len(odds_cols)}")
    print(f"  Scores/results: {len(score_cols)}")
    
    # Coverage check
    print(f"\nCoverage:")
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
    print("[DONE] SINGLE SOURCE OF TRUTH CREATED")
    print("=" * 70)


if __name__ == "__main__":
    main()
