#!/usr/bin/env python3
"""
Ingestion Healthcheck: verifies external API accessibility and basic data integrity.

Checks:
- Barttorvik ratings JSON endpoint responds and decodes
- The Odds API odds endpoint responds with valid JSON using configured API key

Usage:
    python testing/scripts/ingestion_healthcheck.py
    python testing/scripts/ingestion_healthcheck.py --season 2025 --sport-key basketball_ncaab

Exit codes:
- 0: All checks passed
- 1: One or more checks failed
"""

import argparse
import os
import sys
import time
import random
from typing import Tuple

import requests

DEFAULT_SPORT_KEY = "basketball_ncaab"


def _read_secret_file(file_path: str, secret_name: str) -> str:
    """Read secret from Docker secret file - REQUIRED, NO fallbacks when env missing."""
    try:
        with open(file_path, "r") as f:
            value = f.read().strip()
            if not value:
                raise ValueError(f"Secret file {file_path} is empty")
            return value
    except FileNotFoundError:
        raise FileNotFoundError(
            f"CRITICAL: Secret file not found: {file_path} ({secret_name}). "
            f"Container must have secrets mounted."
        )


def get_current_season() -> int:
    """Match Go service logic: season switches after May."""
    from datetime import datetime
    now = datetime.now()
    year = now.year
    if now.month >= 5:
        return year + 1
    return year


def _retry_request(method: str, url: str, *, params=None, headers=None, timeout=20, max_attempts=4) -> Tuple[bool, requests.Response | None, str]:
    """Perform HTTP request with exponential backoff + jitter, handling 429/5xx."""
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.request(method, url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return True, resp, ""
            # Retry on 429 or 5xx
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                delay = 2 ** (attempt - 1)
                # Honor Retry-After if present
                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    delay = int(ra)
                # jitter 0-250ms
                delay = delay + random.random() * 0.25
                time.sleep(delay)
                last_err = f"status {resp.status_code}"
                continue
            # Non-retryable
            return False, resp, f"unexpected status {resp.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
            if attempt == max_attempts:
                return False, None, last_err
            delay = 2 ** (attempt - 1) + random.random() * 0.25
            time.sleep(delay)
    return False, None, last_err


def check_barttorvik(season: int) -> Tuple[bool, str]:
    url = f"https://barttorvik.com/{season}_team_results.json"
    ok, resp, err = _retry_request("GET", url, timeout=25)
    if not ok:
        return False, f"Barttorvik check failed: {err}"
    try:
        data = resp.json()
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            return True, f"Barttorvik OK: {len(data)} team rows"
        return False, "Barttorvik payload not in expected array-of-arrays format"
    except Exception as e:
        return False, f"Barttorvik JSON decode error: {e}"


def check_odds_api(sport_key: str) -> Tuple[bool, str]:
    # Get API key from env (Azure) or Docker secret file (Compose)
    api_key = os.getenv("THE_ODDS_API_KEY")
    if not api_key:
        try:
            api_key = _read_secret_file("/run/secrets/odds_api_key", "odds_api_key")
        except Exception as e:
            return False, f"Odds API key missing: {e}"

    # Validate key is not a placeholder
    key_lower = api_key.strip().lower()
    if ("change_me" in key_lower 
        or key_lower.startswith("sample") 
        or key_lower.startswith("your_")
        or key_lower.startswith("<your")):
        return False, "Odds API key appears to be a placeholder. Get your key from https://the-odds-api.com/"

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "spreads,totals",
        "oddsFormat": "american",
    }
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    ok, resp, err = _retry_request("GET", url, params=params, timeout=25)
    if not ok:
        return False, f"Odds API check failed: {err}"
    try:
        data = resp.json()
        if isinstance(data, list):
            # Log request quota if available
            remaining = resp.headers.get("x-requests-remaining", "?")
            return True, f"Odds API OK: {len(data)} events (remaining: {remaining})"
        return False, "Odds API payload not a list"
    except Exception as e:
        return False, f"Odds API JSON decode error: {e}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion healthcheck")
    parser.add_argument("--season", type=int, default=get_current_season(), help="Barttorvik season year")
    parser.add_argument("--sport-key", type=str, default=DEFAULT_SPORT_KEY, help="Odds API sport key")
    args = parser.parse_args()

    b_ok, b_msg = check_barttorvik(args.season)
    o_ok, o_msg = check_odds_api(args.sport_key)

    print(f"Barttorvik: {'PASS' if b_ok else 'FAIL'} - {b_msg}")
    print(f"Odds API:  {'PASS' if o_ok else 'FAIL'} - {o_msg}")

    sys.exit(0 if (b_ok and o_ok) else 1)

