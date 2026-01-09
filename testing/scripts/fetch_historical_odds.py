#!/usr/bin/env python3
"""
Fetch Historical Betting Lines from The Odds API

This script fetches historical NCAAB betting lines for backtesting, covering both full-game and first-half markets.
Outputs include an is_march_madness flag based on the game date (override with --tourney-start/--tourney-end).
Data available from late 2020.

API Documentation: https://the-odds-api.com/liveapi/guides/v4/

Usage:
    # Set API key first
    export ODDS_API_KEY=your_key_here

    # Fetch odds for a date range
    python testing/scripts/fetch_historical_odds.py --start 2024-01-01 --end 2024-03-31

    # Fetch a full season (2024-25)
    python testing/scripts/fetch_historical_odds.py --season 2025

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
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:
    print("[ERROR] requests library required: pip install requests")
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_ROOT = Path(
    os.environ.get("HISTORICAL_DATA_ROOT", ROOT_DIR / "ncaam_historical_data_local")
).resolve()
ODDS_RAW_DIR = Path(
    os.environ.get("HISTORICAL_ODDS_RAW_DIR", HISTORICAL_ROOT / "odds" / "raw")
).resolve()

# Import team canonicalization from single source of truth
# team_utils.py is in the same directory (testing/scripts/)
try:
    from team_utils import resolve_team_name
except ImportError:
    print("[ERROR] team_utils module required - must be in testing/scripts/")
    sys.exit(1)

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"

# Canonicalization threshold - fail if more than 10% of games have unresolved teams
UNRESOLVED_THRESHOLD = 0.10


def get_api_key() -> str:
    """Get Odds API key using unified secrets manager.
    
    Priority order (first found wins):
    1. THE_ODDS_API_KEY environment variable
    2. Docker secret at /run/secrets/odds_api_key
    3. Local file at secrets/odds_api_key.txt
    """
    sys.path.insert(0, str(ROOT_DIR / "testing" / "scripts"))
    from secrets_manager import get_api_key as get_secret_api_key
    return get_secret_api_key("odds")


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
    markets: str = "spreads,totals,spreads_h1,totals_h1,h2h"
) -> dict | None:
    """
    Fetch historical odds for a specific event.
    
    Automatically falls back to non-H1 markets if H1 data unavailable.

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
        if e.response.status_code == 422:
            # Check if it's a markets unavailable error - try without H1 markets
            try:
                error_data = e.response.json()
                if "HISTORICAL_MARKETS_UNAVAILABLE" in error_data.get("error_code", ""):
                    # Retry without H1 markets
                    fallback_markets = "spreads,totals,h2h"
                    params["markets"] = fallback_markets
                    resp = fetch_with_retry(url, params)
                    return resp.json()
            except Exception:
                pass
            return None
        if e.response.status_code == 404:
            return None
        raise
    except Exception:
        return None  # Skip event on persistent errors


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_spread_point(outcomes: list[dict], home_team: str | None) -> float | None:
    if not home_team:
        return None
    for o in outcomes:
        if o.get("name") == home_team:
            return _to_float(o.get("point"))
    return None


def _extract_spread_prices(
    outcomes: list[dict],
    home_team: str | None,
    away_team: str | None,
) -> tuple[float | None, float | None]:
    """Extract juice/price for home and away team spreads."""
    home_price = None
    away_price = None
    if not outcomes:
        return home_price, away_price
    for o in outcomes:
        name = o.get("name")
        if home_team and name == home_team:
            home_price = _to_float(o.get("price"))
        if away_team and name == away_team:
            away_price = _to_float(o.get("price"))
    return home_price, away_price


def _extract_total_point(outcomes: list[dict]) -> float | None:
    for o in outcomes:
        name = o.get("name", "")
        if isinstance(name, str) and name.lower() == "over":
            return _to_float(o.get("point"))
    if outcomes:
        return _to_float(outcomes[0].get("point"))
    return None


