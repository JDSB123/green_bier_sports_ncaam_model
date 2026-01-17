#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix canonical master team name canonicalization.

Actions:
1. Use home_canonical/away_canonical as the single source of truth (100% coverage, 334 unique)
2. Remove redundant canonical columns (_x, _y, _odds variants)
3. Rename columns for clarity
4. Update schema
"""
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=" * 80)
    print("FIXING CANONICAL MASTER TEAM NAMES")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load data
    master_path = Path("manifests/canonical_training_data_master.csv")

    # Create backup first
    backup_path = Path(f"manifests/canonical_training_data_master.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    print(f"Creating backup: {backup_path.name}")
    shutil.copy(master_path, backup_path)

    df = pd.read_csv(master_path)
    print(f"Loaded: {len(df):,} rows, {len(df.columns)} columns\n")

    # ANALYSIS
    print("-" * 80)
    print("CURRENT STATE ANALYSIS")
    print("-" * 80)

    # Show team canonical columns
    team_cols = [c for c in df.columns if 'canonical' in c.lower() and 'team' in c.lower()]
    print(f"Team canonical columns found: {len(team_cols)}")
    for col in team_cols:
        coverage = df[col].notna().sum()
        unique = df[col].nunique()
        print(f"  {col}: {coverage:,} ({coverage/len(df)*100:.1f}%), {unique} unique")

    print(f"\nBest column: home_canonical / away_canonical")
    print(f"  - 100% coverage")
    print(f"  - 334 unique teams (appropriate for D1)")
    print(f"  - Clean names (e.g., 'North Carolina' not 'North Carolina Tar Heels')")

    # FIXES
    print("\n" + "-" * 80)
    print("APPLYING FIXES")
    print("-" * 80)

    # 1. Verify home_canonical and away_canonical exist and are complete
    if 'home_canonical' not in df.columns or 'away_canonical' not in df.columns:
        print("ERROR: home_canonical or away_canonical missing!")
        return 1

    if df['home_canonical'].isna().any() or df['away_canonical'].isna().any():
        print("ERROR: home_canonical or away_canonical have missing values!")
        return 1

    print("✓ Verified home_canonical and away_canonical are complete")

    # 2. Remove redundant canonical columns
    columns_to_remove = []
    for col in team_cols:
        if col not in ['home_canonical', 'away_canonical']:
            columns_to_remove.append(col)

    if columns_to_remove:
        print(f"\nRemoving {len(columns_to_remove)} redundant columns:")
        for col in columns_to_remove:
            print(f"  - {col}")
        df = df.drop(columns=columns_to_remove)

    # 3. Remove other redundant team columns (merge artifacts)
    redundant_team_cols = []
    for col in df.columns:
        if any(suffix in col for suffix in ['_x', '_y']) and 'team' in col.lower():
            # Keep if it's the only version, otherwise mark for removal
            base_col = col.replace('_x', '').replace('_y', '')
            if base_col in df.columns or col in ['home_team_x', 'away_team_x']:
                # These are likely from merges, we have original versions
                if col not in ['home_team_x', 'away_team_x']:  # Keep _x as original for now
                    redundant_team_cols.append(col)

    if redundant_team_cols:
        print(f"\nRemoving {len(redundant_team_cols)} merge artifact columns:")
        for col in redundant_team_cols:
            print(f"  - {col}")
        df = df.drop(columns=redundant_team_cols)

    # 4. Rename home_team_x/away_team_x to home_team_original/away_team_original if needed
    if 'home_team_x' in df.columns and 'home_team_original' in df.columns:
        # We already have home_team_original, drop home_team_x
        print("\nRemoving home_team_x (home_team_original exists)")
        df = df.drop(columns=['home_team_x'])
    elif 'home_team_x' in df.columns:
        print("\nRenaming home_team_x -> home_team_original")
        df = df.rename(columns={'home_team_x': 'home_team_original'})

    if 'away_team_x' in df.columns and 'away_team_original' in df.columns:
        print("Removing away_team_x (away_team_original exists)")
        df = df.drop(columns=['away_team_x'])
    elif 'away_team_x' in df.columns:
        print("Renaming away_team_x -> away_team_original")
        df = df.rename(columns={'away_team_x': 'away_team_original'})

    # VALIDATION
    print("\n" + "-" * 80)
    print("VALIDATION")
    print("-" * 80)

    # Check team columns remaining
    remaining_team_cols = [c for c in df.columns if 'team' in c.lower()]
    print(f"\nRemaining team columns ({len(remaining_team_cols)}):")
    for col in sorted(remaining_team_cols):
        coverage = df[col].notna().sum()
        unique = df[col].nunique() if df[col].notna().any() else 0
        print(f"  {col}: {coverage:,} ({coverage/len(df)*100:.1f}%), {unique} unique")

    # Verify canonical columns
    home_unique = set(df['home_canonical'].dropna())
    away_unique = set(df['away_canonical'].dropna())
    total_unique = home_unique | away_unique

    print(f"\nCanonical team validation:")
    print(f"  Home unique: {len(home_unique)}")
    print(f"  Away unique: {len(away_unique)}")
    print(f"  Total unique: {len(total_unique)}")

    if len(total_unique) <= 350:
        print("  ✓ PASS: Team count appropriate for D1 basketball")
    else:
        print(f"  ⚠️  WARNING: {len(total_unique)} teams is higher than expected")

    # Check for potential duplicates
    print(f"\nChecking for potential duplicate team names...")
    teams = sorted(total_unique)
    duplicates = []
    for i, team1 in enumerate(teams):
        for team2 in teams[i+1:]:
            if team1.lower() in team2.lower() or team2.lower() in team1.lower():
                if team1 != team2:
                    duplicates.append((team1, team2))

    if duplicates:
        print(f"  Found {len(duplicates)} potential duplicates:")
        for t1, t2 in duplicates[:10]:  # Show first 10
            print(f"    - '{t1}' vs '{t2}'")
        if len(duplicates) > 10:
            print(f"    ... and {len(duplicates) - 10} more")
    else:
        print("  ✓ No obvious duplicates found")

    # SAVE
    print("\n" + "-" * 80)
    print("SAVING CHANGES")
    print("-" * 80)

    print(f"\nOriginal: {len(pd.read_csv(master_path).columns)} columns")
    print(f"New: {len(df.columns)} columns")
    print(f"Removed: {len(pd.read_csv(master_path).columns) - len(df.columns)} columns")

    df.to_csv(master_path, index=False)
    print(f"\n✓ Saved to: {master_path}")
    print(f"✓ Backup at: {backup_path}")

    # SUMMARY
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Consolidated to single canonical team columns:")
    print(f"  - home_canonical ({len(home_unique)} unique)")
    print(f"  - away_canonical ({len(away_unique)} unique)")
    print(f"✓ Removed {len(columns_to_remove) + len(redundant_team_cols)} redundant columns")
    print(f"✓ Total unique teams: {len(total_unique)}")
    print("\nNext: Update scripts to use home_canonical/away_canonical only")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    exit(main())
