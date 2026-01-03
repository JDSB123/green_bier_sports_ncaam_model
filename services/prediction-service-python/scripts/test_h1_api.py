#!/usr/bin/env python3
"""Test The Odds API for 1H historical data."""
import requests
import json

API_KEY = "4a0b80471d1ebeeb74c358fa0fcc4a27"
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_ncaab"

# Test 1: Standard historical odds
print("Test 1: Standard historical markets (spreads, totals)")
url = f"{BASE_URL}/historical/sports/{SPORT}/odds"
params = {
    "apiKey": API_KEY,
    "date": "2024-01-15T12:00:00Z",
    "markets": "spreads,totals",
    "regions": "us",
}
resp = requests.get(url, params=params, timeout=30)
print(f"  Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    events = data.get("data", [])
    print(f"  Events: {len(events)}")
    if events:
        e = events[0]
        print(f"  Sample: {e.get('away_team')} @ {e.get('home_team')}")
        bms = e.get("bookmakers", [])
        if bms:
            markets = [m.get("key") for m in bms[0].get("markets", [])]
            print(f"  Markets available: {markets}")
else:
    print(f"  Error: {resp.text[:200]}")

# Test 2: Try 1H markets
print("\nTest 2: 1H markets (spreads_h1, totals_h1)")
params["markets"] = "spreads_h1,totals_h1"
resp = requests.get(url, params=params, timeout=30)
print(f"  Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    events = data.get("data", [])
    print(f"  Events: {len(events)}")
    if events:
        # Check if any have 1H markets
        h1_count = 0
        for e in events:
            for bm in e.get("bookmakers", []):
                for m in bm.get("markets", []):
                    if "h1" in m.get("key", ""):
                        h1_count += 1
                        break
        print(f"  Events with 1H markets: {h1_count}")
else:
    print(f"  Error: {resp.text[:200]}")

# Test 3: Event-specific odds (may have more markets)
print("\nTest 3: Check event-specific endpoint for additional markets")
events_url = f"{BASE_URL}/historical/sports/{SPORT}/events"
params = {"apiKey": API_KEY, "date": "2024-01-15T12:00:00Z"}
resp = requests.get(events_url, params=params, timeout=30)
print(f"  Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    events = data.get("data", [])
    print(f"  Events: {len(events)}")
    if events:
        event_id = events[0].get("id")
        print(f"  Sample event ID: {event_id}")
        
        # Try event-specific odds
        event_odds_url = f"{BASE_URL}/historical/sports/{SPORT}/events/{event_id}/odds"
        params = {
            "apiKey": API_KEY,
            "date": "2024-01-15T12:00:00Z",
            "markets": "spreads_h1,totals_h1",
            "regions": "us",
        }
        resp2 = requests.get(event_odds_url, params=params, timeout=30)
        print(f"  Event odds status: {resp2.status_code}")
        if resp2.status_code == 200:
            event_data = resp2.json()
            print(f"  Event data keys: {list(event_data.keys())}")
        else:
            print(f"  Error: {resp2.text[:200]}")
else:
    print(f"  Error: {resp.text[:200]}")

# Test 4: Check historical scores endpoint
print("\nTest 4: Historical scores (for game outcomes)")
scores_url = f"{BASE_URL}/historical/sports/{SPORT}/scores"
params = {"apiKey": API_KEY, "date": "2024-01-16T12:00:00Z"}
resp = requests.get(scores_url, params=params, timeout=30)
print(f"  Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    events = data.get("data", [])
    print(f"  Games with scores: {len(events)}")
    if events:
        e = events[0]
        print(f"  Sample: {e.get('away_team')} @ {e.get('home_team')}")
        print(f"  Completed: {e.get('completed')}")
        scores = e.get("scores", [])
        print(f"  Scores: {scores}")
else:
    print(f"  Error: {resp.text[:200]}")

# Test 5: Event-specific odds with 1H markets
print("\nTest 5: Event-specific odds endpoint with 1H markets")
events_url = f"{BASE_URL}/historical/sports/{SPORT}/events"
params = {"apiKey": API_KEY, "date": "2024-01-15T12:00:00Z"}
resp = requests.get(events_url, params=params, timeout=30)

if resp.status_code == 200:
    events = resp.json().get("data", [])
    if events:
        event_id = events[0].get("id")
        print(f"  Testing event: {events[0].get('away_team')} @ {events[0].get('home_team')}")
        
        # Get event-specific odds
        event_url = f"{BASE_URL}/historical/sports/{SPORT}/events/{event_id}/odds"
        params = {
            "apiKey": API_KEY,
            "date": "2024-01-15T12:00:00Z",
            "markets": "spreads,totals,spreads_h1,totals_h1",
            "regions": "us",
        }
        resp2 = requests.get(event_url, params=params, timeout=30)
        print(f"  Status: {resp2.status_code}")
        
        if resp2.status_code == 200:
            data = resp2.json()
            event_data = data.get("data", {})
            bms = event_data.get("bookmakers", [])
            print(f"  Bookmakers: {len(bms)}")
            
            if bms:
                all_markets = set()
                for bm in bms:
                    for m in bm.get("markets", []):
                        all_markets.add(m.get("key"))
                print(f"  Markets found: {sorted(all_markets)}")
                
                # Check for 1H specifically
                has_h1 = any("h1" in m for m in all_markets)
                print(f"  Has 1H markets: {has_h1}")
        else:
            print(f"  Error: {resp2.text[:200]}")

# Test 6: Current scores endpoint (check for period breakdowns)
print("\nTest 6: Current scores endpoint (period breakdown check)")
scores_url = f"{BASE_URL}/sports/{SPORT}/scores"
params = {"apiKey": API_KEY, "daysFrom": 3, "dateFormat": "iso"}
resp = requests.get(scores_url, params=params, timeout=30)
print(f"  Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    print(f"  Total games: {len(data)}")
    
    # Find completed games
    completed = [g for g in data if g.get("completed")]
    print(f"  Completed: {len(completed)}")
    
    if completed:
        g = completed[0]
        print(f"  Sample: {g.get('away_team')} @ {g.get('home_team')}")
        print(f"  Scores: {g.get('scores')}")
        print(f"  Keys: {list(g.keys())}")
else:
    print(f"  Error: {resp.text[:200]}")

print("\nDone!")
