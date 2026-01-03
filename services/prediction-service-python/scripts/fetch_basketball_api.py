#!/usr/bin/env python3
"""
Fetch historical NCAA games from Basketball API.

This script fetches game data and saves to CSV for ML training.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Basketball API configuration
API_KEY = os.environ.get("BASKETBALL_API_KEY", "eea8757fae3c507add2df14800bae25f")
BASE_URL = "https://v1.basketball.api-sports.io"
NCAAM_LEAGUE_ID = 116


def fetch_games(season: str) -> list:
    """Fetch all games for a season."""
    headers = {"x-apisports-key": API_KEY}
    url = f"{BASE_URL}/games"
    
    print(f"Fetching {season} season...")
    resp = requests.get(url, headers=headers, params={"league": NCAAM_LEAGUE_ID, "season": season})
    
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        print(resp.text[:500])
        return []
    
    data = resp.json()
    games = data.get("response", [])
    print(f"  Found {len(games)} games")
    
    return games


def process_games(games: list) -> list:
    """Process games into training data format."""
    processed = []
    
    for g in games:
        status = g.get("status", {}).get("long", "")
        if status != "Game Finished":
            continue
        
        home = g.get("teams", {}).get("home", {})
        away = g.get("teams", {}).get("away", {})
        scores = g.get("scores", {})
        
        home_score = scores.get("home", {}).get("total")
        away_score = scores.get("away", {}).get("total")
        
        if home_score is None or away_score is None:
            continue
        
        # Parse date
        date_str = g.get("date", "")[:10]  # YYYY-MM-DD
        
        processed.append({
            "game_id": g.get("id"),
            "game_date": date_str,
            "home_team": home.get("name", ""),
            "away_team": away.get("name", ""),
            "home_score": home_score,
            "away_score": away_score,
            # Placeholders for odds (would need Odds API historical data)
            "spread_open": None,
            "total_open": None,
        })
    
    return processed


def save_to_csv(games: list, output_path: Path):
    """Save games to CSV."""
    if not games:
        print("No games to save")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=games[0].keys())
        writer.writeheader()
        writer.writerows(games)
    
    print(f"Saved {len(games)} games to {output_path}")


def main():
    print("=" * 60)
    print("Basketball API Game Fetcher")
    print("=" * 60)
    
    all_games = []
    
    # Fetch 2023-24 and 2024-25 seasons
    for season in ["2023-2024", "2024-2025"]:
        games = fetch_games(season)
        processed = process_games(games)
        print(f"  Completed games: {len(processed)}")
        all_games.extend(processed)
        time.sleep(1)  # Rate limiting
    
    print(f"\nTotal completed games: {len(all_games)}")
    
    # Save to CSV
    output_dir = Path(__file__).parent.parent / "training_data"
    output_path = output_dir / "games_2023_2025.csv"
    save_to_csv(all_games, output_path)
    
    # Show sample
    if all_games:
        print("\nSample games:")
        for g in all_games[:5]:
            print(f"  {g['game_date']}: {g['away_team']} @ {g['home_team']} ({g['away_score']}-{g['home_score']})")
    
    print("\n✅ Done!")
    print("\nNote: This data doesn't include opening lines or Barttorvik ratings.")
    print("You'll need to add those for proper ML training.")


if __name__ == "__main__":
    main()
