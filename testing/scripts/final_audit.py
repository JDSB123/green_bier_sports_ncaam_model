#!/usr/bin/env python3
"""Final data audit - show exactly what we have."""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "ncaam_historical_data_local" / "backtest_datasets"

def audit():
    bt = pd.read_csv(DATA_DIR / "backtest_master.csv", low_memory=False)
    
    print("=" * 70)
    print("ACTUAL DATA INVENTORY - backtest_master.csv")
    print("=" * 70)
    
    print(f"Total games: {len(bt):,}")
    print(f"Total columns: {len(bt.columns)}")
    print(f"Date range: {bt['game_date'].min()} to {bt['game_date'].max()}")
    
    # Count by year
    bt['year'] = pd.to_datetime(bt['game_date']).dt.year
    print("\nGames by year:")
    for year in sorted(bt['year'].unique()):
        count = len(bt[bt['year'] == year])
        print(f"  {year}: {count:,}")
    
    # Feature coverage
    print("\nFeature coverage:")
    features = {
        'Scores': ['home_score', 'away_score'],
        'FG Odds': ['fg_spread', 'fg_spread_home_price'],
        'H1 Odds': ['h1_spread', 'h1_spread_home_price'],
        'H1 Scores': ['home_h1', 'h1_actual_margin'],
        'Barttorvik': ['home_adj_o', 'home_adj_d'],
        'ncaahoopR': ['home_box_efg', 'home_box_ppp_last3']
    }
    
    for name, cols in features.items():
        valid_cols = [c for c in cols if c in bt.columns]
        if valid_cols:
            coverage = bt[valid_cols[0]].notna().sum()
            pct = coverage / len(bt) * 100
            print(f"  {name}: {coverage:,} / {len(bt):,} ({pct:.1f}%)")
        else:
            print(f"  {name}: MISSING")
    
    # Backtest ready by year (2023-2026)
    print("\n" + "=" * 70)
    print("BACKTEST-READY GAMES (scores + odds + prices + ratings)")
    print("=" * 70)
    
    for year in [2023, 2024, 2025, 2026]:
        year_df = bt[bt['year'] == year].copy()
        if len(year_df) == 0:
            print(f"  {year}: No data")
            continue
        
        # FG ready - using .values to avoid index issues
        fg_ready = pd.Series([True] * len(year_df), index=year_df.index)
        if 'actual_margin' in year_df.columns:
            fg_ready = fg_ready & year_df['actual_margin'].notna().values
        if 'fg_spread' in year_df.columns:
            fg_ready = fg_ready & year_df['fg_spread'].notna().values
        if 'fg_spread_home_price' in year_df.columns:
            fg_ready = fg_ready & year_df['fg_spread_home_price'].notna().values
        if 'home_adj_o' in year_df.columns:
            fg_ready = fg_ready & year_df['home_adj_o'].notna().values
        
        # H1 ready
        h1_ready = fg_ready.copy()
        if 'h1_actual_margin' in year_df.columns:
            h1_ready = h1_ready & year_df['h1_actual_margin'].notna().values
        if 'h1_spread' in year_df.columns:
            h1_ready = h1_ready & year_df['h1_spread'].notna().values
        
        # Full features (with ncaahoopR)
        full_ready = fg_ready.copy()
        if 'home_box_efg' in year_df.columns:
            full_ready = full_ready & year_df['home_box_efg'].notna().values
        
        print(f"  {year}: {len(year_df):,} games")
        print(f"         FG ready: {fg_ready.sum():,} ({fg_ready.sum()/len(year_df)*100:.0f}%)")
        print(f"         H1 ready: {h1_ready.sum():,} ({h1_ready.sum()/len(year_df)*100:.0f}%)")
        print(f"         Full features: {full_ready.sum():,} ({full_ready.sum()/len(year_df)*100:.0f}%)")


def debug_years():
    bt = pd.read_csv(DATA_DIR / "backtest_master.csv", low_memory=False)
    bt['year'] = pd.to_datetime(bt['game_date']).dt.year
    
    print("\nDEBUG - Column values by year:")
    for year in [2023, 2024, 2025]:
        y = bt[bt['year'] == year]
        print(f"\n{year} ({len(y)} games):")
        print(f"  fg_spread not null: {y['fg_spread'].notna().sum()}")
        col = 'fg_spread_home_price'
        if col in y.columns:
            print(f"  {col} not null: {y[col].notna().sum()}")
        else:
            print(f"  {col}: COLUMN MISSING")
        col = 'home_adj_o'
        if col in y.columns:
            print(f"  {col} not null: {y[col].notna().sum()}")
        else:
            print(f"  {col}: COLUMN MISSING")


def check_merge_potential():
    print("\n" + "=" * 70)
    print("MERGE POTENTIAL - BT vs ODDS")
    print("=" * 70)
    
    bt = pd.read_csv(DATA_DIR / "backtest_master.csv", low_memory=False)
    odds = pd.read_csv(DATA_DIR.parent / "odds" / "normalized" / "odds_consolidated_canonical.csv", low_memory=False)
    
    bt['year'] = pd.to_datetime(bt['game_date']).dt.year
    odds['year'] = pd.to_datetime(odds['game_date']).dt.year
    
    for year in [2024, 2025]:
        bt_y = bt[bt['year'] == year]
        odds_y = odds[odds['year'] == year]
        
        print(f"\n{year}:")
        print(f"  BT games: {len(bt_y)}")
        print(f"  Odds games: {len(odds_y)} with {odds_y['spread_home_price'].notna().sum()} prices")
        
        # Check key overlap
        bt_keys = set(bt_y['home_team'].str.lower() + '_' + bt_y['game_date'].astype(str))
        odds_keys = set(odds_y['home_team'].str.lower() + '_' + odds_y['game_date'].astype(str))
        overlap = bt_keys.intersection(odds_keys)
        print(f"  Key overlap: {len(overlap)} games SHOULD get prices")


if __name__ == "__main__":
    audit()
    debug_years()
    check_merge_potential()
