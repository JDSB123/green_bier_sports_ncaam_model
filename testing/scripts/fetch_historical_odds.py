#!/usr/bin/env python3
"""
Fetch Historical Betting Lines from The Odds API

This script fetches historical NCAAB betting lines for backtesting.
Data available from late 2020.

API Documentation: https://the-odds-api.com/liveapi/guides/v4/

Usage:
    # Set API key first
    export ODDS_API_KEY=your_key_here

    # Fetch odds for a date range
    python testing/scripts/fetch_historical_odds.py --start 2024-01-01 --end 2024-03-31

Requirements:
    - The Odds API key (free tier: 500 requests/month)
    - Sign up at: https://the-odds-api.com/
"""
from __future__ import annotations

import argparse
import csv
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
DATA_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"


def get_api_key() -> str:
    """Get API key from environment or secrets file."""
    # Try environment first
    key = os.environ.get("ODDS_API_KEY") or os.environ.get("THE_ODDS_API_KEY")

    # Try secrets file (same pattern as production code)
    if not key:
        secrets_file = ROOT_DIR / "secrets" / "odds_api_key.txt"
        if secrets_file.exists():
            key = secrets_file.read_text().strip()

    # Try Docker secret location
    if not key:
        docker_secret = Path("/run/secrets/odds_api_key")
        if docker_secret.exists():
            key = docker_secret.read_text().strip()

    if not key:
        print("[ERROR] No Odds API key found")
        print("        Set ODDS_API_KEY env var or create secrets/odds_api_key.txt")
        sys.exit(1)

    return key


