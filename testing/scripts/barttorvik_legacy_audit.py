#!/usr/bin/env python3
"""
Barttorvik Legacy Audit: verify we can fetch and decode ALL legacy files and fields.

- Iterates seasons in a range and fetches `<season>_team_results.json`
- Confirms payload shape (array-of-arrays) and field counts per row
- Reports any anomalies (short rows, non-list payloads, HTTP errors)

Usage:
  python testing/scripts/barttorvik_legacy_audit.py --from 2010 --to 2025
  python testing/scripts/barttorvik_legacy_audit.py --season 2018

Exit codes: 0 on success (no anomalies), 1 if anomalies detected
"""

import argparse
import sys
import time
import random
from typing import List, Tuple

import requests


def retry_get(url: str, max_attempts: int = 4, timeout: int = 25) -> Tuple[bool, requests.Response | None, str]:
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "NCAAM-Ratings-Audit/1.0"})
            if resp.status_code == 200:
                return True, resp, ""
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                delay = 2 ** (attempt - 1)
                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    delay = int(ra)
                time.sleep(delay + random.random() * 0.25)
                last_err = f"status {resp.status_code}"
                continue
            return False, resp, f"unexpected status {resp.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
            if attempt == max_attempts:
                return False, None, last_err
            time.sleep(2 ** (attempt - 1) + random.random() * 0.25)
    return False, None, last_err


def audit_season(season: int) -> Tuple[bool, List[str]]:
    url = f"https://barttorvik.com/{season}_team_results.json"
    ok, resp, err = retry_get(url)
    if not ok:
        return False, [f"HTTP failure: {err}"]
    try:
        data = resp.json()
    except Exception as e:
        return False, [f"JSON decode error: {e}"]

    anomalies: List[str] = []
    if not isinstance(data, list):
        anomalies.append("payload is not a list")
        return False, anomalies

    # Basic field count expectation: modern files have >= 46 fields per row
    short_rows = 0
    for row in data:
        if not isinstance(row, list):
            anomalies.append("row not a list")
            continue
        if len(row) < 46:
            short_rows += 1
    if short_rows > 0:
        anomalies.append(f"{short_rows} rows with <46 fields")

    return len(anomalies) == 0, anomalies


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Barttorvik legacy audit")
    parser.add_argument("--from", dest="start", type=int, help="Starting season year")
    parser.add_argument("--to", dest="end", type=int, help="Ending season year")
    parser.add_argument("--season", dest="season", type=int, help="Single season to audit")
    args = parser.parse_args()

    seasons: List[int] = []
    if args.season:
        seasons = [args.season]
    elif args.start and args.end:
        start, end = args.start, args.end
        if start > end:
            start, end = end, start
        seasons = list(range(start, end + 1))
    else:
        print("Provide --season or --from and --to range.")
        sys.exit(2)

    all_ok = True
    for s in seasons:
        ok, anomalies = audit_season(s)
        status = "PASS" if ok else "FAIL"
        print(f"Season {s}: {status}")
        for a in anomalies:
            print(f"  - {a}")
        all_ok = all_ok and ok

    sys.exit(0 if all_ok else 1)
