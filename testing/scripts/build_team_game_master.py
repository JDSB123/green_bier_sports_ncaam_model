#!/usr/bin/env python3
"""Build TEAM-GAME master dataset from canonical backtest master.

Creates a single, canonical table with one row per team per game,
using ONLY canonical team names from the canonical backtest dataset.

Input (from Azure via AzureDataReader):
  - backtest_datasets/backtest_master_enhanced.csv (if available)
    else backtest_datasets/backtest_master.csv

Output:
  - backtest_datasets/team_game_master.csv

Each game produces two rows:
  - side = "home"  (team = home_team,  opponent = away_team, is_home = True)
  - side = "away"  (team = away_team,  opponent = home_team, is_home = False)

This table is intended as the single source of truth for
team-level, game-by-game modeling, with no alternate team name columns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Ensure project root is on sys.path so `testing` imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_data_reader import get_azure_reader
from testing.azure_io import write_csv


def build_team_game_master(
    output_blob: str = "backtest_datasets/team_game_master.csv",
    use_enhanced: bool = True,
) -> pd.DataFrame:
    """Build and save the team-game master dataset.

    Args:
        output_blob: Azure blob path for the output CSV.
        use_enhanced: If True, prefer the enhanced backtest master
            (with NCAAR-derived features) when available.

    Returns:
        The constructed team-game DataFrame.
    """
    reader = get_azure_reader()

    print("=" * 80)
    print("TEAM-GAME MASTER BUILDER")
    print("=" * 80)

    # Load canonical backtest master from Azure
    print("Step 1: Loading canonical backtest master...")
    df = reader.read_backtest_master(enhanced=use_enhanced)
    print(f"  Loaded {len(df):,} games, {len(df.columns)} columns")

    # Determine game date column
    date_col: Optional[str] = None
    if "game_date" in df.columns:
        date_col = "game_date"
    elif "date" in df.columns:
        date_col = "date"

    if date_col is None:
        raise ValueError("Backtest master is missing a game_date/date column")

    # Ensure datetime
    df[date_col] = pd.to_datetime(df[date_col])

    required_team_cols = ["home_team", "away_team"]
    for col in required_team_cols:
        if col not in df.columns:
            raise ValueError(f"Backtest master missing required column: {col}")

    print(f"  Using '{date_col}' as game date column")

    # Build per-team records
    print("\nStep 2: Building per-team rows...")
    records = []
    for _, row in df.iterrows():
        # Common fields copied from the game row
        base = row.to_dict()
        base["game_date"] = row[date_col]

        # Home team row
        home_rec = base.copy()
        home_rec["team"] = row["home_team"]
        home_rec["opponent"] = row["away_team"]
        home_rec["is_home"] = True
        home_rec["side"] = "home"
        records.append(home_rec)

        # Away team row
        away_rec = base.copy()
        away_rec["team"] = row["away_team"]
        away_rec["opponent"] = row["home_team"]
        away_rec["is_home"] = False
        away_rec["side"] = "away"
        records.append(away_rec)

    team_df = pd.DataFrame.from_records(records)
    team_df["game_date"] = pd.to_datetime(team_df["game_date"])

    print(f"  Built {len(team_df):,} team-game rows")

    # Optional: enforce canonical team names only by relying on the fact
    # that backtest master has already been through canonical ingestion.

    # Save to Azure
    print("\nStep 3: Saving team-game master to Azure...")
    write_csv(output_blob, team_df, index=False)
    print(f"  ✓ Saved: {output_blob}")

    # Summary
    print("\n" + "=" * 80)
    print("TEAM-GAME MASTER SUMMARY")
    print("=" * 80)
    print(f"Rows:    {len(team_df):,}")
    print(f"Columns: {len(team_df.columns)}")
    print(f"Date range: {team_df['game_date'].min()} to {team_df['game_date'].max()}")

    return team_df


def main():
    parser = argparse.ArgumentParser(description="Build team-game master dataset")
    parser.add_argument(
        "--output",
        type=str,
        default="backtest_datasets/team_game_master.csv",
        help="Output blob path for team-game master CSV",
    )
    parser.add_argument(
        "--no-enhanced",
        action="store_true",
        help="Use base backtest master (no enhanced features)",
    )

    args = parser.parse_args()
    use_enhanced = not args.no_enhanced

    build_team_game_master(output_blob=args.output, use_enhanced=use_enhanced)


if __name__ == "__main__":
    main()
