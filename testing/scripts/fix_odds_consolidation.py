#!/usr/bin/env python3
"""
Fix odds consolidation to include prices for all seasons.

The issue: odds_consolidated_canonical.csv has 0% price coverage for 2024-2025
because the consolidation process dropped price columns.

Solution: Rebuild using the o4 (2024) and o5 (2025) raw files which have 99%+ price coverage.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd


def rebuild_consolidated_odds():
    """Rebuild the consolidated odds file with proper price columns."""
    data_dir = Path(__file__).resolve().parents[2] / "ncaam_historical_data_local"
    
    print("=" * 80)
    print("REBUILDING ODDS CONSOLIDATION WITH PRICES")
    print("=" * 80)
    
    # Define the raw files to use (best versions with prices)
    raw_files = [
        ("2021", data_dir / "odds" / "raw" / "odds_season_2021_o1-fix_20201101_20210430.csv"),
        ("2022", data_dir / "odds" / "raw" / "odds_season_2022_o2-fix_20211101_20220430.csv"),
        ("2023", data_dir / "odds" / "raw" / "odds_season_2023_o3-fix_20221101_20230430.csv"),
        ("2024", data_dir / "odds" / "raw" / "archive" / "odds_season_2024_o4_20231101_20240430.csv"),
        ("2025", data_dir / "odds" / "raw" / "archive" / "odds_season_2025_o5_20241101_20250430.csv"),
    ]
    
    all_dfs = []
    
    for season, file_path in raw_files:
        if file_path.exists():
            df = pd.read_csv(file_path)
            print(f"\n{season}: Loaded {len(df)} rows from {file_path.name}")
            
            # Check price coverage
            if 'spread_home_price' in df.columns:
                coverage = df['spread_home_price'].notna().mean() * 100
                print(f"  Price coverage: {coverage:.1f}%")
            
            # Add season column if not present
            if 'season' not in df.columns:
                df['season'] = int(season)
            
            # Add game_date if not present (derive from commence_time)
            if 'game_date' not in df.columns and 'commence_time' in df.columns:
                df['game_date'] = pd.to_datetime(df['commence_time']).dt.strftime('%Y-%m-%d')
            
            all_dfs.append(df)
        else:
            print(f"\n{season}: File not found - {file_path}")
    
    if not all_dfs:
        raise ValueError("No raw files found!")
    
    # Combine all dataframes
    print("\n" + "=" * 40)
    print("Combining all seasons...")
    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"Combined: {len(combined)} rows")
    
    # Ensure canonical team names are present
    if 'home_team_canonical' not in combined.columns:
        # Use home_team as canonical if not present
        combined['home_team_canonical'] = combined['home_team']
        combined['away_team_canonical'] = combined['away_team']
    
    # Aggregate to one row per game (pick best bookmaker - Pinnacle preferred)
    print("\nAggregating to one row per game...")
    
    def select_best_odds(group):
        """Select best odds row for a game - prefer Pinnacle, then DraftKings."""
        preferred = ['pinnacle', 'draftkings', 'fanduel', 'betmgm']
        for book in preferred:
            match = group[group['bookmaker'].str.lower() == book]
            if len(match) > 0:
                return match.iloc[0]
        # Return first row if no preferred book
        return group.iloc[0]
    
    # Group by game identifiers
    group_cols = ['event_id'] if 'event_id' in combined.columns else ['home_team', 'away_team', 'game_date']
    
    aggregated = combined.groupby(group_cols, as_index=False).apply(select_best_odds, include_groups=False)
    aggregated = aggregated.reset_index(drop=True)
    
    print(f"Aggregated: {len(aggregated)} unique games")
    
    # Verify price coverage by year
    aggregated['year'] = pd.to_datetime(aggregated['game_date']).dt.year
    print("\n--- Price coverage by year (AFTER fix) ---")
    for year in sorted(aggregated['year'].unique()):
        year_data = aggregated[aggregated['year'] == year]
        if 'spread_home_price' in aggregated.columns:
            coverage = year_data['spread_home_price'].notna().mean() * 100
            print(f"  {year}: {len(year_data)} games, {coverage:.1f}% have spread_home_price")
    
    # Drop the year column we added for checking
    aggregated = aggregated.drop(columns=['year'], errors='ignore')
    
    # Save the fixed consolidated file
    output_path = data_dir / "odds" / "normalized" / "odds_consolidated_canonical.csv"
    backup_path = output_path.with_suffix('.csv.backup')
    
    # Backup existing file
    if output_path.exists():
        import shutil
        shutil.copy(output_path, backup_path)
        print(f"\nBacked up existing file to {backup_path.name}")
    
    # Save new file
    aggregated.to_csv(output_path, index=False)
    print(f"Saved fixed consolidated file: {output_path}")
    print(f"Total rows: {len(aggregated)}")
    
    print("\n" + "=" * 80)
    print("CONSOLIDATION FIX COMPLETE")
    print("=" * 80)
    
    return aggregated


if __name__ == "__main__":
    rebuild_consolidated_odds()