def fetch_with_retry(url: str, params: dict, max_retries: int = 3) -> requests.Response:
    """Fetch URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 2  # 2, 4, 8 seconds
                print(f"  [RETRY] Connection error, waiting {wait}s: {e}")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                wait = 60
                print(f"  [RATE LIMIT] Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


def fetch_historical_events(api_key: str, date: str) -> list[dict]:
    """
    Fetch historical events (games) for a specific date.

    Note: The Odds API historical endpoint requires knowing event IDs.
    We'll need to fetch events first, then get odds for each.
    """
    # The historical events endpoint
    url = f"{BASE_URL}/historical/sports/{SPORT_KEY}/events"

    params = {
        "apiKey": api_key,
        "date": f"{date}T12:00:00Z",  # Noon UTC
    }

    try:
        resp = fetch_with_retry(url, params)
        data = resp.json()

        # Check remaining quota
        remaining = resp.headers.get("x-requests-remaining", "?")
        print(f"  [API] Requests remaining: {remaining}")

        return data.get("data", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:
            print(f"  [WARN] No historical data for {date}")
            return []
        raise


def fetch_historical_odds(
    api_key: str,
    event_id: str,
    date: str,
    markets: str = "spreads,totals"
) -> dict | None:
    """
    Fetch historical odds for a specific event.

    Args:
        api_key: The Odds API key
        event_id: Event ID from events endpoint
        date: ISO8601 date string (e.g., "2024-01-15T18:00:00Z")
        markets: Comma-separated markets (spreads, totals, h2h)
    """
    url = f"{BASE_URL}/historical/sports/{SPORT_KEY}/events/{event_id}/odds"

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
        "date": date,
    }

    try:
        resp = fetch_with_retry(url, params)
        return resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (404, 422):
            return None
        raise
    except Exception:
        return None  # Skip event on persistent errors


def parse_odds_data(event: dict, odds_data: dict) -> dict | None:
    """Extract relevant fields from odds response."""
    try:
        data = odds_data.get("data", {})
        bookmakers = data.get("bookmakers", [])

        if not bookmakers:
            return None

        # Find Pinnacle (sharp) or DraftKings (liquid)
        target_books = ["pinnacle", "draftkings", "fanduel", "betmgm"]
        selected_book = None

        for book_name in target_books:
            for bm in bookmakers:
                if bm.get("key", "").lower() == book_name:
                    selected_book = bm
                    break
            if selected_book:
                break

        if not selected_book:
            selected_book = bookmakers[0]  # Fallback to first

        # Parse markets
        spread = None
        total = None

        for market in selected_book.get("markets", []):
            if market.get("key") == "spreads":
                outcomes = market.get("outcomes", [])
                for o in outcomes:
                    if o.get("name") == event.get("home_team"):
                        spread = o.get("point")
                        break

            if market.get("key") == "totals":
                outcomes = market.get("outcomes", [])
                for o in outcomes:
                    if o.get("name") == "Over":
                        total = o.get("point")
                        break

        return {
            "event_id": event.get("id"),
            "commence_time": event.get("commence_time"),
            "home_team": event.get("home_team"),
            "away_team": event.get("away_team"),
            "bookmaker": selected_book.get("key"),
            "spread": spread,
            "total": total,
            "timestamp": odds_data.get("timestamp"),
        }

    except Exception as e:
        print(f"  [WARN] Parse error: {e}")
        return None


def fetch_date_range(
    api_key: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    save_interval: int = 7,  # Save every 7 days
) -> list[dict]:
    """Fetch odds for all games in a date range with incremental saving."""
    all_odds = []
    days_since_save = 0

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    current = start
    failed_dates = []

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n[INFO] Fetching {date_str}...")

        try:
            events = fetch_historical_events(api_key, date_str)
            print(f"  Found {len(events)} events")

            for event in events:
                event_id = event.get("id")
                commence = event.get("commence_time", "")

                # Fetch odds at game time
                odds = fetch_historical_odds(api_key, event_id, commence)

                if odds:
                    parsed = parse_odds_data(event, odds)
                    if parsed:
                        all_odds.append(parsed)
                        print(f"    {parsed['away_team']} @ {parsed['home_team']}: "
                              f"spread={parsed['spread']}, total={parsed['total']}")

                time.sleep(0.3)  # Rate limiting

            days_since_save += 1

            # Save incrementally
            if days_since_save >= save_interval and all_odds:
                temp_path = output_dir / f"odds_partial_{start_date.replace('-', '')}_{date_str.replace('-', '')}.csv"
                save_odds_csv(all_odds, temp_path)
                print(f"  [CHECKPOINT] Saved {len(all_odds)} records")
                days_since_save = 0

        except Exception as e:
            print(f"  [ERROR] Failed to fetch {date_str}: {e}")
            failed_dates.append(date_str)
            time.sleep(5)  # Wait before continuing

        current += timedelta(days=1)
        time.sleep(0.5)

    if failed_dates:
        print(f"\n[WARN] Failed to fetch {len(failed_dates)} dates: {failed_dates[:10]}...")

    return all_odds


def save_odds_csv(odds: list[dict], filepath: Path) -> None:
    """Save odds to CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if not odds:
        print("[WARN] No odds to save")
        return

    headers = list(odds[0].keys())

    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(odds)

    print(f"[INFO] Saved {len(odds)} odds records to {filepath}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch historical NCAAB betting odds"
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output CSV file (default: historical_odds/odds_YYYYMMDD_YYYYMMDD.csv)"
    )

    args = parser.parse_args(argv)

    print("=" * 72)
    print(" Historical NCAAB Odds Fetcher")
    print("=" * 72)
    print(f" Date Range: {args.start} to {args.end}")
    print(" Source: The Odds API (https://the-odds-api.com)")
    print("=" * 72)

    api_key = get_api_key()

    odds = fetch_date_range(api_key, args.start, args.end, DATA_DIR)

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        start_clean = args.start.replace("-", "")
        end_clean = args.end.replace("-", "")
        output_path = DATA_DIR / f"odds_{start_clean}_{end_clean}.csv"

    save_odds_csv(odds, output_path)

    print("\n" + "=" * 72)
    print(f" SUCCESS: Fetched {len(odds)} odds records")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
