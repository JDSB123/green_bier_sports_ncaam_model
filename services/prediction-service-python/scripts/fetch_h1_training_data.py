#!/usr/bin/env python3
"""
Fetch 1H Training Data: Combine Odds API lines with ESPN scores.

This script:
1. Fetches 1H spread/total lines from The Odds API (event-specific endpoint)
2. Fetches 1H scores from ESPN API (using team/date matching)
3. Combines them for training 1H ML models

Usage:
    python scripts/fetch_h1_training_data.py --sample-dates 30
    python scripts/fetch_h1_training_data.py --full --start-date 2024-01-01 --end-date 2025-03-15
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import requests

# API Configuration
ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY", "4a0b80471d1ebeeb74c358fa0fcc4a27")
ODDS_BASE_URL = "https://api.the-odds-api.com/v4"
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
SPORT = "basketball_ncaab"


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    name = name.lower()
    # Remove common suffixes
    for suffix in [' hawks', ' eagles', ' bulldogs', ' wildcats', ' tigers', ' bears',
                   ' cardinals', ' panthers', ' cougars', ' lions', ' wolves',
                   ' mustangs', ' rams', ' falcons', ' hornets', ' bees',
                   ' cowboys', ' longhorns', ' cavaliers', ' wolverines',
                   ' spartans', ' gators', ' hurricanes', ' terrapins',
                   ' nittany lions', ' hoosiers', ' boilermakers', ' hawkeyes',
                   ' badgers', ' huskers', ' jayhawks', ' sooners', ' cowboys',
                   ' red raiders', ' horned frogs', ' volunteers', ' razorbacks',
                   ' crimson tide', ' golden eagles', ' blue devils', ' demon deacons',
                   ' tar heels', ' orange', ' fighting irish', ' seminoles',
                   ' yellow jackets', ' hokies', ' mountaineers', ' aggies',
                   ' rebels', ' commodores', ' gamecocks', ' pirates',
                   ' thunder', ' owls', ' penguins', ' mastodons', ' phoenix',
                   ' friars', ' red storm', ' musketeers', ' bluejays', ' seahawks',
                   ' explorers', ' griffs', ' bonnies', ' billikens', ' rams',
                   ' golden griffins', ' minutemen', ' flyers', ' hatters',
                   ' paladins', ' catamounts', ' keydets', ' midshipmen']:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    # Remove state abbreviations
    name = re.sub(r'\s+st\.?$', ' state', name)
    
    # Normalize common variations
    replacements = {
        'uconn': 'connecticut',
        'unc': 'north carolina',
        'lsu': 'louisiana state',
        'uc ': 'california ',
        'ucf': 'central florida',
        'ole miss': 'mississippi',
        'smu': 'southern methodist',
        'tcu': 'texas christian',
        'vcu': 'virginia commonwealth',
        'unlv': 'nevada las vegas',
        'utep': 'texas el paso',
        'umass': 'massachusetts',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    
    return name.strip()


def get_team_match_score(name1: str, name2: str) -> float:
    """Calculate similarity score between two team names."""
    n1 = normalize_team_name(name1)
    n2 = normalize_team_name(name2)
    
    # Exact match
    if n1 == n2:
        return 1.0
    
    # One contains the other
    if n1 in n2 or n2 in n1:
        return 0.8
    
    # Word overlap
    words1 = set(n1.split())
    words2 = set(n2.split())
    overlap = len(words1 & words2)
    total = max(len(words1), len(words2))
    
    return overlap / total if total > 0 else 0


def fetch_odds_events(game_date: str) -> List[Dict]:
    """Fetch events from The Odds API for a date."""
    url = f"{ODDS_BASE_URL}/historical/sports/{SPORT}/events"
    params = {"apiKey": ODDS_API_KEY, "date": f"{game_date}T12:00:00Z"}
    
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []


def fetch_event_h1_odds(event_id: str, game_date: str) -> Optional[Dict]:
    """Fetch 1H odds for a specific event."""
    url = f"{ODDS_BASE_URL}/historical/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "date": f"{game_date}T12:00:00Z",
        "markets": "spreads,totals,spreads_h1,totals_h1",
        "regions": "us",
    }
    
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    return None


def fetch_espn_scoreboard(game_date: str) -> List[Dict]:
    """Fetch ESPN scoreboard for a date to get game IDs.
    
    IMPORTANT: Must use groups=50 (D1) and limit=300 to get ALL games,
    not just the 3-5 nationally featured games.
    """
    url = ESPN_SCOREBOARD_URL
    params = {
        "dates": game_date.replace("-", ""),
        "groups": "50",  # D1 basketball - CRITICAL for getting all games!
        "limit": "300",  # Get all games, not just featured
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        
        games = []
        for event in events:
            comps = event.get("competitions", [])
            if not comps:
                continue
            
            comp = comps[0]
            competitors = comp.get("competitors", [])
            
            home_team = away_team = ""
            home_score = away_score = 0
            
            for c in competitors:
                if c.get("homeAway") == "home":
                    home_team = c.get("team", {}).get("displayName", "")
                    home_score = int(c.get("score", 0) or 0)
                else:
                    away_team = c.get("team", {}).get("displayName", "")
                    away_score = int(c.get("score", 0) or 0)
            
            games.append({
                "espn_id": event.get("id"),
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "completed": comp.get("status", {}).get("type", {}).get("completed", False),
            })
        
        return games
    except Exception as e:
        print(f"    ESPN scoreboard error: {e}")
        return []


def fetch_espn_h1_scores(game_id: str) -> Optional[Dict]:
    """Fetch 1H scores from ESPN game summary."""
    url = f"{ESPN_SUMMARY_URL}?event={game_id}"
    
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        summary = resp.json()
        
        header = summary.get("header", {})
        competitions = header.get("competitions", [])
        if not competitions:
            return None
        
        competitors = competitions[0].get("competitors", [])
        
        home_h1 = away_h1 = None
        home_fg = away_fg = None
        
        for comp in competitors:
            home_away = comp.get("homeAway", "")
            linescores = comp.get("linescores", [])
            
            if linescores:
                h1_score = int(linescores[0].get("displayValue", 0) or 0)
                fg_score = int(comp.get("score", 0) or 0)
                
                if home_away == "home":
                    home_h1 = h1_score
                    home_fg = fg_score
                else:
                    away_h1 = h1_score
                    away_fg = fg_score
        
        if home_h1 is not None and away_h1 is not None:
            return {
                "home_h1": home_h1,
                "away_h1": away_h1,
                "h1_total": home_h1 + away_h1,
                "home_fg": home_fg,
                "away_fg": away_fg,
            }
        
        return None
    except Exception:
        return None


def match_odds_to_espn(odds_games: List[Dict], espn_games: List[Dict]) -> Dict[str, str]:
    """Match Odds API games to ESPN games by team names."""
    matches = {}
    
    for odds_game in odds_games:
        odds_home = odds_game.get("home_team", "")
        odds_away = odds_game.get("away_team", "")
        
        best_match = None
        best_score = 0.5  # Minimum threshold
        
        for espn_game in espn_games:
            if not espn_game.get("completed"):
                continue
            
            espn_home = espn_game.get("home_team", "")
            espn_away = espn_game.get("away_team", "")
            
            home_score = get_team_match_score(odds_home, espn_home)
            away_score = get_team_match_score(odds_away, espn_away)
            
            avg_score = (home_score + away_score) / 2
            
            if avg_score > best_score:
                best_score = avg_score
                best_match = espn_game
        
        if best_match:
            matches[odds_game.get("id")] = best_match.get("espn_id")
    
    return matches


def main():
    parser = argparse.ArgumentParser(description="Fetch 1H training data")
    parser.add_argument("--sample-dates", type=int, default=30, help="Number of dates to sample")
    parser.add_argument("--full", action="store_true", help="Fetch all dates")
    parser.add_argument("--start-date", type=str, default="2024-01-01", help="Start date")
    parser.add_argument("--end-date", type=str, default="2025-03-15", help="End date")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV path")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("1H Training Data Fetcher (Odds API + ESPN)")
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
    print()
    
    all_games = []
    
    for i, game_date in enumerate(fetch_dates):
        print(f"[{i+1}/{len(fetch_dates)}] {game_date}...", end=" ", flush=True)
        
        # 1. Get events from Odds API
        odds_events = fetch_odds_events(game_date)
        
        if not odds_events:
            print("No events")
            continue
        
        # 2. Get ESPN scoreboard for matching
        espn_games = fetch_espn_scoreboard(game_date)
        
        if not espn_games:
            print(f"{len(odds_events)} events, no ESPN data")
            continue
        
        # 3. Match games
        matches = match_odds_to_espn(odds_events, espn_games)
        
        # 4. For matched games, fetch 1H odds and scores
        day_games = []
        
        for odds_event in odds_events[:15]:  # Limit per day
            event_id = odds_event.get("id")
            espn_id = matches.get(event_id)
            
            if not espn_id:
                continue
            
            # Fetch 1H odds
            event_odds = fetch_event_h1_odds(event_id, game_date)
            if not event_odds:
                continue
            
            # Extract odds
            h1_spread = h1_total = fg_spread = fg_total = None
            home_team = odds_event.get("home_team", "")
            
            for bm in event_odds.get("bookmakers", [])[:3]:  # First 3 bookmakers
                for market in bm.get("markets", []):
                    key = market.get("key")
                    outcomes = market.get("outcomes", [])
                    
                    if key == "spreads_h1" and h1_spread is None:
                        for out in outcomes:
                            if out.get("name") == home_team:
                                h1_spread = out.get("point")
                                break
                    
                    if key == "totals_h1" and h1_total is None:
                        for out in outcomes:
                            if out.get("name") == "Over":
                                h1_total = out.get("point")
                                break
                    
                    if key == "spreads" and fg_spread is None:
                        for out in outcomes:
                            if out.get("name") == home_team:
                                fg_spread = out.get("point")
                                break
                    
                    if key == "totals" and fg_total is None:
                        for out in outcomes:
                            if out.get("name") == "Over":
                                fg_total = out.get("point")
                                break
            
            if h1_spread is None and h1_total is None:
                continue
            
            # Fetch 1H scores from ESPN
            scores = fetch_espn_h1_scores(espn_id)
            if not scores:
                continue
            
            game = {
                "date": game_date,
                "home_team": home_team,
                "away_team": odds_event.get("away_team", ""),
                "h1_spread": h1_spread,
                "h1_total": h1_total,
                "fg_spread": fg_spread,
                "fg_total": fg_total,
                "home_h1": scores.get("home_h1"),
                "away_h1": scores.get("away_h1"),
                "actual_h1_total": scores.get("h1_total"),
                "home_fg": scores.get("home_fg"),
                "away_fg": scores.get("away_fg"),
            }
            
            # Calculate outcomes
            if h1_spread is not None and game["home_h1"] is not None:
                margin = game["home_h1"] - game["away_h1"]
                game["h1_spread_cover"] = 1 if (margin + h1_spread) > 0 else 0
            
            if h1_total is not None and game["actual_h1_total"] is not None:
                game["h1_total_over"] = 1 if game["actual_h1_total"] > h1_total else 0
            
            day_games.append(game)
            time.sleep(0.1)
        
        print(f"{len(day_games)} games with 1H data")
        all_games.extend(day_games)
        
        time.sleep(0.3)
    
    print()
    print("=" * 70)
    print(f"Total games with 1H data: {len(all_games)}")
    
    # Stats
    h1_spread_count = sum(1 for g in all_games if g.get("h1_spread") is not None)
    h1_total_count = sum(1 for g in all_games if g.get("h1_total") is not None)
    h1_covers = sum(1 for g in all_games if g.get("h1_spread_cover") is not None)
    h1_overs = sum(1 for g in all_games if g.get("h1_total_over") is not None)
    
    print(f"  With 1H spread: {h1_spread_count}")
    print(f"  With 1H total: {h1_total_count}")
    print(f"  With spread outcome: {h1_covers}")
    print(f"  With total outcome: {h1_overs}")
    
    if h1_covers > 0:
        cover_rate = sum(g.get("h1_spread_cover", 0) for g in all_games if g.get("h1_spread_cover") is not None) / h1_covers
        print(f"  Home cover rate: {cover_rate:.1%}")
    
    if h1_overs > 0:
        over_rate = sum(g.get("h1_total_over", 0) for g in all_games if g.get("h1_total_over") is not None) / h1_overs
        print(f"  Over rate: {over_rate:.1%}")
    
    # Save
    output_dir = Path(__file__).parent.parent / "training_data"
    output_path = args.output or output_dir / "h1_training_data.csv"
    
    if all_games:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = list(all_games[0].keys())
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_games)
        
        print(f"\nSaved to {output_path}")
    
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
