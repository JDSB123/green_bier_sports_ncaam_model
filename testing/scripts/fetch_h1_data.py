#!/usr/bin/env python3
"""Fetch historical 1H (First Half) scores from ESPN for backtesting.

ESPN's boxscore/summary API includes linescore with period scores.
This script fetches 1H data for all games we have in our historical data.

Data Flow:
1. Load existing game IDs from games_all.csv
2. Fetch boxscore for each game to get 1H scores
3. Save 1H data for backtest validation
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from typing import Any

try:
    import requests
except ImportError:
    print("[ERROR] requests library required: pip install requests")
    sys.exit(1)

# Import team canonicalization from single source of truth
try:
    from team_utils import resolve_team_name
except ImportError:
    print("[ERROR] team_utils module required - must be in testing/scripts/")
    sys.exit(1)

# Canonicalization threshold - fail if more than 10% of games have unresolved teams
UNRESOLVED_THRESHOLD = 0.10

from testing.azure_io import read_csv, upload_text, write_json, blob_exists

SCORES_FG_BLOB = "scores/fg/games_all.csv"
SCORES_H1_BLOB = "scores/h1/h1_games_all.csv"

ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"


def fetch_game_summary(game_id: str) -> dict | None:
    """Fetch game summary with linescore (period scores)."""
    url = f"{ESPN_SUMMARY_URL}?event={game_id}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [WARN] Failed to fetch game {game_id}: {e}")
        return None


def parse_h1_scores(summary: dict, game_id: str) -> dict | None:
    """Extract 1H scores from ESPN summary."""
    try:
        boxscore = summary.get("boxscore", {})
        teams = boxscore.get("teams", [])

        if len(teams) != 2:
            return None

        home_h1 = away_h1 = None
        home_fg = away_fg = None
        home_team = away_team = ""

        for team_data in teams:
            team_info = team_data.get("team", {})
            team_name = team_info.get("displayName", "")
            home_away = team_data.get("homeAway", "")

            # Get statistics with linescore
            stats = team_data.get("statistics", [])

            # Find linescore in stats
            linescore = None
            for stat in stats:
                if stat.get("name") == "linescore":
                    linescore = stat.get("displayValue", "")
                    break

            # If not in statistics, check directly in team_data
            if not linescore:
                linescores = team_data.get("linescores", [])
                if linescores:
                    # Sum first half periods (period 1 for 1H)
                    h1_score = 0
                    for ls in linescores:
                        period = ls.get("period", 0)
                        if period == 1:  # First half
                            h1_score = int(ls.get("displayValue", 0) or 0)
                            break
                    if home_away == "home":
                        home_h1 = h1_score
                        home_team = team_name
                    else:
                        away_h1 = h1_score
                        away_team = team_name
                    continue

            # Parse linescore string (e.g., "35-42" for 1H-2H)
            if linescore and "-" in linescore:
                parts = linescore.split("-")
                if len(parts) >= 1:
                    h1_score = int(parts[0])
                    if home_away == "home":
                        home_h1 = h1_score
                        home_team = team_name
                    else:
                        away_h1 = h1_score
                        away_team = team_name

        # Try header->competitions->competitors->linescores if boxscore didn't work
        if home_h1 is None or away_h1 is None:
            header = summary.get("header", {})
            competitions = header.get("competitions", [])
            if competitions:
                competitors = competitions[0].get("competitors", [])
                for comp in competitors:
                    team_info = comp.get("team", {})
                    team_name = team_info.get("displayName", "")
                    home_away = comp.get("homeAway", "")
                    linescores = comp.get("linescores", [])

                    if linescores:
                        # Get first period score
                        h1_score = int(linescores[0].get("displayValue", 0) or 0)
                        if home_away == "home":
                            home_h1 = h1_score
                            home_team = team_name
                            home_fg = int(comp.get("score", 0) or 0)
                        else:
                            away_h1 = h1_score
                            away_team = team_name
                            away_fg = int(comp.get("score", 0) or 0)

        if home_h1 is None or away_h1 is None:
            return None

        # Canonicalize team names using central resolver
        home_team_canonical = resolve_team_name(home_team) if home_team else home_team
        away_team_canonical = resolve_team_name(away_team) if away_team else away_team
        
        # Check for unresolved teams
        unresolved = []
        if home_team and home_team_canonical == home_team:
            # Could be canonical already - check case-insensitive
            check = resolve_team_name(home_team.lower())
            if check == home_team.lower():
                unresolved.append(("home", home_team))
        if away_team and away_team_canonical == away_team:
            check = resolve_team_name(away_team.lower())
            if check == away_team.lower():
                unresolved.append(("away", away_team))
        
        if unresolved:
            return {
                "_unresolved": unresolved,
                "game_id": game_id,
                "home_team_raw": home_team,
                "away_team_raw": away_team,
            }

        return {
            "game_id": game_id,
            "home_team": home_team_canonical,
            "away_team": away_team_canonical,
            "home_h1": home_h1,
            "away_h1": away_h1,
            "h1_total": home_h1 + away_h1,
            "home_fg": home_fg,
            "away_fg": away_fg,
            "fg_total": (home_fg + away_fg) if home_fg and away_fg else None,
        }
    except Exception as e:
        print(f"  [ERROR] Parsing game {game_id}: {e}")
        return None


def load_game_ids(blob_path: str) -> list[dict]:
    """Load game IDs and basic info from CSV."""
    df = read_csv(blob_path)
    games = []
    for _, row in df.iterrows():
        games.append({
            "game_id": str(row.get("game_id", "")),
            "date": str(row.get("date", "")),
            "home_team": row.get("home_team", ""),
            "away_team": row.get("away_team", ""),
            "home_score": int(row.get("home_score", 0) or 0),
            "away_score": int(row.get("away_score", 0) or 0),
        })
    return games


def build_tags(
    dataset: str,
    source: str | None = None,
    scope: str | None = None,
    season: int | None = None,
) -> dict:
    tags = {"dataset": dataset}
    if source:
        tags["source"] = source
    if scope:
        tags["scope"] = scope
    if season is not None:
        tags["season"] = str(season)
    return tags


def save_h1_data(h1_games: list[dict], blob_path: str, tags: dict | None = None) -> None:
    """Save 1H data to CSV in Azure Blob Storage."""

    headers = [
        "game_id", "date", "home_team", "away_team",
        "home_h1", "away_h1", "h1_total",
        "home_fg", "away_fg", "fg_total"
    ]

    lines = [",".join(headers)]
    for g in h1_games:
        lines.append(",".join([str(g.get(h, "")).replace(",", ";") for h in headers]))
    upload_text(blob_path, "\n".join(lines) + "\n", content_type="text/csv", tags=tags)
    print(f"[INFO] Saved {len(h1_games)} games with 1H data to {blob_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch historical 1H (First Half) scores from ESPN."
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input games CSV (default: scores/fg/games_all.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output H1 CSV (default: scores/h1/h1_games_all.csv)"
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Optional JSON output path (default: output CSV name with .json)"
    )
    args = parser.parse_args()

    print("=" * 72)
    print(" 1H Historical Data Fetcher (ESPN)")
    print("=" * 72)

    # Load existing game IDs
    games_blob = args.input if args.input else SCORES_FG_BLOB
    if not blob_exists(games_blob):
        print(f"[ERROR] Games file not found: {games_blob}")
        print("        Run fetch_historical_data.py first!")
        return 1

    games = load_game_ids(games_blob)
    print(f"[INFO] Loaded {len(games)} games from {games_blob}")

    # Check for existing progress
    output_blob = args.output if args.output else SCORES_H1_BLOB
    tags = build_tags("scores_h1", source="espn", scope="all")
    existing_ids = set()
    if blob_exists(output_blob):
        existing_df = read_csv(output_blob)
        if "game_id" in existing_df.columns:
            existing_ids = set(existing_df["game_id"].astype(str).tolist())
        print(f"[INFO] Found {len(existing_ids)} existing 1H records")

    # Fetch 1H data for each game
    h1_games = []
    failed_count = 0

    # If resuming, load existing data
    if existing_ids:
        existing_df = read_csv(output_blob)
        h1_games.extend(existing_df.to_dict(orient="records"))

    games_to_fetch = [g for g in games if g["game_id"] not in existing_ids]
    print(f"[INFO] Need to fetch {len(games_to_fetch)} new games")
    print()

    unresolved_games = []  # Track unresolved for summary
    
    for i, game in enumerate(games_to_fetch):
        game_id = game["game_id"]

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(games_to_fetch)} ({len(h1_games)} with 1H data)")
            # Save progress
            save_h1_data(h1_games, output_blob, tags=tags)

        summary = fetch_game_summary(game_id)
        if not summary:
            failed_count += 1
            continue

        h1_data = parse_h1_scores(summary, game_id)
        if h1_data:
            # Check for unresolved teams
            if "_unresolved" in h1_data:
                unresolved_games.append(h1_data)
                for side, name in h1_data["_unresolved"]:
                    print(f"  [WARN] UNRESOLVED {side}: '{name}' (game {game_id})")
                continue
            
            h1_data["date"] = game["date"]
            h1_games.append(h1_data)
        else:
            failed_count += 1

        # Throttle requests; lowered for faster bulk backfills while remaining polite.
        time.sleep(0.02)  # Was 0.15

    # Final save
    save_h1_data(h1_games, output_blob, tags=tags)

    # Also save as JSON
    json_blob = args.output_json if args.output_json else output_blob.replace(".csv", ".json")
    write_json(json_blob, h1_games, indent=2, tags=tags)
    print(f"[INFO] Saved JSON to {json_blob}")

    # Check threshold for unresolved teams
    total_processed = len(h1_games) + len(unresolved_games)
    if total_processed > 0 and len(unresolved_games) > 0:
        failure_rate = len(unresolved_games) / total_processed
        print()
        print(f"[WARN] {len(unresolved_games)}/{total_processed} games ({failure_rate:.1%}) have unresolved teams")
        
        if failure_rate > UNRESOLVED_THRESHOLD:
            print(f"[ERROR] Unresolved rate exceeds {UNRESOLVED_THRESHOLD:.0%} threshold!")
            seen = set()
            for g in unresolved_games:
                for side, name in g["_unresolved"]:
                    if name not in seen:
                        print(f"  - UNRESOLVED {side}: '{name}'")
                        seen.add(name)
            return 1

    print()
    print("=" * 72)
    print(f" DONE: {len(h1_games)} games with 1H data")
    print(f" Failed: {failed_count} games (no 1H data available)")
    if unresolved_games:
        print(f" Skipped: {len(unresolved_games)} games (unresolved teams)")
    print("=" * 72)

    # Summary statistics
    if h1_games:
        h1_totals = [int(g.get("h1_total", 0) or 0) for g in h1_games if g.get("h1_total")]
        fg_totals = [int(g.get("fg_total", 0) or 0) for g in h1_games if g.get("fg_total")]

        if h1_totals:
            avg_h1 = sum(h1_totals) / len(h1_totals)
            print(f" Average 1H Total: {avg_h1:.1f}")
        if fg_totals:
            avg_fg = sum(fg_totals) / len(fg_totals)
            print(f" Average FG Total: {avg_fg:.1f}")
        if h1_totals and fg_totals:
            # Calculate ratio for games that have both
            ratios = []
            for g in h1_games:
                h1 = int(g.get("h1_total", 0) or 0)
                fg = int(g.get("fg_total", 0) or 0)
                if h1 > 0 and fg > 0:
                    ratios.append(h1 / fg)
            if ratios:
                avg_ratio = sum(ratios) / len(ratios)
                print(f" Average 1H/FG Ratio: {avg_ratio:.3f} (expected ~0.48)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