def _extract_total_price(outcomes: list[dict]) -> tuple[float | None, float | None]:
    """Extract juice/price for over and under."""
    over_price = None
    under_price = None
    for o in outcomes:
        name = o.get("name", "")
        if isinstance(name, str):
            if name.lower() == "over":
                over_price = _to_float(o.get("price"))
            elif name.lower() == "under":
                under_price = _to_float(o.get("price"))
    return over_price, under_price


def _extract_moneyline_prices(
    outcomes: list[dict],
    home_team: str | None,
    away_team: str | None,
) -> tuple[float | None, float | None]:
    """Extract moneyline prices for home and away teams."""
    home_price = None
    away_price = None
    if not outcomes:
        return home_price, away_price
    for o in outcomes:
        name = o.get("name")
        if home_team and name == home_team:
            home_price = _to_float(o.get("price"))
        if away_team and name == away_team:
            away_price = _to_float(o.get("price"))
    return home_price, away_price


def _parse_commence_date(commence_time: str | None) -> date | None:
    if not commence_time:
        return None
    try:
        return datetime.fromisoformat(commence_time.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _default_march_madness_window(year: int) -> tuple[date, date]:
    return date(year, 3, 15), date(year, 4, 8)


def _is_march_madness(
    commence_time: str | None,
    tourney_window: tuple[date, date] | None,
) -> bool:
    game_date = _parse_commence_date(commence_time)
    if not game_date:
        return False
    if tourney_window:
        start, end = tourney_window
    else:
        start, end = _default_march_madness_window(game_date.year)
    return start <= game_date <= end


def _select_bookmakers(bookmakers: list[dict], mode: str) -> list[dict]:
    if mode == "all":
        return bookmakers

    # Preferred books: Pinnacle (sharp) then major US books.
    target_books = ["pinnacle", "draftkings", "fanduel", "betmgm"]
    selected = []
    for book_name in target_books:
        for bm in bookmakers:
            if bm.get("key", "").lower() == book_name:
                selected.append(bm)
                break
        if selected:
            break

    if selected:
        return selected

    return bookmakers[:1] if bookmakers else []


def _parse_bookmaker_row(
    event: dict,
    bookmaker: dict,
    odds_data: dict,
    tourney_window: tuple[date, date] | None = None,
) -> dict | None:
    """Parse a single bookmaker's odds for an event.
    
    Team names are canonicalized using the central resolver.
    Returns dict with '_unresolved' key if teams cannot be resolved.
    """
    home_team_raw = event.get("home_team")
    away_team_raw = event.get("away_team")
    
    # Canonicalize team names at ingestion
    home_team = resolve_team_name(home_team_raw) if home_team_raw else None
    away_team = resolve_team_name(away_team_raw) if away_team_raw else None
    
    # Check for unresolved teams (resolver returns input unchanged if not found)
    unresolved = []
    if home_team_raw and home_team == home_team_raw:
        # Could be canonical already - check case-insensitive
        check = resolve_team_name(home_team_raw.lower())
        if check == home_team_raw.lower():
            unresolved.append(("home", home_team_raw))
    if away_team_raw and away_team == away_team_raw:
        check = resolve_team_name(away_team_raw.lower())
        if check == away_team_raw.lower():
            unresolved.append(("away", away_team_raw))
    
    if unresolved:
        # Return marker for threshold tracking
        return {
            "_unresolved": unresolved,
            "event_id": event.get("id"),
            "commence_time": event.get("commence_time"),
            "home_team_raw": home_team_raw,
            "away_team_raw": away_team_raw,
        }
    
    spread = None
    spread_home_price = None
    spread_away_price = None
    total = None
    total_over_price = None
    total_under_price = None
    h1_spread = None
    h1_spread_home_price = None
    h1_spread_away_price = None
    h1_total = None
    h1_total_over_price = None
    h1_total_under_price = None
    moneyline_home_price = None
    moneyline_away_price = None

    # Use raw names for matching in outcomes (API returns raw names)
    for market in bookmaker.get("markets", []):
        key = market.get("key")
        outcomes = market.get("outcomes", []) or []

        if key == "spreads":
            spread = _extract_spread_point(outcomes, home_team_raw)
            spread_home_price, spread_away_price = _extract_spread_prices(outcomes, home_team_raw, away_team_raw)
        elif key == "spreads_h1":
            h1_spread = _extract_spread_point(outcomes, home_team_raw)
            h1_spread_home_price, h1_spread_away_price = _extract_spread_prices(outcomes, home_team_raw, away_team_raw)
        elif key == "totals":
            total = _extract_total_point(outcomes)
            total_over_price, total_under_price = _extract_total_price(outcomes)
        elif key == "totals_h1":
            h1_total = _extract_total_point(outcomes)
            h1_total_over_price, h1_total_under_price = _extract_total_price(outcomes)
        elif key == "h2h":
            moneyline_home_price, moneyline_away_price = _extract_moneyline_prices(
                outcomes, home_team_raw, away_team_raw
            )

    commence_time = event.get("commence_time")

    return {
        "event_id": event.get("id"),
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "bookmaker": bookmaker.get("key"),
        "bookmaker_title": bookmaker.get("title"),
        "bookmaker_last_update": bookmaker.get("last_update"),
        "spread": spread,
        "spread_price": spread_home_price,
        "spread_home_price": spread_home_price,
        "spread_away_price": spread_away_price,
        "total": total,
        "total_over_price": total_over_price,
        "total_under_price": total_under_price,
        "moneyline_home_price": moneyline_home_price,
        "moneyline_away_price": moneyline_away_price,
        "h1_spread": h1_spread,
        "h1_spread_price": h1_spread_home_price,
        "h1_spread_home_price": h1_spread_home_price,
        "h1_spread_away_price": h1_spread_away_price,
        "h1_total": h1_total,
        "h1_total_over_price": h1_total_over_price,
        "h1_total_under_price": h1_total_under_price,
        "is_march_madness": _is_march_madness(commence_time, tourney_window),
        "timestamp": odds_data.get("timestamp"),
    }


def parse_odds_rows(
    event: dict,
    odds_data: dict,
    tourney_window: tuple[date, date] | None = None,
    bookmakers_mode: str = "all",
) -> list[dict]:
    """Extract relevant fields from odds response."""
    try:
        data = odds_data.get("data", {})
        bookmakers = data.get("bookmakers", [])

        if not bookmakers:
            return []

        selected = _select_bookmakers(bookmakers, bookmakers_mode)
        rows = []
        for bm in selected:
            row = _parse_bookmaker_row(event, bm, odds_data, tourney_window=tourney_window)
            if row:
                rows.append(row)
        return rows
    except Exception as e:
        print(f"  [WARN] Parse error: {e}")
        return []


def fetch_date_range(
    api_key: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    markets: str,
    tourney_window: tuple[date, date] | None = None,
    save_interval: int = 7,  # Save every 7 days
    bookmakers_mode: str = "all",
    checkpoint_tag: str | None = None,
) -> list[dict]:
    """Fetch odds for all games in a date range with incremental saving.
    
    Team names are canonicalized at ingestion. If >10% of a day's games 
    have unresolved teams, the script aborts.
    
    Raises:
        RuntimeError: If >10% of games on any day have unresolved team names
    """
    all_odds = []
    all_unresolved = []  # Track all unresolved for summary
    days_since_save = 0

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    current = start
    failed_dates = []
    failed_events = 0

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n[INFO] Fetching {date_str}...")

        day_resolved = []
        day_unresolved = []

        try:
            events = fetch_historical_events(api_key, date_str)
            print(f"  Found {len(events)} events")

            for event in events:
                event_id = event.get("id")
                commence = event.get("commence_time", "")

                # Fetch odds at game time - skip on failure
                try:
                    odds = fetch_historical_odds(api_key, event_id, commence, markets=markets)

                    if odds:
                        parsed_rows = parse_odds_rows(
                            event,
                            odds,
                            tourney_window=tourney_window,
                            bookmakers_mode=bookmakers_mode,
                        )
                        for parsed in parsed_rows:
                            if "_unresolved" in parsed:
                                # Track unresolved for threshold checking
                                day_unresolved.append(parsed)
                                all_unresolved.append(parsed)
                            else:
                                day_resolved.append(parsed)
                                print(
                                    f"    {parsed['away_team']} @ {parsed['home_team']} "
                                    f"({parsed.get('bookmaker')}): "
                                    f"spread={parsed['spread']}, total={parsed['total']}, "
                                    f"h1_spread={parsed['h1_spread']}, h1_total={parsed['h1_total']}"
                                )
                except Exception as e:
                    failed_events += 1
                    print(f"    [SKIP] Failed to fetch event {event_id}: {e}")
                    continue

                # Throttle lightly
                time.sleep(0.05)

            # Check threshold for this day
            total_day = len(day_resolved) + len(day_unresolved)
            if total_day > 0 and len(day_unresolved) > 0:
                failure_rate = len(day_unresolved) / total_day
                
                if failure_rate > UNRESOLVED_THRESHOLD:
                    # More than 10% failed - abort
                    msg = (f"[ERROR] {date_str}: "
                           f"{len(day_unresolved)}/{total_day} events ({failure_rate:.1%}) have unresolved teams "
                           f"(threshold: {UNRESOLVED_THRESHOLD:.0%})")
                    print(msg)
                    seen = set()
                    for g in day_unresolved:
                        for side, name in g["_unresolved"]:
                            if name not in seen:
                                print(f"  - UNRESOLVED {side}: '{name}'")
                                seen.add(name)
                    raise RuntimeError(msg)
                else:
                    # Under threshold - log warning and skip
                    print(f"  [WARN] Skipping {len(day_unresolved)} events with unresolved teams")
                    seen = set()
                    for g in day_unresolved:
                        for side, name in g["_unresolved"]:
                            if name not in seen:
                                print(f"    - UNRESOLVED {side}: '{name}'")
                                seen.add(name)

            all_odds.extend(day_resolved)
            days_since_save += 1

            # Save incrementally
            if days_since_save >= save_interval and all_odds:
                tag = f"_{checkpoint_tag}" if checkpoint_tag else ""
                temp_path = output_dir / f"odds_partial{tag}_{start_date.replace('-', '')}_{date_str.replace('-', '')}.csv"
                save_odds_csv(all_odds, temp_path)
                print(f"  [CHECKPOINT] Saved {len(all_odds)} records")
                days_since_save = 0

        except RuntimeError:
            raise  # Re-raise threshold errors
        except Exception as e:
            print(f"  [ERROR] Failed to fetch {date_str}: {e}")
            failed_dates.append(date_str)
            time.sleep(5)  # Wait before continuing

        current += timedelta(days=1)
        time.sleep(0.05)  # Was 0.5

    if failed_dates:
        print(f"\n[WARN] Failed to fetch {len(failed_dates)} dates: {failed_dates[:10]}...")
    
    if all_unresolved:
        print(f"\n[WARN] Skipped {len(all_unresolved)} events total due to unresolved teams")

    return all_odds


PREFERRED_HEADERS = [
    "event_id",
    "commence_time",
    "home_team",
    "away_team",
    "bookmaker",
    "bookmaker_title",
    "bookmaker_last_update",
    "spread",
    "spread_price",
    "spread_home_price",
    "spread_away_price",
    "total",
    "total_over_price",
    "total_under_price",
    "moneyline_home_price",
    "moneyline_away_price",
    "h1_spread",
    "h1_spread_price",
    "h1_spread_home_price",
    "h1_spread_away_price",
    "h1_total",
    "h1_total_over_price",
    "h1_total_under_price",
    "is_march_madness",
    "timestamp",
]


def _build_headers(rows: Iterable[dict]) -> list[str]:
    seen = set()
    ordered = []
    for key in PREFERRED_HEADERS:
        seen.add(key)
        ordered.append(key)
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
    return ordered


def save_odds_csv(odds: list[dict], filepath: Path) -> None:
    """Save odds to CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if not odds:
        print("[WARN] No odds to save")
        return

    headers = _build_headers(odds)

    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(odds)

    print(f"[INFO] Saved {len(odds)} odds records to {filepath}")


def _season_date_range(season: int) -> tuple[str, str]:
    """
    Map an NCAA season to its default date range.

    Season is represented by the spring year (e.g., 2025 for the 2024-25 season).
    """
    start = date(season - 1, 11, 1)
    end = date(season, 4, 30)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _parse_date_arg(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date format: {value} (expected YYYY-MM-DD)") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch historical NCAAB betting odds"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--season",
        type=int,
        help="Season year (e.g., 2025 for the 2024-25 season); fills start/end automatically"
    )
    parser.add_argument(
        "--tourney-start",
        type=str,
        help="Optional March Madness start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--tourney-end",
        type=str,
        help="Optional March Madness end date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--bookmakers",
        type=str,
        choices=["all", "preferred"],
        default=os.environ.get("HISTORICAL_ODDS_BOOKMAKERS", "all"),
        help="Bookmaker selection: all or preferred (default: all)"
    )
    parser.add_argument(
        "--markets",
        type=str,
        default=os.environ.get("HISTORICAL_ODDS_MARKETS", "spreads,totals,spreads_h1,totals_h1,h2h"),
        help="Comma-separated markets (default: spreads,totals,spreads_h1,totals_h1,h2h)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output CSV file (default: odds/raw/odds_YYYYMMDD_YYYYMMDD.csv or odds_season_YYYY_YYYY.csv)"
    )
    parser.add_argument(
        "--job-id",
        type=str,
        help="Optional job id to namespace checkpoint files and output names"
    )

    args = parser.parse_args(argv)

    season_range = None
    if args.season:
        season_range = _season_date_range(args.season)

    start_date = args.start or (season_range[0] if season_range else None)
    end_date = args.end or (season_range[1] if season_range else None)

    if not start_date or not end_date:
        parser.error("Please provide both --start and --end, or use --season to auto-populate them.")

    tourney_window = None
    if args.tourney_start or args.tourney_end:
        if not args.tourney_start or not args.tourney_end:
            parser.error("Please provide both --tourney-start and --tourney-end.")
        try:
            tourney_window = (
                _parse_date_arg(args.tourney_start),
                _parse_date_arg(args.tourney_end),
            )
        except ValueError as exc:
            parser.error(str(exc))
    elif args.season:
        tourney_window = _default_march_madness_window(args.season)

    print("=" * 72)
    print(" Historical NCAAB Odds Fetcher")
    print("=" * 72)
    if args.season:
        print(f" Season: {args.season} ({start_date} to {end_date})")
    else:
        print(f" Date Range: {start_date} to {end_date}")
    if tourney_window:
        print(f" March Madness window: {tourney_window[0]} to {tourney_window[1]}")
    print(f" Bookmakers: {args.bookmakers}")
    print(f" Markets: {args.markets}")
    if args.job_id:
        print(f" Job ID: {args.job_id}")
    print(" Source: The Odds API (https://the-odds-api.com)")
    print("=" * 72)

    api_key = get_api_key()

    odds = fetch_date_range(
        api_key,
        start_date,
        end_date,
        ODDS_RAW_DIR,
        args.markets,
        tourney_window=tourney_window,
        bookmakers_mode=args.bookmakers,
        checkpoint_tag=args.job_id,
    )

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        start_clean = start_date.replace("-", "")
        end_clean = end_date.replace("-", "")
        job_label = f"_{args.job_id}" if args.job_id else ""
        if args.season:
            season_label = f"season_{args.season}"
            output_path = ODDS_RAW_DIR / f"odds_{season_label}{job_label}_{start_clean}_{end_clean}.csv"
        else:
            output_path = ODDS_RAW_DIR / f"odds{job_label}_{start_clean}_{end_clean}.csv"

    save_odds_csv(odds, output_path)

    print("\n" + "=" * 72)
    print(f" SUCCESS: Fetched {len(odds)} odds records")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
