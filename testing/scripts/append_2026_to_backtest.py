#!/usr/bin/env python3
"""
Append 2025-2026 season data to backtest_master_enhanced.csv.

This script:
1. Loads existing backtest_master_enhanced.csv (11,763 games through Apr 2025)
2. Loads 2026 scores from scores/fg/games_2026.csv
3. Merges with odds from spreads_fg_all.csv (has 2026 data)
4. Appends to create updated backtest_master_enhanced.csv

Usage:
    python testing/scripts/append_2026_to_backtest.py
"""
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_data_reader import get_azure_reader
from testing.azure_io import write_csv
from testing.scripts.team_utils import resolve_team_name


def resolve_team_safe(team: str) -> str:
    """Resolve team name to canonical, or return lowercase original."""
    try:
        resolved = resolve_team_name(team)
        return resolved if resolved else team.lower()
    except:
        return team.lower() if team else ""


def main():
    print("=" * 72)
    print("APPEND 2026 SEASON TO BACKTEST MASTER")
    print("=" * 72)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    reader = get_azure_reader()

    # Step 1: Load existing backtest_master_enhanced.csv
    print("Step 1: Loading existing backtest_master_enhanced.csv...")
    bm = reader.read_csv("backtest_datasets/backtest_master_enhanced.csv", data_type=None)
    bm["game_date"] = pd.to_datetime(bm["game_date"], errors="coerce")
    print(f"  Loaded: {len(bm)} games")
    print(f"  Date range: {bm['game_date'].min().date()} to {bm['game_date'].max().date()}")
    
    # Check if 2026 already exists
    bm_2026 = bm[bm["game_date"] >= "2025-11-01"]
    if len(bm_2026) > 0:
        print(f"  WARNING: Already has {len(bm_2026)} games from 2026 season!")
        return 1

    # Step 2: Load 2026 scores
    print()
    print("Step 2: Loading 2026 season scores...")
    scores_2026 = reader.read_csv("scores/fg/games_2026.csv", data_type=None)
    scores_2026 = scores_2026.rename(columns={"date": "game_date"})
    scores_2026["game_date"] = pd.to_datetime(scores_2026["game_date"], errors="coerce")
    print(f"  Loaded: {len(scores_2026)} games")
    print(f"  Date range: {scores_2026['game_date'].min().date()} to {scores_2026['game_date'].max().date()}")

    # Step 3: Load odds (spreads_fg_all.csv has 2026)
    print()
    print("Step 3: Loading odds data (spreads_fg_all.csv)...")
    odds = reader.read_csv("odds/canonical/spreads/fg/spreads_fg_all.csv", data_type=None)
    odds["game_date"] = pd.to_datetime(odds["game_date"], errors="coerce")
    odds_2026 = odds[odds["game_date"] >= "2025-11-01"]
    print(f"  Total odds: {len(odds)} rows")
    print(f"  2026 season odds: {len(odds_2026)} rows")

    # Get best odds per game (use consensus/average across books)
    odds_2026_agg = odds_2026.groupby(
        ["home_team", "away_team", "game_date"]
    ).agg({
        "spread": "first",  # Use first (usually consensus)
    }).reset_index()
    odds_2026_agg = odds_2026_agg.rename(columns={"spread": "fg_spread"})
    print(f"  Unique games with odds: {len(odds_2026_agg)}")

    # Step 4: Load H1 odds (if available)
    print()
    print("Step 4: Loading H1 odds data...")
    try:
        h1_odds = reader.read_csv("odds/canonical/spreads/h1/spreads_h1_all.csv", data_type=None)
        h1_odds["game_date"] = pd.to_datetime(h1_odds["game_date"], errors="coerce")
        h1_2026 = h1_odds[h1_odds["game_date"] >= "2025-11-01"]
        
        # H1 odds file uses 'h1_spread' not 'spread'
        h1_col = "h1_spread" if "h1_spread" in h1_2026.columns else "spread"
        h1_2026_agg = h1_2026.groupby(
            ["home_team", "away_team", "game_date"]
        ).agg({
            h1_col: "first",
        }).reset_index()
        h1_2026_agg = h1_2026_agg.rename(columns={h1_col: "h1_spread"})
        print(f"  Unique games with H1 odds: {len(h1_2026_agg)}")
    except Exception as e:
        print(f"  Warning: Could not load H1 odds: {e}")
        h1_2026_agg = None

    # Step 5: Load H1 scores (if available)
    print()
    print("Step 5: Loading H1 scores...")
    try:
        h1_scores = reader.read_csv("scores/h1/h1_games_all.csv", data_type=None)
        h1_scores["date"] = pd.to_datetime(h1_scores["date"], errors="coerce")
        h1_scores_2026 = h1_scores[h1_scores["date"] >= "2025-11-01"]
        h1_scores_2026 = h1_scores_2026.rename(columns={"date": "game_date"})
        print(f"  2026 H1 scores: {len(h1_scores_2026)}")
    except Exception as e:
        print(f"  Warning: Could not load H1 scores: {e}")
        h1_scores_2026 = None

    # Step 6: Merge all data for 2026
    print()
    print("Step 6: Merging 2026 data...")
    
    # Start with scores
    df_2026 = scores_2026.copy()
    
    # Resolve team names to canonical form
    print("  Resolving team names...")
    df_2026["home_team_resolved"] = df_2026["home_team"].apply(resolve_team_safe)
    df_2026["away_team_resolved"] = df_2026["away_team"].apply(resolve_team_safe)
    
    # Resolve odds team names  
    odds_2026_agg["home_team_resolved"] = odds_2026_agg["home_team"].apply(resolve_team_safe)
    odds_2026_agg["away_team_resolved"] = odds_2026_agg["away_team"].apply(resolve_team_safe)
    
    # Merge FG odds
    df_2026 = df_2026.merge(
        odds_2026_agg[["home_team_resolved", "away_team_resolved", "game_date", "fg_spread"]],
        on=["home_team_resolved", "away_team_resolved", "game_date"],
        how="left"
    )
    fg_matched = df_2026["fg_spread"].notna().sum()
    print(f"  FG odds matched: {fg_matched}/{len(df_2026)} ({100*fg_matched/len(df_2026):.1f}%)")

    # Merge H1 odds
    if h1_2026_agg is not None:
        h1_2026_agg["home_team_resolved"] = h1_2026_agg["home_team"].apply(resolve_team_safe)
        h1_2026_agg["away_team_resolved"] = h1_2026_agg["away_team"].apply(resolve_team_safe)
        df_2026 = df_2026.merge(
            h1_2026_agg[["home_team_resolved", "away_team_resolved", "game_date", "h1_spread"]],
            on=["home_team_resolved", "away_team_resolved", "game_date"],
            how="left"
        )
        h1_matched = df_2026["h1_spread"].notna().sum()
        print(f"  H1 odds matched: {h1_matched}/{len(df_2026)} ({100*h1_matched/len(df_2026):.1f}%)")
    else:
        df_2026["h1_spread"] = None

    # Merge H1 scores
    if h1_scores_2026 is not None and len(h1_scores_2026) > 0:
        h1_scores_2026["home_team_resolved"] = h1_scores_2026["home_team"].apply(resolve_team_safe)
        h1_scores_2026["away_team_resolved"] = h1_scores_2026["away_team"].apply(resolve_team_safe)
        df_2026 = df_2026.merge(
            h1_scores_2026[["home_team_resolved", "away_team_resolved", "game_date", "home_h1", "away_h1"]],
            on=["home_team_resolved", "away_team_resolved", "game_date"],
            how="left"
        )
        h1_score_matched = df_2026["home_h1"].notna().sum()
        print(f"  H1 scores matched: {h1_score_matched}/{len(df_2026)} ({100*h1_score_matched/len(df_2026):.1f}%)")
    else:
        df_2026["home_h1"] = None
        df_2026["away_h1"] = None

    # Drop temp columns
    df_2026 = df_2026.drop(columns=["home_team_resolved", "away_team_resolved"])

    # Step 7: Align columns with existing backtest master
    print()
    print("Step 7: Aligning columns with existing backtest master...")
    existing_cols = list(bm.columns)
    
    # Add missing columns with NaN
    for col in existing_cols:
        if col not in df_2026.columns:
            df_2026[col] = None
    
    # Reorder to match
    df_2026 = df_2026[existing_cols]
    print(f"  Aligned to {len(existing_cols)} columns")

    # Step 8: Combine and save
    print()
    print("Step 8: Combining and saving...")
    combined = pd.concat([bm, df_2026], ignore_index=True)
    print(f"  Total games: {len(combined)}")
    print(f"  Date range: {combined['game_date'].min().date()} to {combined['game_date'].max().date()}")

    # Calculate season breakdown
    def get_season(d):
        if pd.isna(d):
            return None
        if d.month >= 7:
            return d.year + 1
        return d.year
    
    combined["_season"] = combined["game_date"].apply(get_season)
    print()
    print("  By season:")
    for season in [2024, 2025, 2026]:
        count = (combined["_season"] == season).sum()
        h1_odds = combined[combined["_season"] == season]["h1_spread"].notna().sum() if "h1_spread" in combined.columns else 0
        fg_odds = combined[combined["_season"] == season]["fg_spread"].notna().sum() if "fg_spread" in combined.columns else 0
        print(f"    {season}: {count} games | FG odds: {fg_odds} ({100*fg_odds/count:.0f}%) | H1 odds: {h1_odds} ({100*h1_odds/count:.0f}%)")
    
    combined = combined.drop(columns=["_season"])

    # Save using azure_io
    from testing.azure_io import upload_text
    import io
    
    output_buffer = io.StringIO()
    combined.to_csv(output_buffer, index=False)
    csv_content = output_buffer.getvalue()
    
    upload_text(
        "backtest_datasets/backtest_master_enhanced.csv",
        csv_content,
        content_type="text/csv",
        tags={"data_type": "backtest_master", "version": "enhanced", "updated": datetime.now().isoformat()}
    )
    print()
    print(f"  Saved to backtest_datasets/backtest_master_enhanced.csv")

    print()
    print("=" * 72)
    print("SUCCESS: 2026 season appended to backtest_master_enhanced.csv")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
