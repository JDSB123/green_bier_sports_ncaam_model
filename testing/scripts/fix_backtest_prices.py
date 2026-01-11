#!/usr/bin/env python3
"""
Fix backtest_master.csv prices for 2024-2025.

The odds_consolidated_canonical.csv has prices.
The backtest_master.csv doesn't have them merged.
This script fixes that.
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "ncaam_historical_data_local"


def fix():
    print("=" * 70)
    print("FIXING BACKTEST_MASTER.CSV PRICES")
    print("=" * 70)
    
    # Load files
    bt_path = DATA_DIR / "backtest_datasets" / "backtest_master.csv"
    odds_path = DATA_DIR / "odds" / "normalized" / "odds_consolidated_canonical.csv"
    
    bt = pd.read_csv(bt_path, low_memory=False)
    odds = pd.read_csv(odds_path, low_memory=False)
    
    print(f"BT: {len(bt)} games")
    print(f"Odds: {len(odds)} games")
    
    # Check current state
    bt['year'] = pd.to_datetime(bt['game_date']).dt.year
    for year in [2024, 2025]:
        y = bt[bt['year'] == year]
        prices = y['fg_spread_home_price'].notna().sum()
        print(f"  BEFORE {year}: {prices} prices")
    
    # Create merge key
    bt['merge_key'] = bt['home_team'].str.lower().str.strip() + '_' + bt['game_date'].astype(str)
    odds['merge_key'] = odds['home_team'].str.lower().str.strip() + '_' + odds['game_date'].astype(str)
    
    # Get odds columns to update
    price_cols = ['spread_home_price', 'spread_away_price', 'total_over_price', 'total_under_price',
                  'h1_spread_home_price', 'h1_spread_away_price', 'h1_total_over_price', 'h1_total_under_price',
                  'moneyline_home_price', 'moneyline_away_price']
    price_cols = [c for c in price_cols if c in odds.columns]
    
    # Create odds lookup with price columns
    odds_lookup = odds[['merge_key'] + price_cols].drop_duplicates(subset=['merge_key'], keep='first')
    print(f"Odds lookup: {len(odds_lookup)} unique games")
    
    # Rename odds columns to BT format
    rename_map = {
        'spread_home_price': 'fg_spread_home_price',
        'spread_away_price': 'fg_spread_away_price', 
        'total_over_price': 'fg_total_over_price',
        'total_under_price': 'fg_total_under_price',
    }
    
    # For each row in BT that's missing prices, try to fill from odds
    for idx in bt.index:
        key = bt.loc[idx, 'merge_key']
        
        # Skip if already has prices
        if pd.notna(bt.loc[idx, 'fg_spread_home_price']):
            continue
        
        # Look up in odds
        match = odds_lookup[odds_lookup['merge_key'] == key]
        if len(match) > 0:
            for old_col, new_col in rename_map.items():
                if old_col in match.columns:
                    bt.loc[idx, new_col] = match[old_col].iloc[0]
            # Also update H1 prices
            for h1_col in ['h1_spread_home_price', 'h1_spread_away_price', 'h1_total_over_price', 'h1_total_under_price']:
                if h1_col in match.columns:
                    bt.loc[idx, h1_col] = match[h1_col].iloc[0]
    
    # Cleanup
    bt = bt.drop(columns=['merge_key', 'year'], errors='ignore')
    
    # Check result
    bt['year'] = pd.to_datetime(bt['game_date']).dt.year
    for year in [2024, 2025]:
        y = bt[bt['year'] == year]
        prices = y['fg_spread_home_price'].notna().sum()
        print(f"  AFTER {year}: {prices} prices")
    
    bt = bt.drop(columns=['year'], errors='ignore')
    
    # Save
    bt.to_csv(bt_path, index=False)
    print(f"\nSaved: {bt_path}")
    
    print("\n" + "=" * 70)
    print("FIX COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    fix()
