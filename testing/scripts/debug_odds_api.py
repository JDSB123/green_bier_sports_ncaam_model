#!/usr/bin/env python3
"""Debug script to test historical odds API response structure."""
import requests
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "testing" / "scripts"))

from secrets_manager import get_api_key
API_KEY = get_api_key("odds")

# Test a date we know had events - Dec 3, 2022
print("=== Step 1: Fetch Events ===")
events_url = "https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/events"
resp = requests.get(events_url, params={"apiKey": API_KEY, "date": "2022-12-03T12:00:00Z"})
events = resp.json()
print(f"Events keys: {events.keys()}")
print(f"Data count: {len(events.get('data', []))}")

if events.get("data"):
    event = events["data"][0]
    print(f"First event ID: {event['id']}")
    print(f"Home: {event['home_team']} vs Away: {event['away_team']}")
    print(f"Commence: {event['commence_time']}")
    
    # Now fetch odds for that event
    print("\n=== Step 2: Fetch Odds ===")
    event_id = event["id"]
    commence = event.get("commence_time", "2022-12-03T18:00:00Z")
    
    odds_url = f"https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/events/{event_id}/odds"
    # Test WITH h1 markets (same as the fetch script uses)
    odds_resp = requests.get(odds_url, params={
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "spreads,totals,spreads_h1,totals_h1,h2h",
        "oddsFormat": "american",
        "date": commence
    })
    
    print(f"Status: {odds_resp.status_code}")
    odds_data = odds_resp.json()
    print(f"Top-level keys: {odds_data.keys()}")
    
    data = odds_data.get("data", {})
    print(f"Data type: {type(data)}")
    
    if isinstance(data, dict):
        print(f"Data keys: {data.keys()}")
        bookmakers = data.get("bookmakers", [])
        print(f"Bookmakers count: {len(bookmakers)}")
        
        if bookmakers:
            print("\n=== First Bookmaker ===")
            print(json.dumps(bookmakers[0], indent=2)[:1500])
        else:
            print("\n=== NO BOOKMAKERS - Full response ===")
            print(json.dumps(odds_data, indent=2)[:2000])
    else:
        print(f"Data is not a dict: {type(data)}")
        print(json.dumps(odds_data, indent=2)[:2000])
else:
    print("No events returned!")
