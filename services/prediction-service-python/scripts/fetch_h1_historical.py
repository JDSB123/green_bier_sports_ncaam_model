#!/usr/bin/env python3
"""
Fetch Historical 1st Half Odds and Scores from The Odds API.

The Odds API provides:
- spreads_h1: 1st Half Spreads
- totals_h1: 1st Half Totals
- Historical odds snapshots with scores

Usage:
    python scripts/fetch_h1_historical.py --sample-dates 50
    python scripts/fetch_h1_historical.py --full
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import requests

# API Configuration
API_KEY = os.environ.get("THE_ODDS_API_KEY", "4a0b80471d1ebeeb74c358fa0fcc4a27")
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_ncaab"


def fetch_historical_events(event_date: str) -> Tuple[int, List[Dict]]:
    """
    Fetch list of historical events for a date.
    """
    url = f"{BASE_URL}/historical/sports/{SPORT}/events"
    params = {
        "apiKey": API_KEY,
        "date": event_date,
    }
    
    resp = requests.get(url, params=params, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        return resp.status_code, data.get("data", [])
    else:
        return resp.status_code, []


def fetch_event_odds(event_id: str, event_date: str) -> Tuple[int, Optional[Dict]]:
    """
    Fetch odds for a specific event including 1H markets.
    
    The event-specific endpoint supports 1H markets unlike the bulk endpoint.
    """
    url = f"{BASE_URL}/historical/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "date": event_date,
        "markets": "spreads,totals,spreads_h1,totals_h1",
        "regions": "us",
    }
    
    resp = requests.get(url, params=params, timeout=30)
    
    if resp.status_code == 200:
        return resp.status_code, resp.json()
    else:
        return resp.status_code, None


def fetch_historical_scores(event_date: str) -> Tuple[int, Optional[Dict]]:
    """
    Fetch historical scores for completed games.
    
    The scores endpoint includes final and period scores.
    """
    url = f"{BASE_URL}/historical/sports/{SPORT}/scores"
    params = {
        "apiKey": API_KEY,
        "date": event_date,
        "daysFrom": 1,  # Get scores from games that ended within 1 day
    }
    
    resp = requests.get(url, params=params, timeout=30)
    
    if resp.status_code == 200:
        return resp.status_code, resp.json()
    else:
        return resp.status_code, None


def extract_h1_data(odds_data: Dict, scores_data: Optional[Dict] = None) -> List[Dict]:
    """
    Extract 1H spread and total lines from historical odds data.
    """
    games = []
    
    events = odds_data.get("data", [])
    
    # Build scores lookup if available
    scores_lookup = {}
    if scores_data and "data" in scores_data:
        for event in scores_data["data"]:
            event_id = event.get("id")
            scores = event.get("scores", [])
            if scores and event.get("completed"):
                scores_lookup[event_id] = {
                    "home_score": None,
                    "away_score": None,
                    "home_h1": None,
                    "away_h1": None,
                }
                for score in scores:
                    if score.get("name") == event.get("home_team"):
                        scores_lookup[event_id]["home_score"] = score.get("score")
                    elif score.get("name") == event.get("away_team"):
                        scores_lookup[event_id]["away_score"] = score.get("score")
    
    for event in events:
        event_id = event.get("id")
        home = event.get("home_team")
        away = event.get("away_team")
        commence_time = event.get("commence_time", "")
        
        if not home or not away:
            continue
        
        game = {
            "event_id": event_id,
            "game_date": commence_time[:10] if commence_time else "",
            "home_team": home,
            "away_team": away,
            "h1_spread": None,
            "h1_total": None,
            "fg_spread": None,
            "fg_total": None,
        }
        
        # Extract odds from first available bookmaker
        for bm in event.get("bookmakers", []):
            for market in bm.get("markets", []):
                key = market.get("key")
                outcomes = market.get("outcomes", [])
                
                if key == "spreads_h1" and game["h1_spread"] is None:
                    for outcome in outcomes:
                        if outcome.get("name") == home:
                            game["h1_spread"] = outcome.get("point")
                            break
                
                if key == "totals_h1" and game["h1_total"] is None:
                    for outcome in outcomes:
                        if outcome.get("name") == "Over":
                            game["h1_total"] = outcome.get("point")
                            break
                
                if key == "spreads" and game["fg_spread"] is None:
                    for outcome in outcomes:
                        if outcome.get("name") == home:
                            game["fg_spread"] = outcome.get("point")
                            break
                
                if key == "totals" and game["fg_total"] is None:
                    for outcome in outcomes:
                        if outcome.get("name") == "Over":
                            game["fg_total"] = outcome.get("point")
                            break
        
        # Add scores if available
        if event_id in scores_lookup:
            game.update(scores_lookup[event_id])
        
        # Only include games with 1H data
        if game["h1_spread"] is not None or game["h1_total"] is not None:
            games.append(game)
    
    return games


def main():
    parser = argparse.ArgumentParser(description="Fetch historical 1H data")
    parser.add_argument("--sample-dates", type=int, default=30, help="Number of dates to sample")
    parser.add_argument("--full", action="store_true", help="Fetch all dates")
    parser.add_argument("--start-date", type=str, default="2023-11-10", help="Start date")
    parser.add_argument("--end-date", type=str, default="2025-03-15", help="End date")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV path")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Historical 1H Data Fetcher (The Odds API)")
    print("=" * 70)
    
    # Generate date range
    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")
    
    all_dates = []
    current = start
    while current <= end:
        all_dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    print(f"Date range: {args.start_date} to {args.end_date} ({len(all_dates)} days)")
    
    # Sample dates
    if args.full:
        fetch_dates = all_dates
    else:
        step = max(1, len(all_dates) // args.sample_dates)
        fetch_dates = all_dates[::step]
    
    print(f"Fetching {len(fetch_dates)} dates...")
    
    all_games = []
    
    for i, game_date in enumerate(fetch_dates):
        api_date = f"{game_date}T12:00:00Z"
        
        print(f"  [{i+1}/{len(fetch_dates)}] {game_date}...", end=" ", flush=True)
        
        # First get list of events for this date
        status, events = fetch_historical_events(api_date)
        
        if status != 200:
            print(f"Error getting events: {status}")
            continue
        
        if not events:
            print("No events")
            continue
        
        h1_count = 0
        day_games = []
        
        # Fetch odds for each event (with 1H markets)
        for event in events[:20]:  # Limit to first 20 per day to avoid API overload
            event_id = event.get("id")
            home = event.get("home_team")
            away = event.get("away_team")
            commence = event.get("commence_time", "")
            
            status, odds_data = fetch_event_odds(event_id, api_date)
            
            if status != 200 or odds_data is None:
                continue
            
            event_odds = odds_data.get("data", {})
            
            game = {
                "event_id": event_id,
                "game_date": commence[:10] if commence else game_date,
                "home_team": home,
                "away_team": away,
                "h1_spread": None,
                "h1_total": None,
                "fg_spread": None,
                "fg_total": None,
            }
            
            # Extract odds from bookmakers
            for bm in event_odds.get("bookmakers", []):
                for market in bm.get("markets", []):
                    key = market.get("key")
                    outcomes = market.get("outcomes", [])
                    
                    if key == "spreads_h1" and game["h1_spread"] is None:
                        for outcome in outcomes:
                            if outcome.get("name") == home:
                                game["h1_spread"] = outcome.get("point")
                                break
                    
                    if key == "totals_h1" and game["h1_total"] is None:
                        for outcome in outcomes:
                            if outcome.get("name") == "Over":
                                game["h1_total"] = outcome.get("point")
                                break
                    
                    if key == "spreads" and game["fg_spread"] is None:
                        for outcome in outcomes:
                            if outcome.get("name") == home:
                                game["fg_spread"] = outcome.get("point")
                                break
                    
                    if key == "totals" and game["fg_total"] is None:
                        for outcome in outcomes:
                            if outcome.get("name") == "Over":
                                game["fg_total"] = outcome.get("point")
                                break
            
            if game["h1_spread"] is not None:
                h1_count += 1
            
            day_games.append(game)
            time.sleep(0.1)  # Rate limit between events
        
        print(f"{len(day_games)} games, {h1_count} with 1H spread")
        all_games.extend(day_games)
        
        time.sleep(0.3)
    
    print(f"\nTotal games with 1H data: {len(all_games)}")
    
    # Count games with each field
    h1_spread_count = sum(1 for g in all_games if g.get("h1_spread") is not None)
    h1_total_count = sum(1 for g in all_games if g.get("h1_total") is not None)
    
    print(f"  With 1H spread: {h1_spread_count}")
    print(f"  With 1H total: {h1_total_count}")
    
    # Save to CSV
    output_dir = Path(__file__).parent.parent / "training_data"
    output_path = args.output or output_dir / "h1_historical_odds.csv"
    
    if all_games:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = list(all_games[0].keys())
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_games)
        
        print(f"\nSaved to {output_path}")
    
    # Show sample
    print("\nSample games with 1H data:")
    for g in all_games[:5]:
        if g.get("h1_spread") is not None:
            print(f"  {g['game_date']}: {g['away_team']} @ {g['home_team']}")
            print(f"    1H Spread: {g['h1_spread']}, 1H Total: {g['h1_total']}")
    
    print("\n" + "=" * 70)
    print("NOTE: The Odds API historical scores may not include period breakdowns.")
    print("To train 1H models, we need to combine with another source for 1H scores.")
    print("=" * 70)


if __name__ == "__main__":
    main()
