
import pandas as pd
import uuid
import requests
import json
import os
from pathlib import Path

# Paths
SOURCE_FILE = Path("testing/data/backtest_ready.csv")
TARGET_DIR = Path("testing/data/historical_odds")
TARGET_GAMES_FILE = TARGET_DIR / "games_all.csv"
TARGET_DIR.mkdir(parents=True, exist_ok=True)

def prepare_games_file():
    print(f"Reading {SOURCE_FILE}...")
    df = pd.read_csv(SOURCE_FILE)
    
    print("Columns found:", df.columns.tolist())
    
    # Rename columns to match backtest_engine expectation
    rename_map = {
        'game_date': 'date',
        'h1_home_score': 'home_h1',
        'h1_away_score': 'away_h1',
        # home_score, away_score, home_team, away_team are already correct
    }
    
    # Check what we have
    available_cols = set(df.columns)
    final_rename = {k: v for k, v in rename_map.items() if k in available_cols}
    
    df = df.rename(columns=final_rename)
    
    # Add game_id if missing
    if 'game_id' not in df.columns:
        print("Generating game_ids...")
        df['game_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
        
    # Ensure neutral is boolean string
    if 'neutral' in df.columns:
        df['neutral'] = df['neutral'].astype(str).str.lower()
        
    # Save
    print(f"Saving to {TARGET_GAMES_FILE}...")
    df.to_csv(TARGET_GAMES_FILE, index=False)
    print("Games file prepared.")

def fetch_ratings(seasons):
    print("Fetching Barttorvik ratings...")
    BARTTORVIK_BASE = "https://barttorvik.com"
    
    for season in seasons:
        url = f"{BARTTORVIK_BASE}/{season}_team_results.json"
        target_file = TARGET_DIR / f"barttorvik_{season}.json"
        
        if target_file.exists():
            print(f"Ratings for {season} already exist at {target_file}")
            continue
            
        print(f"Fetching season {season} from {url}...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            with open(target_file, 'w') as f:
                json.dump(data, f)
            print(f"Saved {season} ratings.")
        except Exception as e:
            print(f"Failed to fetch {season}: {e}")

if __name__ == "__main__":
    prepare_games_file()
    # Fetch ratings for seasons present in the file + 1 (just in case)
    # Actually just 2023-2026 as requested
    fetch_ratings([2023, 2024, 2025, 2026])
