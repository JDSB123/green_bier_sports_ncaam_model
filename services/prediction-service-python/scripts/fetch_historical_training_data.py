#!/usr/bin/env python3
"""
Fetch comprehensive historical training data.

This script:
1. Loads game outcomes from Basketball API (already fetched)
2. Fetches historical opening odds from The Odds API
3. Combines into training-ready CSV

Usage:
    python scripts/fetch_historical_training_data.py --games training_data/games_2023_2025.csv
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

import requests

# API Configuration
ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY", "4a0b80471d1ebeeb74c358fa0fcc4a27")
ODDS_BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_ncaab"


def load_games_csv(csv_path: Path) -> List[Dict]:
    """Load games from CSV."""
    games = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            games.append({
                "game_id": row.get("game_id"),
                "game_date": row.get("game_date"),
                "home_team": row.get("home_team"),
                "away_team": row.get("away_team"),
                "home_score": int(row.get("home_score", 0)),
                "away_score": int(row.get("away_score", 0)),
            })
    return games


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    if not name:
        return ""
    # Common substitutions
    name = name.lower().strip()
    name = name.replace("state", "st")
    name = name.replace("university", "")
    name = name.replace("college", "")
    name = name.replace("the ", "")
    # Remove common suffixes
    for suffix in ["tigers", "bulldogs", "wildcats", "bears", "eagles", "hawks", 
                   "cardinals", "blue devils", "tar heels", "hoosiers", "wolverines",
                   "buckeyes", "spartans", "fighting irish", "crimson tide"]:
        name = name.replace(suffix, "")
    return name.strip()


def match_teams(api_home: str, api_away: str, games: List[Dict]) -> Optional[Dict]:
    """Match API team names to our games."""
    api_home_norm = normalize_team_name(api_home)
    api_away_norm = normalize_team_name(api_away)
    
    for game in games:
        game_home_norm = normalize_team_name(game["home_team"])
        game_away_norm = normalize_team_name(game["away_team"])
        
        # Check if teams match (home/away order may differ)
        if (api_home_norm in game_home_norm or game_home_norm in api_home_norm) and \
           (api_away_norm in game_away_norm or game_away_norm in api_away_norm):
            return game
        
        # Check reversed
        if (api_home_norm in game_away_norm or game_away_norm in api_home_norm) and \
           (api_away_norm in game_home_norm or game_home_norm in api_away_norm):
            return game
    
    return None


def fetch_historical_odds(event_date: str) -> Tuple[int, Optional[Dict]]:
    """Fetch historical odds for a specific date."""
    url = f"{ODDS_BASE_URL}/historical/sports/{SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "date": event_date,
        "markets": "spreads,totals",
        "regions": "us",
        "bookmakers": "fanduel,draftkings,betmgm,pinnacle",
    }
    
    resp = requests.get(url, params=params)
    
    if resp.status_code == 200:
        return resp.status_code, resp.json()
    else:
        return resp.status_code, None


def extract_opening_lines(odds_data: Dict) -> Dict[str, Dict]:
    """Extract opening lines from odds data."""
    lines = {}
    
    events = odds_data.get("data", [])
    
    for event in events:
        event_id = event.get("id")
        home = event.get("home_team")
        away = event.get("away_team")
        
        if not home or not away:
            continue
        
        # Key by normalized team names
        key = f"{normalize_team_name(home)}_{normalize_team_name(away)}"
        
        # Get first available bookmaker odds
        spread = None
        total = None
        
        for bm in event.get("bookmakers", []):
            for market in bm.get("markets", []):
                mkey = market.get("key")
                outcomes = market.get("outcomes", [])
                
                if mkey == "spreads" and spread is None:
                    for outcome in outcomes:
                        if outcome.get("name") == home:
                            spread = outcome.get("point")
                            break
                
                if mkey == "totals" and total is None:
                    for outcome in outcomes:
                        if outcome.get("name") == "Over":
                            total = outcome.get("point")
                            break
                
                if spread is not None and total is not None:
                    break
            if spread is not None and total is not None:
                break
        
        if spread is not None or total is not None:
            lines[key] = {
                "home_team": home,
                "away_team": away,
                "spread": spread,
                "total": total,
            }
    
    return lines


def main():
    parser = argparse.ArgumentParser(description="Fetch historical training data")
    parser.add_argument("--games", type=Path, required=True, help="Games CSV file")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--sample-dates", type=int, default=30, help="Number of dates to sample")
    parser.add_argument("--full", action="store_true", help="Fetch all dates (slow)")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Historical Training Data Fetcher")
    print("=" * 70)
    
    # Load games
    print(f"\nLoading games from {args.games}...")
    games = load_games_csv(args.games)
    print(f"Loaded {len(games)} games")
    
    # Get unique dates
    dates = sorted(set(g["game_date"] for g in games))
    print(f"Spanning {len(dates)} unique dates: {dates[0]} to {dates[-1]}")
    
    # Sample dates to fetch (API has limits)
    if args.full:
        fetch_dates = dates
    else:
        # Sample evenly spaced dates
        step = max(1, len(dates) // args.sample_dates)
        fetch_dates = dates[::step]
    
    print(f"Fetching odds for {len(fetch_dates)} dates...")
    
    # Create game lookup by date
    games_by_date = defaultdict(list)
    for game in games:
        games_by_date[game["game_date"]].append(game)
    
    # Fetch odds
    all_lines = {}
    matched_count = 0
    
    for i, game_date in enumerate(fetch_dates):
        # Convert date to ISO format for API
        api_date = f"{game_date}T12:00:00Z"
        
        print(f"  [{i+1}/{len(fetch_dates)}] {game_date}...", end=" ")
        
        status, data = fetch_historical_odds(api_date)
        
        if status != 200 or data is None:
            print(f"Error: {status}")
            continue
        
        lines = extract_opening_lines(data)
        print(f"Found {len(lines)} games with odds")
        
        # Match to our games
        day_games = games_by_date.get(game_date, [])
        for key, line_data in lines.items():
            matched_game = match_teams(line_data["home_team"], line_data["away_team"], day_games)
            if matched_game:
                matched_game["spread_open"] = line_data["spread"]
                matched_game["total_open"] = line_data["total"]
                matched_count += 1
        
        # Rate limiting
        time.sleep(0.5)
    
    print(f"\nMatched {matched_count} games with odds data")
    
    # Count games with odds
    games_with_odds = [g for g in games if g.get("spread_open") is not None]
    print(f"Games with spread: {len(games_with_odds)}")
    
    # Save output
    output_path = args.output or args.games.parent / "training_data_with_odds.csv"
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["game_id", "game_date", "home_team", "away_team", 
                     "home_score", "away_score", "spread_open", "total_open"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(games)
    
    print(f"\nSaved to {output_path}")
    
    # Summary
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
For full ML training, you also need Barttorvik ratings per game date.
Options:
1. Use current ratings as proxy (introduces some bias)
2. Scrape historical Barttorvik data
3. Use average ratings as baseline features

For testing, we can proceed with games that have odds.
""")


if __name__ == "__main__":
    main()
