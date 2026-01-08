"""
Reorganize odds data into structured format by market type and period.

Structure:
  odds/
  ├── raw/                      # Original API pulls (pre-canonicalization)
  │   ├── spreads/
  │   │   ├── fg/               # Full-game spreads
  │   │   └── h1/               # First-half spreads
  │   ├── totals/
  │   │   ├── fg/
  │   │   └── h1/
  │   ├── moneylines/
  │   └── archive/              # Old mixed files
  ├── canonical/                # Post-QA (team names resolved)
  │   ├── spreads/
  │   │   ├── fg/
  │   │   └── h1/
  │   └── totals/
  │       ├── fg/
  │       └── h1/
  └── normalized/               # Legacy (to be deprecated)

Usage:
    python scripts/reorganize_odds.py
"""

import pandas as pd
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent / "ncaam_historical_data_local" / "odds"


def split_consolidated_to_markets():
    """Split the consolidated file into market-specific raw files."""
    
    consolidated_path = ROOT / "normalized" / "odds_consolidated_canonical.csv"
    
    if not consolidated_path.exists():
        print(f"ERROR: {consolidated_path} not found")
        return
    
    print(f"Reading {consolidated_path}...")
    df = pd.read_csv(consolidated_path)
    print(f"  Total rows: {len(df)}")
    
    # Identify which rows have which markets
    has_fg_spread = df['spread'].notna()
    has_h1_spread = df['h1_spread'].notna()
    has_fg_total = df['total'].notna()
    has_h1_total = df['h1_total'].notna()
    
    # Define columns for each market type
    base_cols = ['event_id', 'commence_time', 'home_team', 'away_team', 
                 'bookmaker', 'timestamp', 'game_date', 'season', 'is_march_madness']
    
    # RAW files keep original team names (home_team, away_team)
    # CANONICAL files have home_team_canonical, away_team_canonical
    
    raw_base_cols = ['event_id', 'commence_time', 'home_team', 'away_team', 
                     'bookmaker', 'timestamp', 'game_date', 'season', 'is_march_madness']
    
    canonical_cols = ['event_id', 'commence_time', 'home_team', 'away_team',
                      'home_team_canonical', 'away_team_canonical',
                      'bookmaker', 'timestamp', 'game_date', 'season', 'is_march_madness']
    
    # Split into market files
    outputs = {
        'canonical/spreads/fg/spreads_fg_all.csv': (
            df[has_fg_spread],
            canonical_cols + ['spread']
        ),
        'canonical/spreads/h1/spreads_h1_all.csv': (
            df[has_h1_spread],
            canonical_cols + ['h1_spread']
        ),
        'canonical/totals/fg/totals_fg_all.csv': (
            df[has_fg_total],
            canonical_cols + ['total']
        ),
        'canonical/totals/h1/totals_h1_all.csv': (
            df[has_h1_total],
            canonical_cols + ['h1_total']
        ),
    }
    
    for output_path, (data, cols) in outputs.items():
        out_file = ROOT / output_path
        available_cols = [c for c in cols if c in data.columns]
        subset = data[available_cols].copy()
        
        if len(subset) > 0:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            subset.to_csv(out_file, index=False)
            print(f"  ✓ {output_path}: {len(subset)} rows")
        else:
            print(f"  - {output_path}: 0 rows (skipped)")


def archive_legacy_files():
    """Move old mixed files to archive."""
    
    legacy_files = [
        "odds_2020_2021.csv",
        "odds_2020_2021_part2.csv",
        "odds_h1_20231105_20240109.csv",
        "odds_h1_20240110_20240415.csv",
        "odds_h1_20251227_20260106.csv",
        "odds_with_h1_20231101_20240415.csv",
    ]
    
    archive_dir = ROOT / "raw" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    for fname in legacy_files:
        src = ROOT / fname
        if src.exists():
            dst = archive_dir / fname
            shutil.move(str(src), str(dst))
            print(f"  Archived: {fname}")


