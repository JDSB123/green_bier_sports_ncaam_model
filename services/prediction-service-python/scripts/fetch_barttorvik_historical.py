#!/usr/bin/env python3
"""
Fetch Historical Barttorvik Ratings.

Barttorvik provides season-end ratings as JSON files.
These can be used for ML training (with end-of-season ratings as proxy).

Note: These are SEASON-END ratings, not daily. This introduces some bias
for early-season games, but provides consistent metrics for training.

Usage:
    python scripts/fetch_barttorvik_historical.py --seasons 2021 2022 2023 2024
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import requests


def fetch_barttorvik_season(season: int) -> List[Dict]:
    """
    Fetch Barttorvik ratings for a season.
    
    Args:
        season: Season year (e.g., 2024 for 2023-24 season)
    
    Returns:
        List of team rating dicts
    """
    url = f"https://barttorvik.com/{season}_team_results.json"
    
    headers = {
        "User-Agent": "NCAAM-ML-Research/1.0",
    }
    
    print(f"  Fetching {season} season from {url}...")
    
    resp = requests.get(url, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        print(f"    Error: {resp.status_code}")
        return []
    
    # Barttorvik returns array-of-arrays, need to parse
    data = resp.json()
    
    if not data:
        return []
    
    # Check format - could be array-of-arrays or array-of-objects
    sample = data[0]
    
    if isinstance(sample, list):
        # Array-of-arrays format - 2025 season has 45 fields
        # Index mapping from ratings-sync-go:
        # [0]=rank, [1]=team, [2]=conf, [3]=record, [4]=adjoe, [5]=adjoe_rank,
        # [6]=adjde, [7]=adjde_rank, [8]=barthag, [9]=barthag_rank,
        # [10]=wins, [11]=losses, [12]=conf_wins, [13]=conf_losses, [14]=conf_record,
        # [15]=efg_o, [16]=efg_d, [17]=tor, [18]=tord, [19]=orb_o, [20]=drb_d,
        # [21]=ftr_o, [22]=ftr_d, [23]=2p_o, [24]=2p_d, [25]=3p_o, [26]=3p_d,
        # [27]=3pr_o, [28]=3pr_d, [44]=adj_tempo (LAST FIELD)
        teams = []
        for row in data:
            if len(row) < 45:
                continue  # Skip incomplete records
            try:
                # Parse wins/losses as ints
                wins = int(float(row[10])) if row[10] else 0
                losses = int(float(row[11])) if row[11] else 0
                
                teams.append({
                    "team": row[1],
                    "conf": row[2] if len(row) > 2 else "",
                    "games": wins + losses,
                    "wins": wins,
                    "losses": losses,
                    "adj_o": float(row[4]) if row[4] else 100.0,
                    "adj_d": float(row[6]) if row[6] else 100.0,
                    "barthag": float(row[8]) if row[8] else 0.5,
                    "efg": float(row[15]) if row[15] else 50.0,
                    "efgd": float(row[16]) if row[16] else 50.0,
                    "tor": float(row[17]) if row[17] else 18.5,
                    "tord": float(row[18]) if row[18] else 18.5,
                    "orb": float(row[19]) if row[19] else 28.0,
                    "drb": float(row[20]) if row[20] else 72.0,
                    "ftr": float(row[21]) if row[21] else 33.0,
                    "ftrd": float(row[22]) if row[22] else 33.0,
                    "two_pt_pct": float(row[23]) if row[23] else 50.0,
                    "two_pt_pct_d": float(row[24]) if row[24] else 50.0,
                    "three_pt_pct": float(row[25]) if row[25] else 35.0,
                    "three_pt_pct_d": float(row[26]) if row[26] else 35.0,
                    "three_pt_rate": float(row[27]) if row[27] else 35.0,
                    "three_pt_rate_d": float(row[28]) if row[28] else 35.0,
                    "tempo": float(row[44]) if row[44] else 67.6,  # LAST FIELD
                    "wab": 0.0,  # WAB not consistently positioned
                    "rank": int(row[0]) if row[0] else 200,
                    "season": season,
                })
            except (ValueError, IndexError, TypeError) as e:
                continue
        return teams
    
    elif isinstance(sample, dict):
        # Already array-of-objects
        teams = []
        for row in data:
            teams.append({
                "team": row.get("team", ""),
                "conf": row.get("conf", ""),
                "games": row.get("g", 0),
                "wins": row.get("wins", 0),
                "losses": row.get("losses", 0),
                "adj_o": row.get("adjoe", 100.0),
                "adj_d": row.get("adjde", 100.0),
                "barthag": row.get("barthag", 0.5),
                "efg": row.get("efg_o", 50.0),
                "efgd": row.get("efg_d", 50.0),
                "tor": row.get("tor", 18.5),
                "tord": row.get("tord", 18.5),
                "orb": row.get("orb", 28.0),
                "drb": row.get("drb", 72.0),
                "ftr": row.get("ftr", 33.0),
                "ftrd": row.get("ftrd", 33.0),
                "two_pt_pct": row.get("2p_o", 50.0),
                "two_pt_pct_d": row.get("2p_d", 50.0),
                "three_pt_pct": row.get("3p_o", 35.0),
                "three_pt_pct_d": row.get("3p_d", 35.0),
                "three_pt_rate": row.get("3pr", 35.0),
                "three_pt_rate_d": row.get("3prd", 35.0),
                "tempo": row.get("adj_t", 67.6),
                "wab": row.get("wab", 0.0),
                "rank": row.get("rk", 200),
                "season": season,
            })
        return teams
    
    return []


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    if not name:
        return ""
    name = name.lower().strip()
    # Common substitutions
    name = name.replace("state", "st")
    name = name.replace("university", "")
    name = name.replace("college", "")
    name = name.replace("'", "")
    name = name.replace(".", "")
    name = name.replace("-", " ")
    return " ".join(name.split())  # Normalize whitespace


def save_ratings_csv(ratings: List[Dict], output_path: Path):
    """Save ratings to CSV."""
    if not ratings:
        print("No ratings to save")
        return
    
    fieldnames = list(ratings[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ratings)
    
    print(f"Saved {len(ratings)} team ratings to {output_path}")


def save_ratings_json(ratings: List[Dict], output_path: Path):
    """Save ratings to JSON for easy lookup."""
    # Create lookup by normalized team name
    lookup = {}
    for r in ratings:
        key = normalize_team_name(r["team"])
        season = r["season"]
        if key not in lookup:
            lookup[key] = {}
        lookup[key][season] = r
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(lookup, f, indent=2)
    
    print(f"Saved ratings lookup to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Barttorvik historical ratings")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2024, 2025],
                       help="Seasons to fetch (year is season END, e.g., 2024 = 2023-24)")
    parser.add_argument("--output", type=Path, default=None, help="Output directory")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Barttorvik Historical Ratings Fetcher")
    print("=" * 60)
    
    output_dir = args.output or Path(__file__).parent.parent / "training_data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_ratings = []
    
    for season in args.seasons:
        ratings = fetch_barttorvik_season(season)
        print(f"    Found {len(ratings)} teams")
        all_ratings.extend(ratings)
        time.sleep(1)  # Be nice to their server
    
    print(f"\nTotal: {len(all_ratings)} team-season ratings")
    
    # Save CSV
    csv_path = output_dir / "barttorvik_ratings.csv"
    save_ratings_csv(all_ratings, csv_path)
    
    # Save JSON lookup
    json_path = output_dir / "barttorvik_lookup.json"
    save_ratings_json(all_ratings, json_path)
    
    # Show sample
    print("\nSample ratings:")
    for r in all_ratings[:5]:
        print(f"  {r['season']}: {r['team']}: AdjO={r['adj_o']:.1f}, AdjD={r['adj_d']:.1f}, "
              f"Tempo={r['tempo']:.1f}, Barthag={r['barthag']:.3f}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
