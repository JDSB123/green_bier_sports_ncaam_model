#!/usr/bin/env python3
"""
Prospective Closing Line Capture

Set up to automatically capture closing lines 60-90 minutes before game tip-off.
This builds a closing line dataset going forward (can't backfill 2023-2025).

Scheduled to run via Windows Task Scheduler or similar.

Usage (manual):
    python capture_closing_lines.py --run-once

Usage (scheduled):
    Set up a Windows Task Scheduler job to run this script at regular intervals
    (e.g., every 15 minutes during betting hours)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))


@dataclass
class ClosingLine:
    """A closing line captured near game tip-off."""
    game_id: str
    commence_time: str
    capture_time: str
    home_team: str
    away_team: str
    fg_spread_closing: float | None = None
    fg_spread_price_closing: float | None = None
    fg_total_closing: float | None = None
    fg_total_price_closing: float | None = None
    h1_spread_closing: float | None = None
    h1_spread_price_closing: float | None = None
    h1_total_closing: float | None = None
    h1_total_price_closing: float | None = None
    source: str = "the_odds_api"


def _read_secret_file(path: str) -> str | None:
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
        return value if value else None
    except Exception:
        return None


def _get_odds_api_key() -> str | None:
    """Best-effort Odds API key lookup (env, docker secret, local secrets file)."""
    env_key = os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
    if env_key:
        return env_key.strip()

    file_path = os.getenv("THE_ODDS_API_KEY_FILE") or "/run/secrets/odds_api_key"
    file_key = _read_secret_file(file_path)
    if file_key:
        return file_key

    local_key = _read_secret_file(str(ROOT_DIR / "secrets" / "odds_api_key.txt"))
    if local_key:
        return local_key

    return None


def fetch_closing_lines() -> dict[str, ClosingLine]:
    """
    Fetch latest odds 60-90 minutes before tip-off.

    Returns dict: {game_id: ClosingLine}
    """
    try:
        import requests
    except ImportError:
        print("[ERROR] requests library required: pip install requests")
        return {}

    api_key = _get_odds_api_key()
    if not api_key:
        print(
            "[WARN] Odds API key not found; skipping capture. "
            "Set THE_ODDS_API_KEY/ODDS_API_KEY or provide /run/secrets/odds_api_key (Compose)."
        )
        return {}

    try:
        # Fetch upcoming games
        url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/events"
        params = {"apiKey": api_key}

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()

        events = resp.json()
        if not events:
            print("[INFO] No upcoming games found")
            return {}

        closing_lines = {}
        now = datetime.now(tz=__import__('datetime').timezone.utc)

        for event in events:
            # Check if game is within 60-90 minutes
            commence_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
            time_until_tip = (commence_time - now).total_seconds() / 60

            # Only capture if within 60-90 minutes window
            if not (60 <= time_until_tip <= 90):
                continue

            game_id = event["id"]
            home_team = event["home_team"]
            away_team = event["away_team"]

            closing_line = ClosingLine(
                game_id=game_id,
                commence_time=event["commence_time"],
                capture_time=now.isoformat(),
                home_team=home_team,
                away_team=away_team,
            )

            # Fetch odds for this game
            try:
                odds_url = f"https://api.the-odds-api.com/v4/sports/basketball_ncaab/events/{game_id}/odds"
                odds_params = {
                    "apiKey": api_key,
                    "regions": "us",
                    "markets": "spreads,totals,h2h",
                    "oddsFormat": "american",
                }

                odds_resp = requests.get(odds_url, params=odds_params, timeout=10)
                odds_resp.raise_for_status()

                odds_data = odds_resp.json()

                if "bookmakers" in odds_data and odds_data["bookmakers"]:
                    # Get latest bookmaker (usually DraftKings or FanDuel)
                    bookmaker = odds_data["bookmakers"][0]

                    for market in bookmaker.get("markets", []):
                        if market["key"] == "spreads":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == home_team:
                                    closing_line.fg_spread_closing = outcome["point"]
                                    closing_line.fg_spread_price_closing = outcome["price"]
                                    break

                        elif market["key"] == "totals":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == "Over":
                                    closing_line.fg_total_closing = outcome["point"]
                                    closing_line.fg_total_price_closing = outcome["price"]
                                    break

                closing_lines[game_id] = closing_line

            except Exception as e:
                print(f"[WARN] Error fetching odds for {game_id}: {e}")
                continue

        return closing_lines

    except Exception as e:
        print(f"[ERROR] Failed to fetch closing lines: {e}")
        return {}


def append_to_closing_lines_archive(closing_lines: dict[str, ClosingLine]) -> None:
    """Append captured closing lines to archive CSV."""
    if not closing_lines:
        print("[INFO] No closing lines captured")
        return

    archive_file = ROOT_DIR / "testing" / "data" / "closing_lines_archive.csv"
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert to DataFrame
    records = [asdict(cl) for cl in closing_lines.values()]
    df_new = pd.DataFrame(records)

    # Append to archive
    if archive_file.exists():
        df_archive = pd.read_csv(archive_file)
        df_combined = pd.concat([df_archive, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=["game_id", "capture_time"], keep="last")
        df_combined.to_csv(archive_file, index=False)
        print(f"[OK] Appended {len(df_new)} closing lines to {archive_file}")
    else:
        df_new.to_csv(archive_file, index=False)
        print(f"[OK] Created archive with {len(df_new)} closing lines at {archive_file}")


def log_capture_event(closing_lines: dict[str, ClosingLine]) -> None:
    """Log capture event to timestamped JSON file."""
    log_dir = ROOT_DIR / "testing" / "logs" / "closing_line_captures"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"capture_{timestamp}.json"

    log_data = {
        "capture_time": datetime.now().isoformat(),
        "lines_captured": len(closing_lines),
        "closing_lines": [asdict(cl) for cl in closing_lines.values()],
    }

    with log_file.open("w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    print(f"[OK] Logged to {log_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Capture closing lines 60-90 min before tip-off"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run once and exit (for manual testing)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (checks every 5 minutes)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Check interval in minutes (for daemon mode)"
    )

    args = parser.parse_args()

    print("\n" + "="*70)
    print("CLOSING LINE CAPTURE")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    if args.daemon:
        print(f"[INFO] Running in daemon mode, checking every {args.interval} minutes")
        import time

        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking for games...")
            closing_lines = fetch_closing_lines()

            if closing_lines:
                append_to_closing_lines_archive(closing_lines)
                log_capture_event(closing_lines)

            print(f"[INFO] Next check in {args.interval} minutes...")
            time.sleep(args.interval * 60)

    else:
        # Run once
        print("[INFO] Running once...")
        closing_lines = fetch_closing_lines()

        if closing_lines:
            append_to_closing_lines_archive(closing_lines)
            log_capture_event(closing_lines)
        else:
            print("[INFO] No closing lines captured")

        print("\n[OK] Done")


if __name__ == "__main__":
    main()
