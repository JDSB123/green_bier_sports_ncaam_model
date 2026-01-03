#!/usr/bin/env python3
"""
Fetch historical odds from The Odds API.

Checks available endpoints and fetches historical betting lines.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path

import requests

# The Odds API configuration
API_KEY = os.environ.get("THE_ODDS_API_KEY", "4a0b80471d1ebeeb74c358fa0fcc4a27")
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_ncaab"


def get_historical_events(event_date: str) -> list:
    """
    Try to get historical events for a specific date.
    
    Note: The Odds API may require premium plan for historical data.
    """
    url = f"{BASE_URL}/historical/sports/{SPORT}/events"
    params = {
        "apiKey": API_KEY,
        "date": event_date,
    }
    
    resp = requests.get(url, params=params)
    return resp.status_code, resp.json() if resp.status_code == 200 else resp.text


def get_historical_odds(event_date: str, markets: str = "spreads,totals") -> dict:
    """
    Try to get historical odds for a specific date.
    """
    url = f"{BASE_URL}/historical/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "date": event_date,
        "markets": markets,
        "regions": "us",
    }
    
    resp = requests.get(url, params=params)
    return resp.status_code, resp.json() if resp.status_code == 200 else resp.text


def check_api_quota():
    """Check remaining API quota."""
    url = f"{BASE_URL}/sports"
    params = {"apiKey": API_KEY}
    
    resp = requests.get(url, params=params)
    
    remaining = resp.headers.get("x-requests-remaining", "unknown")
    used = resp.headers.get("x-requests-used", "unknown")
    
    print(f"API Quota: {remaining} remaining, {used} used")
    return resp.status_code == 200


def main():
    print("=" * 60)
    print("The Odds API - Historical Data Check")
    print("=" * 60)
    
    # Check quota first
    print("\nChecking API access...")
    if not check_api_quota():
        print("Error: Could not access API")
        return
    
    # Try historical endpoints
    print("\n" + "-" * 40)
    print("Testing historical endpoints...")
    print("-" * 40)
    
    # Try a date from 2024 season
    test_date = "2024-01-15T00:00:00Z"
    
    print(f"\nTrying historical events for {test_date}...")
    status, data = get_historical_events(test_date)
    
    if status == 200:
        print(f"Success! Found data")
        if isinstance(data, list):
            print(f"  Events: {len(data)}")
            for event in data[:3]:
                print(f"    - {event.get('home_team')} vs {event.get('away_team')}")
        else:
            print(f"  Response type: {type(data)}")
            print(f"  {str(data)[:200]}")
    else:
        print(f"  Status: {status}")
        if isinstance(data, dict):
            print(f"  Message: {data.get('message', data)}")
        else:
            print(f"  Response: {str(data)[:200]}")
    
    print(f"\nTrying historical odds for {test_date}...")
    status, data = get_historical_odds(test_date)
    
    if status == 200:
        print(f"Success! Found odds data")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
    else:
        print(f"  Status: {status}")
        if isinstance(data, dict):
            print(f"  Message: {data.get('message', data)}")
        else:
            print(f"  Response: {str(data)[:200]}")
    
    # Alternative: Get current events to understand structure
    print("\n" + "-" * 40)
    print("Getting current/upcoming events...")
    print("-" * 40)
    
    url = f"{BASE_URL}/sports/{SPORT}/events"
    params = {"apiKey": API_KEY, "dateFormat": "iso"}
    resp = requests.get(url, params=params)
    
    if resp.status_code == 200:
        events = resp.json()
        print(f"Found {len(events)} upcoming events")
        for event in events[:3]:
            print(f"  - {event.get('commence_time')}: {event.get('away_team')} @ {event.get('home_team')}")
    else:
        print(f"Error: {resp.status_code}")
    
    print("\n" + "-" * 40)
    print("Getting current odds...")
    print("-" * 40)
    
    url = f"{BASE_URL}/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "spreads,totals",
        "bookmakers": "pinnacle,fanduel",
    }
    resp = requests.get(url, params=params)
    
    if resp.status_code == 200:
        odds_data = resp.json()
        print(f"Found odds for {len(odds_data)} events")
        
        for event in odds_data[:2]:
            print(f"\n  {event.get('away_team')} @ {event.get('home_team')}")
            for bm in event.get("bookmakers", [])[:1]:
                print(f"    {bm.get('title')}:")
                for market in bm.get("markets", []):
                    key = market.get("key")
                    outcomes = market.get("outcomes", [])
                    if key == "spreads" and outcomes:
                        print(f"      Spread: {outcomes[0].get('point')} ({outcomes[0].get('name')})")
                    elif key == "totals" and outcomes:
                        print(f"      Total: {outcomes[0].get('point')}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text[:200])
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
The Odds API historical endpoints may require:
1. Premium/Pro subscription tier
2. Historical add-on package

Alternative approaches:
1. Collect odds going forward (capture at game time)
2. Use OddsPortal web scraping (not recommended)
3. Use proxy market lines (average spreads from Barttorvik)
4. Train without market features (ratings-only model)

For now, we can train a ratings-only ML model using:
- Barttorvik ratings (can be scraped or use synthetic values)
- Game outcomes (already fetched: 11,763 games)
""")


if __name__ == "__main__":
    main()
