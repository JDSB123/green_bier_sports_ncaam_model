#!/usr/bin/env python3
"""Fetch historical NCAAM data from free public APIs for backtesting.

Data Sources:
- ESPN API: Game results with scores (free, no auth)
- Barttorvik: Team efficiency ratings by season

This script downloads historical data needed to properly validate
the prediction model against real outcomes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("[ERROR] requests library required: pip install requests")
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_ROOT = Path(
    os.environ.get("HISTORICAL_DATA_ROOT", ROOT_DIR / "ncaam_historical_data_local")
).resolve()
SCORES_FG_DIR = Path(
    os.environ.get("HISTORICAL_SCORES_FG_DIR", HISTORICAL_ROOT / "scores" / "fg")
).resolve()
RATINGS_DIR = Path(
    os.environ.get("HISTORICAL_RATINGS_DIR", HISTORICAL_ROOT / "ratings" / "barttorvik")
).resolve()

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
BARTTORVIK_BASE = "https://barttorvik.com"


def fetch_espn_scoreboard(date: str) -> list[dict]:
    """Fetch all games for a specific date (YYYYMMDD format)."""
    url = f"{ESPN_BASE}/scoreboard?dates={date}&limit=200"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("events", [])
    except Exception as e:
        print(f"  [WARN] Failed to fetch {date}: {e}")
        return []


def parse_espn_game(event: dict) -> dict | None:
    """Extract relevant fields from ESPN event."""
    try:
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])

        if len(competitors) != 2:
            return None

        home_team = away_team = None
        home_score = away_score = 0

        for c in competitors:
            team_data = c.get("team", {})
            team_name = team_data.get("displayName", "")
            team_abbr = team_data.get("abbreviation", "")
            score = int(c.get("score", 0) or 0)

            if c.get("homeAway") == "home":
                home_team = team_name
                home_abbr = team_abbr
                home_score = score
            else:
                away_team = team_name
                away_abbr = team_abbr
                away_score = score

        if not home_team or not away_team:
            return None

        # Only include completed games
        status = event.get("status", {}).get("type", {}).get("name", "")
        if status != "STATUS_FINAL":
            return None

        return {
            "game_id": event.get("id"),
            "date": event.get("date", "")[:10],
            "home_team": home_team,
            "home_abbr": home_abbr,
            "away_team": away_team,
            "away_abbr": away_abbr,
            "home_score": home_score,
            "away_score": away_score,
            "total": home_score + away_score,
            "spread_result": home_score - away_score,  # positive = home won by X
            "venue": comp.get("venue", {}).get("fullName", ""),
            "neutral": comp.get("neutralSite", False),
        }
    except Exception:
        return None


def fetch_season_games(season: int, verbose: bool = True) -> list[dict]:
    """Fetch all games for a season (e.g., 2024 = 2023-24 season)."""
    games = []

    # NCAA season runs Nov through early April
    start_date = datetime(season - 1, 11, 1)
    end_date = datetime(season, 4, 15)

    current = start_date
    total_days = (end_date - start_date).days

    if verbose:
        print(f"[INFO] Fetching {season-1}-{str(season)[-2:]} season ({total_days} days)...")

    day_count = 0
    while current <= end_date:
        date_str = current.strftime("%Y%m%d")
        events = fetch_espn_scoreboard(date_str)

        for event in events:
            game = parse_espn_game(event)
            if game:
                games.append(game)

        day_count += 1
        if verbose and day_count % 30 == 0:
            print(f"  Progress: {day_count}/{total_days} days, {len(games)} games found")

        current += timedelta(days=1)
        time.sleep(0.1)  # Be nice to ESPN

    if verbose:
        print(f"  [DONE] {len(games)} completed games for {season-1}-{str(season)[-2:]} season")

    return games


def fetch_barttorvik_ratings(season: int) -> dict | None:
    """Fetch team efficiency ratings for a season."""
    url = f"{BARTTORVIK_BASE}/{season}_team_results.json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[WARN] Failed to fetch Barttorvik {season}: {e}")
        return None


def save_games_csv(games: list[dict], filepath: Path) -> None:
    """Save games to CSV format."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "game_id", "date", "home_team", "home_abbr", "away_team", "away_abbr",
        "home_score", "away_score", "total", "spread_result", "venue", "neutral"
    ]

    with filepath.open("w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for g in games:
            row = [str(g.get(h, "")).replace(",", ";") for h in headers]
            f.write(",".join(row) + "\n")

    print(f"[INFO] Saved {len(games)} games to {filepath}")


def save_games_json(games: list[dict], filepath: Path) -> None:
    """Save games to JSON format."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(games, f, indent=2)
    print(f"[INFO] Saved {len(games)} games to {filepath}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch historical NCAAM game data for backtesting"
    )
    parser.add_argument(
        "--seasons",
        type=str,
        default="2024",
        help="Seasons to fetch (e.g., '2024' or '2020-2024')"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(SCORES_FG_DIR),
        help="Output directory for full-game scores"
    )
    parser.add_argument(
        "--ratings-dir",
        type=str,
        default=str(RATINGS_DIR),
        help="Output directory for Barttorvik ratings"
    )

    args = parser.parse_args(argv)

    # Parse seasons
    if "-" in args.seasons:
        start, end = args.seasons.split("-")
        seasons = list(range(int(start), int(end) + 1))
    else:
        seasons = [int(args.seasons)]

    output_dir = Path(args.output_dir)
    ratings_dir = Path(args.ratings_dir)

    print("=" * 72)
    print(" Historical NCAAM Data Fetcher")
    print("=" * 72)
    print(f" Seasons: {seasons}")
    print(f" Scores output: {output_dir}")
    print(f" Ratings output: {ratings_dir}")
    print("=" * 72)
    print()

    all_games = []

    for season in seasons:
        games = fetch_season_games(season)
        all_games.extend(games)

        # Save per-season files
        if args.format in ("csv", "both"):
            save_games_csv(games, output_dir / f"games_{season}.csv")
        if args.format in ("json", "both"):
            save_games_json(games, output_dir / f"games_{season}.json")

        # Fetch Barttorvik ratings
        ratings = fetch_barttorvik_ratings(season)
        if ratings:
            ratings_dir.mkdir(parents=True, exist_ok=True)
            ratings_path = ratings_dir / f"barttorvik_{season}.json"
            with ratings_path.open("w", encoding="utf-8") as f:
                json.dump(ratings, f, indent=2)
            print(f"[INFO] Saved Barttorvik ratings to {ratings_path}")

        print()

    # Save combined file if multiple seasons
    if len(seasons) > 1:
        if args.format in ("csv", "both"):
            save_games_csv(all_games, output_dir / "games_all.csv")
        if args.format in ("json", "both"):
            save_games_json(all_games, output_dir / "games_all.json")

    print("=" * 72)
    print(f" SUCCESS: Downloaded {len(all_games)} games across {len(seasons)} season(s)")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
