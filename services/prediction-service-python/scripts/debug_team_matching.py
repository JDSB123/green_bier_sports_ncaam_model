#!/usr/bin/env python3
"""Debug team name matching between Odds API and ESPN."""

import requests
from datetime import datetime

date = "2024-02-15"

# Odds API teams
ODDS_API_KEY = "4a0b80471d1ebeeb74c358fa0fcc4a27"
url = f"https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/events"
resp = requests.get(url, params={"apiKey": ODDS_API_KEY, "date": f"{date}T12:00:00Z"})
odds_events = resp.json().get("data", [])

print("=" * 70)
print(f"ODDS API TEAMS ({date}): {len(odds_events)} events")
print("=" * 70)
odds_games = []
for e in odds_events[:15]:
    away = e.get("away_team", "")
    home = e.get("home_team", "")
    odds_games.append((away, home))
    print(f"  {away} @ {home}")

# ESPN teams
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
resp = requests.get(ESPN_URL, params={"dates": date.replace("-", "")})
espn_events = resp.json().get("events", [])

print()
print("=" * 70)
print(f"ESPN TEAMS ({date}): {len(espn_events)} events")
print("=" * 70)
espn_games = []
for e in espn_events[:15]:
    comps = e.get("competitions", [])
    if comps:
        competitors = comps[0].get("competitors", [])
        home = away = ""
        for c in competitors:
            if c.get("homeAway") == "home":
                home = c.get("team", {}).get("displayName", "")
            else:
                away = c.get("team", {}).get("displayName", "")
        espn_games.append((away, home))
        print(f"  {away} @ {home}")

# Try matching
print()
print("=" * 70)
print("MATCHING ANALYSIS")
print("=" * 70)


def normalize(name):
    """Simple normalization."""
    n = name.lower().strip()
    # Remove mascots
    parts = n.split()
    # Keep first 2-3 words typically (team location)
    if len(parts) > 2:
        n = " ".join(parts[:2])
    return n


for odds_away, odds_home in odds_games[:10]:
    odds_home_norm = normalize(odds_home)
    odds_away_norm = normalize(odds_away)
    
    best_match = None
    best_score = 0
    
    for espn_away, espn_home in espn_games:
        espn_home_norm = normalize(espn_home)
        espn_away_norm = normalize(espn_away)
        
        # Check if any overlap
        if odds_home_norm in espn_home_norm or espn_home_norm in odds_home_norm:
            home_score = 0.8
        elif odds_home_norm == espn_home_norm:
            home_score = 1.0
        else:
            home_score = 0
        
        if odds_away_norm in espn_away_norm or espn_away_norm in odds_away_norm:
            away_score = 0.8
        elif odds_away_norm == espn_away_norm:
            away_score = 1.0
        else:
            away_score = 0
        
        avg = (home_score + away_score) / 2
        if avg > best_score:
            best_score = avg
            best_match = (espn_away, espn_home)
    
    if best_match:
        print(f"MATCH: {odds_away} @ {odds_home}")
        print(f"  --> {best_match[0]} @ {best_match[1]} (score: {best_score:.2f})")
    else:
        print(f"NO MATCH: {odds_away} @ {odds_home}")
        print(f"  Normalized: {odds_away_norm} @ {odds_home_norm}")
    print()

# Show examples of naming differences
print("=" * 70)
print("NAMING DIFFERENCES EXAMPLES")
print("=" * 70)
print("Odds API format: 'Texas Longhorns', 'Michigan State Spartans'")
print("ESPN format: 'Texas', 'Michigan State Spartans'")
print()
print("Common mismatches:")
print("  Odds: 'UConn Huskies' vs ESPN: 'Connecticut Huskies'")
print("  Odds: 'Miami (FL) Hurricanes' vs ESPN: 'Miami Hurricanes'")
print("  Odds: 'LSU Tigers' vs ESPN: 'LSU Tigers' (usually OK)")
print("  Odds: 'St. John's Red Storm' vs ESPN: 'St. John's Red Storm'")
