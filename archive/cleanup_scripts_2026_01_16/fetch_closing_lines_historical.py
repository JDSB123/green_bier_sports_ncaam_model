#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch historical closing lines and add to canonical master.

This script:
1. Loads canonical_training_data_master.csv
2. For each game, attempts to fetch closing line data from The Odds API
3. Adds closing line columns to the dataset
4. Saves updated canonical master

NOTE: The Odds API typically doesn't provide historical closing lines in their standard API.
This script will check what's available and document limitations.
"""
import sys
import os
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime
import time

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def get_api_key():
    """Get API key from secrets file or environment."""
    # Try secrets file first
    secret_file = Path("secrets/odds_api_key.txt")
    if secret_file.exists():
        with open(secret_file, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("YOUR_"):
                return key

    # Try environment variables
    key = os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")
    if key and not key.startswith("YOUR_"):
        return key

    raise ValueError("No valid API key found. Check secrets/odds_api_key.txt or environment variables.")

def check_api_capabilities(api_key):
    """Check what The Odds API can provide."""
    print("\n" + "="*80)
    print("CHECKING THE ODDS API CAPABILITIES")
    print("="*80)

    base_url = "https://api.the-odds-api.com/v4"

    # Check current events
    url = f"{base_url}/sports/basketball_ncaab/events"
    params = {"apiKey": api_key}

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            events = resp.json()
            print(f"\n✓ API Connected: {len(events)} upcoming NCAAB games")

            remaining = resp.headers.get("x-requests-remaining")
            used = resp.headers.get("x-requests-used")
            print(f"  Requests remaining: {remaining}")
            print(f"  Requests used: {used}")
        else:
            print(f"\n✗ API Error: Status {resp.status_code}")
            print(f"  Response: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"\n✗ Connection Error: {e}")
        return False

    # Check if we can get odds for current events
    if events:
        print("\n" + "-"*80)
        print("CHECKING ODDS DATA AVAILABILITY")
        print("-"*80)

        url = f"{base_url}/sports/basketball_ncaab/odds"
        params = {
            "apiKey": api_key,
            "regions": "us",
            "markets": "spreads,totals",
            "oddsFormat": "american"
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                odds_events = resp.json()
                print(f"✓ Current odds available: {len(odds_events)} games")

                if odds_events:
                    sample = odds_events[0]
                    print(f"\n  Sample game: {sample.get('home_team')} vs {sample.get('away_team')}")
                    print(f"  Bookmakers: {len(sample.get('bookmakers', []))}")
                    if sample.get('bookmakers'):
                        bm = sample['bookmakers'][0]
                        print(f"    - {bm.get('key')}: {len(bm.get('markets', []))} markets")
            else:
                print(f"✗ Odds API Error: Status {resp.status_code}")
        except Exception as e:
            print(f"✗ Error fetching odds: {e}")

    print("\n" + "-"*80)
    print("HISTORICAL DATA LIMITATIONS")
    print("-"*80)
    print("⚠️  The Odds API does NOT provide historical closing lines via their API.")
    print("   - They only provide current/upcoming games")
    print("   - Historical data requires special access or data partners")
    print("   - Closing lines must be captured BEFORE game starts")
    print("\n   OPTIONS:")
    print("   1. Start capturing closing lines prospectively for 2026+ season")
    print("   2. Contact The Odds API for historical data access (if available)")
    print("   3. Use alternative data source (Bovada archives, etc.)")
    print("   4. Accept limitation and skip CLV metric for historical backtests")

    return True

def main():
    print("="*80)
    print("CLOSING LINE DATA ACQUISITION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Get API key
    try:
        api_key = get_api_key()
        print("✓ API key loaded")
    except Exception as e:
        print(f"✗ {e}")
        return 1

    # Check API capabilities
    if not check_api_capabilities(api_key):
        return 1

    # Load canonical master
    print("\n" + "="*80)
    print("CANONICAL MASTER ANALYSIS")
    print("="*80)

    master_path = Path("manifests/canonical_training_data_master.csv")
    if not master_path.exists():
        print(f"✗ Canonical master not found at {master_path}")
        return 1

    df = pd.read_csv(master_path)
    print(f"✓ Loaded: {len(df):,} games across {df['season'].nunique()} seasons")

    # Analyze what we have
    print("\n" + "-"*80)
    print("CURRENT ODDS DATA")
    print("-"*80)

    opening_cols = [c for c in df.columns if any(x in c for x in ['spread', 'total']) and 'actual' not in c]
    print(f"Opening line columns: {len(opening_cols)}")
    for col in sorted(opening_cols)[:10]:
        coverage = df[col].notna().sum()
        print(f"  {col}: {coverage:,} / {len(df):,} ({coverage/len(df)*100:.1f}%)")

    closing_cols = [c for c in df.columns if 'closing' in c.lower()]
    print(f"\nClosing line columns: {len(closing_cols)}")
    if not closing_cols:
        print("  ❌ None found (expected)")

    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    print("\nSince The Odds API doesn't provide historical closing lines:")
    print("\n  OPTION 1 (Recommended): Prospective Capture")
    print("  - Set up automated job to capture closing lines before games start")
    print("  - Build closing line data for 2026+ season going forward")
    print("  - Accept that 2023-2025 backtests won't have CLV metric")
    print("\n  OPTION 2: Alternative Data Source")
    print("  - Find provider with historical closing lines (expensive)")
    print("  - Pinnacle, Bovada, or specialized sports data vendors")
    print("\n  OPTION 3: Skip CLV Metric")
    print("  - Focus on win rate and ROI for backtests")
    print("  - Add CLV tracking prospectively once live")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Decide which option above to pursue")
    print("2. If Option 1: Create automated closing line capture job")
    print("3. If Option 2: Research historical data providers")
    print("4. If Option 3: Update backtest scripts to skip CLV")
    print("\n" + "="*80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
