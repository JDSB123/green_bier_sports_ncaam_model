
import pandas as pd
import uuid
import requests
import json
import os
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from testing.data_paths import DATA_PATHS
from testing.azure_io import read_csv, write_csv, write_json, blob_exists

# Paths - Azure is the only source of truth.
SOURCE_BLOB = str(DATA_PATHS.backtest_datasets / "training_data_with_odds.csv")
TARGET_DIR_BLOB = str(DATA_PATHS.odds_normalized)
TARGET_GAMES_BLOB = str(DATA_PATHS.scores_fg / "games_all.csv")

def build_tags(
    dataset: str,
    season: int | None = None,
    source: str | None = None,
    scope: str | None = None,
) -> dict:
    tags = {"dataset": dataset}
    if season is not None:
        tags["season"] = str(season)
    if source:
        tags["source"] = source
    if scope:
        tags["scope"] = scope
    return tags

def prepare_games_file():
    print(f"Reading {SOURCE_BLOB}...")
    df = read_csv(SOURCE_BLOB)
    
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
    print(f"Saving to {TARGET_GAMES_BLOB}...")
    tags = build_tags("scores_fg", source="prepare_backtest", scope="all")
    write_csv(TARGET_GAMES_BLOB, df, tags=tags)
    print("Games file prepared.")

def fetch_ratings(seasons):
    print("Fetching Barttorvik ratings...")
    BARTTORVIK_BASE = "https://barttorvik.com"
    
    for season in seasons:
        url = f"{BARTTORVIK_BASE}/{season}_team_results.json"
        target_blob = f"{TARGET_DIR_BLOB}/barttorvik_{season}.json"
        
        if blob_exists(target_blob):
            print(f"Ratings for {season} already exist at {target_blob}")
            continue
            
        print(f"Fetching season {season} from {url}...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            tags = build_tags("barttorvik_ratings", season=season, source="barttorvik", scope="season")
            write_json(target_blob, data, tags=tags)
            print(f"Saved {season} ratings.")
        except Exception as e:
            print(f"Failed to fetch {season}: {e}")

if __name__ == "__main__":
    prepare_games_file()
    # Fetch ratings for seasons present in the file + 1 (just in case)
    # Actually just 2023-2026 as requested
    fetch_ratings([2023, 2024, 2025, 2026])
