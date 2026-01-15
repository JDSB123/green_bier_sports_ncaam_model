#!/usr/bin/env python3
"""Fetch historical NCAAM data from free public APIs for backtesting.

Data Sources:
- ESPN API: Game results with scores (free, no auth)
- Barttorvik: Team efficiency ratings by season

This script downloads historical data needed to properly validate
the prediction model against real outcomes.

Canonical window: 2023-24 season onward (season 2024+).

Team Canonicalization:
- All team names are canonicalized at ingestion using team_utils.resolve_team_name()
- If >10% of a day's games have unresolved teams, the script aborts
- Unresolved teams are logged and skipped (< 10% threshold)
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import Any

try:
    import requests
except ImportError:
    print("[ERROR] requests library required: pip install requests")
    sys.exit(1)

# Import team canonicalization from single source of truth
# team_utils.py is in the same directory (testing/scripts/)
try:
    from team_utils import resolve_team_name
except ImportError:
    print("[ERROR] team_utils module required - must be in testing/scripts/")
    sys.exit(1)

from testing.azure_io import upload_text, write_json
from testing.data_window import CANONICAL_START_SEASON, enforce_min_season

SCORES_FG_PREFIX = "scores/fg"
RATINGS_PREFIX = "ratings/barttorvik"

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
    """Extract relevant fields from ESPN event.
    
    Team names are canonicalized at parse time using the central team resolver.
    Returns None if either team cannot be resolved (game is skipped).
    """
    try:
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])

        if len(competitors) != 2:
            return None

        home_team_raw = away_team_raw = None
        home_score = away_score = 0

        for c in competitors:
            team_data = c.get("team", {})
            team_name = team_data.get("displayName", "")
            team_abbr = team_data.get("abbreviation", "")
            score = int(c.get("score", 0) or 0)

            if c.get("homeAway") == "home":
                home_team_raw = team_name
                home_abbr = team_abbr
                home_score = score
            else:
                away_team_raw = team_name
                away_abbr = team_abbr
                away_score = score

        if not home_team_raw or not away_team_raw:
            return None

        # Only include completed games
        status = event.get("status", {}).get("type", {}).get("name", "")
        if status != "STATUS_FINAL":
            return None

        # Canonicalize team names using central resolver
        home_team = resolve_team_name(home_team_raw)
        away_team = resolve_team_name(away_team_raw)
        
        # Track resolution failures - return None with raw names preserved for logging
        unresolved = []
        if home_team == home_team_raw:
            # Check if it's actually a canonical name (resolved to itself)
            canonical_check = resolve_team_name(home_team_raw.lower())
            if canonical_check == home_team_raw.lower():
                unresolved.append(("home", home_team_raw))
        if away_team == away_team_raw:
            canonical_check = resolve_team_name(away_team_raw.lower())
            if canonical_check == away_team_raw.lower():
                unresolved.append(("away", away_team_raw))
        
        if unresolved:
            # Return dict with _unresolved marker for threshold tracking
            return {
                "_unresolved": unresolved,
                "game_id": event.get("id"),
                "date": event.get("date", "")[:10],
                "home_team_raw": home_team_raw,
                "away_team_raw": away_team_raw,
            }

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


# Canonicalization threshold - fail if more than 10% of games have unresolved teams
UNRESOLVED_THRESHOLD = 0.10


def fetch_season_games(season: int, verbose: bool = True) -> list[dict]:
    """Fetch all games for a season (e.g., 2024 = 2023-24 season).
    
    Raises:
        RuntimeError: If >10% of games on any day have unresolved team names
    """
    games = []
    all_unresolved = []  # Track all unresolved for summary

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

        day_games = []
        day_unresolved = []
        
        for event in events:
            game = parse_espn_game(event)
            if game:
                if "_unresolved" in game:
                    # This game has unresolved team(s)
                    day_unresolved.append(game)
                    all_unresolved.append(game)
                else:
                    day_games.append(game)
        
        # Check threshold for this day
        total_day = len(day_games) + len(day_unresolved)
        if total_day > 0 and len(day_unresolved) > 0:
            failure_rate = len(day_unresolved) / total_day
            
            if failure_rate > UNRESOLVED_THRESHOLD:
                # More than 10% failed - abort
                msg = (f"[ERROR] {current.strftime('%Y-%m-%d')}: "
                       f"{len(day_unresolved)}/{total_day} games ({failure_rate:.1%}) have unresolved teams "
                       f"(threshold: {UNRESOLVED_THRESHOLD:.0%})")
                print(msg)
                for g in day_unresolved:
                    for side, name in g["_unresolved"]:
                        print(f"  - UNRESOLVED {side}: '{name}'")
                raise RuntimeError(msg)
            else:
                # Under threshold - log warning and skip
                if verbose:
                    print(f"  [WARN] {current.strftime('%Y-%m-%d')}: Skipping {len(day_unresolved)} games with unresolved teams")
                    for g in day_unresolved:
                        for side, name in g["_unresolved"]:
                            print(f"    - UNRESOLVED {side}: '{name}'")
        
        games.extend(day_games)

        day_count += 1
        if verbose and day_count % 30 == 0:
            print(f"  Progress: {day_count}/{total_days} days, {len(games)} games found")

        current += timedelta(days=1)
        time.sleep(0.1)  # Be nice to ESPN

    if verbose:
        print(f"  [DONE] {len(games)} completed games for {season-1}-{str(season)[-2:]} season")
        if all_unresolved:
            print(f"  [WARN] Skipped {len(all_unresolved)} games total due to unresolved teams")

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


def build_tags(
    dataset: str,
    season: int | None = None,
    source: str | None = None,
    scope: str | None = None,
) -> dict:
    tags = {"dataset": dataset}
    if season is not None:
        tags["season"] = str(season)
    if source:
        tags["source"] = source
    if scope:
        tags["scope"] = scope
    return tags


def save_games_csv(games: list[dict], blob_path: str, tags: dict | None = None) -> None:
    """Save games to CSV format."""
    headers = [
        "game_id", "date", "home_team", "home_abbr", "away_team", "away_abbr",
        "home_score", "away_score", "total", "spread_result", "venue", "neutral"
    ]

    lines = [",".join(headers)]
    for g in games:
        row = [str(g.get(h, "")).replace(",", ";") for h in headers]
        lines.append(",".join(row))
    upload_text(blob_path, "\n".join(lines) + "\n", content_type="text/csv", tags=tags)
    print(f"[INFO] Saved {len(games)} games to {blob_path}")


def save_games_json(games: list[dict], blob_path: str, tags: dict | None = None) -> None:
    """Save games to JSON format."""
    write_json(blob_path, games, indent=2, tags=tags)
    print(f"[INFO] Saved {len(games)} games to {blob_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch historical NCAAM game data for backtesting"
    )
    parser.add_argument(
        "--seasons",
        type=str,
        default=str(CANONICAL_START_SEASON),
        help="Seasons to fetch (e.g., '2024' or '2024-2026')"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format"
    )
    parser.add_argument(
        "--scores-prefix",
        type=str,
        default=SCORES_FG_PREFIX,
        help="Azure blob prefix for full-game scores"
    )
    parser.add_argument(
        "--ratings-prefix",
        type=str,
        default=RATINGS_PREFIX,
        help="Azure blob prefix for Barttorvik ratings"
    )

    args = parser.parse_args(argv)

    # Parse seasons
    if "-" in args.seasons:
        start, end = args.seasons.split("-")
        seasons = list(range(int(start), int(end) + 1))
    else:
        seasons = [int(args.seasons)]
    seasons = enforce_min_season(seasons)

    print("=" * 72)
    print(" Historical NCAAM Data Fetcher")
    print("=" * 72)
    print(f" Seasons: {seasons}")
    print(f" Scores output: {args.scores_prefix}")
    print(f" Ratings output: {args.ratings_prefix}")
    print("=" * 72)
    print()

    all_games = []

    for season in seasons:
        games = fetch_season_games(season)
        all_games.extend(games)

        # Save per-season files
        score_tags = build_tags("scores_fg", season=season, source="espn", scope="season")
        if args.format in ("csv", "both"):
            save_games_csv(
                games,
                f"{args.scores_prefix}/games_{season}.csv",
                tags=score_tags,
            )
        if args.format in ("json", "both"):
            save_games_json(
                games,
                f"{args.scores_prefix}/games_{season}.json",
                tags=score_tags,
            )

        # Fetch Barttorvik ratings
        ratings = fetch_barttorvik_ratings(season)
        if ratings:
            ratings_path = f"{args.ratings_prefix}/barttorvik_{season}.json"
            ratings_tags = build_tags("barttorvik_ratings", season=season, source="barttorvik", scope="season")
            write_json(ratings_path, ratings, indent=2, tags=ratings_tags)
            print(f"[INFO] Saved Barttorvik ratings to {ratings_path}")

        print()

    # Save combined file if multiple seasons
    if len(seasons) > 1:
        combined_tags = build_tags("scores_fg", source="espn", scope="all")
        if args.format in ("csv", "both"):
            save_games_csv(
                all_games,
                f"{args.scores_prefix}/games_all.csv",
                tags=combined_tags,
            )
        if args.format in ("json", "both"):
            save_games_json(
                all_games,
                f"{args.scores_prefix}/games_all.json",
                tags=combined_tags,
            )

    print("=" * 72)
    print(f" SUCCESS: Downloaded {len(all_games)} games across {len(seasons)} season(s)")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
