#!/usr/bin/env python3
"""
ESPN Schedule Cross-Reference (NCAAM)

Fetches ESPN's public scoreboard JSON for a given date and prints a Markdown table.
Optionally cross-references a provided matchup list (e.g., sportsbook slate) to pull the
"official" start time + venue.

Data source:
    https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard

Usage:
    python testing/scripts/espn_schedule_xref.py --date 20251221
    python testing/scripts/espn_schedule_xref.py --date 20251221 --matchups-file matchups.txt

Matchups file format (one per line):
    Team A vs Team B
    Team A,Team B
Lines starting with "#" are ignored.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Optional
from zoneinfo import ZoneInfo


ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
)


@dataclass(frozen=True)
class EspnEvent:
    time_cst: str
    away: str
    home: str
    venue: str
    neutral_site: bool
    away_canon: str
    home_canon: str


def _norm_team_name(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(st)\b", "state", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Canonicalization for common sportsbook/ESPN short-name variants
    canon = {
        "connecticut": "uconn",
        "new mexico st": "new mexico state",
        "wisc milwaukee": "milwaukee",
        "cleveland st": "cleveland state",
        "indiana st": "indiana state",
        "illinois st": "illinois state",
        "long beach st": "long beach state",
        "iowa st": "iowa state",
        "idaho st": "idaho state",
        "cal poly slo": "cal poly",
        "cal irvine": "uc irvine",
        "north dakota st": "north dakota state",
        # ESPN short names sometimes use single-letter directions
        "n dakota state": "north dakota state",
        "n dakota": "north dakota",
        "s dakota state": "south dakota state",
        "s dakota": "south dakota",
    }
    return canon.get(s, s)


def _team_short(team_obj: dict) -> str:
    # Prefer shortDisplayName to avoid mascots (e.g., "Michigan" vs "Michigan Wolverines")
    return (
        team_obj.get("shortDisplayName")
        or team_obj.get("location")
        or team_obj.get("displayName")
        or ""
    )


def fetch_scoreboard(*, date_yyyymmdd: str, groups: int) -> dict:
    url = f"{ESPN_SCOREBOARD_URL}?dates={date_yyyymmdd}&groups={groups}"
    with urllib.request.urlopen(url, timeout=25) as resp:
        return json.load(resp)


def parse_events(payload: dict, *, tz: ZoneInfo) -> list[EspnEvent]:
    events: list[EspnEvent] = []
    for e in payload.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []

        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

        home_team = _team_short(home.get("team", {}))
        away_team = _team_short(away.get("team", {}))

        # ISO timestamp (UTC)
        date_str = comp.get("date") or e.get("date") or ""
        try:
            dt_local = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(tz)
            time_cst = dt_local.strftime("%I:%M %p")
        except Exception:
            time_cst = ""

        venue = comp.get("venue") or {}
        vname = venue.get("fullName") or ""
        city = (venue.get("address") or {}).get("city") or ""
        state = (venue.get("address") or {}).get("state") or ""
        loc = ", ".join([p for p in [city, state] if p])
        venue_str = " - ".join([p for p in [vname, loc] if p]).strip()

        neutral = bool(comp.get("neutralSite"))

        events.append(
            EspnEvent(
                time_cst=time_cst,
                away=away_team,
                home=home_team,
                venue=venue_str,
                neutral_site=neutral,
                away_canon=_norm_team_name(away_team),
                home_canon=_norm_team_name(home_team),
            )
        )

    return events


def _parse_matchups_file(path: str) -> list[tuple[str, str]]:
    matchups: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            lowered = line.lower()
            if " vs " in lowered:
                parts = re.split(r"\s+vs\s+", line, flags=re.IGNORECASE)
            elif "," in line:
                parts = [p.strip() for p in line.split(",", 1)]
            else:
                raise ValueError(
                    f"Invalid matchup line (expected 'A vs B' or 'A,B'): {line!r}"
                )

            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise ValueError(f"Invalid matchup line: {line!r}")
            matchups.append((parts[0].strip(), parts[1].strip()))

    return matchups


def _find_event(events: Iterable[EspnEvent], a: str, b: str) -> Optional[EspnEvent]:
    na, nb = _norm_team_name(a), _norm_team_name(b)
    for ev in events:
        pair = {ev.away_canon, ev.home_canon}
        if na in pair and nb in pair:
            return ev
    return None


def _print_table(rows: list[dict]) -> None:
    # Markdown table (works great in GitHub/Slack/Docs)
    headers = ["Time (CST)", "Away", "Home", "Venue", "Neutral"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        print(
            "| "
            + " | ".join(
                [
                    r.get("time", ""),
                    r.get("away", ""),
                    r.get("home", ""),
                    r.get("venue", ""),
                    "Y" if r.get("neutral") else "",
                ]
            )
            + " |"
        )


def _default_date_cst() -> str:
    tz = ZoneInfo("America/Chicago")
    return dt.datetime.now(tz=tz).strftime("%Y%m%d")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-reference sportsbook matchups to ESPN schedule")
    parser.add_argument("--date", type=str, default=_default_date_cst(), help="Date in YYYYMMDD")
    parser.add_argument("--groups", type=int, default=50, help="ESPN group (50 ~= full D1 slate)")
    parser.add_argument("--matchups-file", type=str, default="", help="Optional path to matchup list file")
    args = parser.parse_args()

    tz = ZoneInfo("America/Chicago")
    payload = fetch_scoreboard(date_yyyymmdd=args.date, groups=args.groups)
    events = parse_events(payload, tz=tz)

    if args.matchups_file:
        matchups = _parse_matchups_file(args.matchups_file)
        rows = []
        missing = []
        for a, b in matchups:
            ev = _find_event(events, a, b)
            if not ev:
                missing.append((a, b))
                continue
            rows.append(
                {
                    "time": ev.time_cst,
                    "away": ev.away,
                    "home": ev.home,
                    "venue": ev.venue,
                    "neutral": ev.neutral_site,
                }
            )

        _print_table(rows)

        if missing:
            print("\nMissing matchups (not found in ESPN feed):")
            for a, b in missing:
                print(f"- {a} vs {b}")
            return 1

        return 0

    # No matchups file: print the whole slate
    rows = [
        {
            "time": ev.time_cst,
            "away": ev.away,
            "home": ev.home,
            "venue": ev.venue,
            "neutral": ev.neutral_site,
        }
        for ev in events
    ]
    _print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