def move_raw_api_files():
    """Move raw API files from odds/raw/ into categorized subdirs based on content."""
    
    raw_dir = ROOT / "raw"
    
    # Find all CSV files directly in raw/ (not in subdirs)
    raw_files = list(raw_dir.glob("*.csv"))
    
    for f in raw_files:
        # Read first few rows to determine content
        try:
            df = pd.read_csv(f, nrows=10)
            
            # Determine market type from columns or filename
            if 'h1' in f.name.lower() or 'h1_spread' in df.columns:
                if 'spread' in f.name.lower() or 'spread' in df.columns or 'h1_spread' in df.columns:
                    dest = raw_dir / "spreads" / "h1" / f.name
                elif 'total' in f.name.lower():
                    dest = raw_dir / "totals" / "h1" / f.name
                else:
                    dest = raw_dir / "archive" / f.name
            else:
                if 'spread' in f.name.lower() or 'spread' in df.columns:
                    dest = raw_dir / "spreads" / "fg" / f.name
                elif 'total' in f.name.lower():
                    dest = raw_dir / "totals" / "fg" / f.name
                else:
                    dest = raw_dir / "archive" / f.name
            
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
            print(f"  Moved: {f.name} -> {dest.parent.name}/{dest.name}")
            
        except Exception as e:
            print(f"  Error processing {f.name}: {e}")


def create_schema_docs():
    """Create schema documentation for each market type."""
    
    schemas = {
        "spreads": {
            "description": "Point spread betting lines",
            "columns": {
                "event_id": "Unique game identifier from odds API",
                "commence_time": "Game start time (UTC ISO8601)",
                "home_team": "Original home team name from source",
                "away_team": "Original away team name from source",
                "home_team_canonical": "(canonical only) Resolved home team name",
                "away_team_canonical": "(canonical only) Resolved away team name",
                "bookmaker": "Sportsbook name (draftkings, fanduel, etc)",
                "spread": "(FG) Full-game spread for home team",
                "h1_spread": "(H1) First-half spread for home team",
                "timestamp": "When odds were captured",
                "game_date": "Game date (YYYY-MM-DD)",
                "season": "Season year (Nov-Apr, e.g. 2024 = 2023-24 season)",
                "is_march_madness": "Boolean flag for tournament games",
            },
            "notes": [
                "Negative spread means home team is favored",
                "Multiple bookmakers per game creates multiple rows",
            ]
        },
        "totals": {
            "description": "Over/under total points betting lines",
            "columns": {
                "total": "(FG) Full-game total points line",
                "h1_total": "(H1) First-half total points line",
            }
        }
    }
    
    schema_file = ROOT.parent / "schemas" / "odds_schema.json"
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(schema_file, 'w') as f:
        json.dump(schemas, f, indent=2)
    
    print(f"  Created: {schema_file}")


def main():
    print("=" * 60)
    print("REORGANIZING ODDS DATA")
    print("=" * 60)
    
    print("\n1. Splitting consolidated data into market files...")
    split_consolidated_to_markets()
    
    print("\n2. Archiving legacy mixed files...")
    archive_legacy_files()
    
    print("\n3. Creating schema documentation...")
    create_schema_docs()
    
    print("\n" + "=" * 60)
    print("DONE. New structure:")
    print("""
  odds/
  ├── raw/                  # Pre-canonicalization (original team names)
  │   ├── spreads/fg/
  │   ├── spreads/h1/
  │   ├── totals/fg/
  │   ├── totals/h1/
  │   └── archive/          # Legacy mixed files
  └── canonical/            # Post-QA (team names resolved)
      ├── spreads/fg/       # spreads_fg_all.csv
      ├── spreads/h1/       # spreads_h1_all.csv
      ├── totals/fg/        # totals_fg_all.csv
      └── totals/h1/        # totals_h1_all.csv
    """)


if __name__ == "__main__":
    main()
