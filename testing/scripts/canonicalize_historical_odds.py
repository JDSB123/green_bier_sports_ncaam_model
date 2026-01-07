#!/usr/bin/env python3
"""
Canonicalize historical odds and expand matchup rows into team-level rows.

This keeps the raw odds values but aligns team names to the production
canonical mapping, then emits two outputs:
1) Matchup-level canonical file (home/away preserved)
2) Team-level canonical file (two rows per matchup, team perspective)
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_ROOT = Path(
    os.environ.get("HISTORICAL_DATA_ROOT", ROOT_DIR / "ncaam_historical_data_local")
).resolve()
ODDS_RAW_DIR = Path(
    os.environ.get("HISTORICAL_ODDS_RAW_DIR", HISTORICAL_ROOT / "odds" / "raw")
).resolve()
ODDS_NORMALIZED_DIR = Path(
    os.environ.get("HISTORICAL_ODDS_NORMALIZED_DIR", HISTORICAL_ROOT / "odds" / "normalized")
).resolve()

sys.path.insert(0, str(ROOT_DIR / "testing"))

from production_parity.team_resolver import ProductionTeamResolver

MATCHUP_COLUMNS = [
    "event_id",
    "commence_time",
    "home_team",
    "away_team",
    "home_team_canonical",
    "away_team_canonical",
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
    "game_date",
    "season",
]

TEAM_COLUMNS = [
    "event_id",
    "commence_time",
    "game_date",
    "season",
    "bookmaker",
    "bookmaker_title",
    "bookmaker_last_update",
    "team",
    "team_canonical",
    "opponent",
    "opponent_canonical",
    "is_home",
    "spread",
    "team_spread",
    "team_spread_price",
    "spread_home_price",
    "spread_away_price",
    "total",
    "total_over_price",
    "total_under_price",
    "moneyline_home_price",
    "moneyline_away_price",
    "team_moneyline_price",
    "h1_spread",
    "team_h1_spread",
    "team_h1_spread_price",
    "h1_spread_home_price",
    "h1_spread_away_price",
    "h1_total",
    "h1_total_over_price",
    "h1_total_under_price",
    "is_march_madness",
    "timestamp",
]

MARKET_FIELDS = (
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
)

METADATA_FIELDS = (
    "bookmaker",
    "bookmaker_title",
    "bookmaker_last_update",
)


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromtimestamp(float(value))
        except (ValueError, TypeError):
            return None


def _game_date_from_commence(commence_time: str) -> str:
    dt = _parse_datetime(commence_time)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d")


def _season_from_commence(commence_time: str) -> int:
    dt = _parse_datetime(commence_time)
    if not dt:
        return 0
    return dt.year + 1 if dt.month >= 11 else dt.year


def _default_march_madness_window(year: int) -> Tuple[date, date]:
    return date(year, 3, 15), date(year, 4, 8)


def _detect_march_madness(
    commence_time: str,
    tourney_window: Optional[Tuple[date, date]] = None,
) -> bool:
    dt = _parse_datetime(commence_time)
    if not dt:
        return False
    start, end = tourney_window or _default_march_madness_window(dt.year)
    return start <= dt.date() <= end


def _to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_float(value: Optional[float]) -> str:
    return "" if value is None else str(value)

def _has_value(value: Optional[str]) -> bool:
    return value not in (None, "")


def _merge_rows(
    existing: Dict[str, str],
    incoming: Dict[str, str],
    prefer_incoming: bool,
) -> Dict[str, str]:
    merged = dict(existing)

    all_fields = MARKET_FIELDS + METADATA_FIELDS

    if prefer_incoming:
        for field in all_fields:
            if _has_value(incoming.get(field)):
                merged[field] = incoming.get(field, "")
        merged["timestamp"] = incoming.get("timestamp", merged.get("timestamp", ""))
    else:
        for field in all_fields:
            if not _has_value(merged.get(field)) and _has_value(incoming.get(field)):
                merged[field] = incoming.get(field, "")

    return merged


def _iter_input_files(input_path: Optional[Path], input_dir: Path) -> List[Path]:
    if input_path:
        return [input_path]

    csv_files = sorted(input_dir.glob("*.csv"))
    exclude_prefixes = (
        "odds_consolidated_canonical",
        "odds_canonical_matchups",
        "odds_team_rows_canonical",
    )
    filtered = []
    for path in csv_files:
        name = path.name
        if name.startswith(exclude_prefixes):
            continue
        filtered.append(path)
    return filtered


def _dedupe_key(row: Dict[str, str]) -> str:
    event_id = (row.get("event_id") or "").strip()
    bookmaker = (row.get("bookmaker") or "").strip()
    if event_id:
        return f"event:{event_id}|book:{bookmaker}"
    home = (row.get("home_team_canonical") or "").strip()
    away = (row.get("away_team_canonical") or "").strip()
    game_date = (row.get("game_date") or "").strip()
    return f"{home}|{away}|{game_date}|{bookmaker}"


def _normalize_matchup_row(
    row: Dict[str, str],
    resolver: ProductionTeamResolver,
    tourney_window: Optional[Tuple[date, date]] = None,
) -> Tuple[Optional[Dict[str, str]], List[str]]:
    home_team = (row.get("home_team") or "").strip()
    away_team = (row.get("away_team") or "").strip()

    if not home_team or not away_team:
        return None, []

    home_result = resolver.resolve(home_team)
    away_result = resolver.resolve(away_team)

    unresolved = []
    if not home_result.resolved:
        unresolved.append(home_team)
    if not away_result.resolved:
        unresolved.append(away_team)

    if unresolved:
        return None, unresolved

    commence_time = row.get("commence_time", "")
    game_date = _game_date_from_commence(commence_time)
    season = _season_from_commence(commence_time)

    is_mm_value = _detect_march_madness(commence_time, tourney_window=tourney_window)

    normalized = {
        "event_id": row.get("event_id", ""),
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "home_team_canonical": home_result.canonical_name or "",
        "away_team_canonical": away_result.canonical_name or "",
        "bookmaker": row.get("bookmaker", ""),
        "bookmaker_title": row.get("bookmaker_title", ""),
        "bookmaker_last_update": row.get("bookmaker_last_update", ""),
        "spread": row.get("spread", ""),
        "spread_price": row.get("spread_price", ""),
        "spread_home_price": row.get("spread_home_price", row.get("spread_price", "")),
        "spread_away_price": row.get("spread_away_price", ""),
        "total": row.get("total", ""),
        "total_over_price": row.get("total_over_price", ""),
        "total_under_price": row.get("total_under_price", ""),
        "moneyline_home_price": row.get("moneyline_home_price", ""),
        "moneyline_away_price": row.get("moneyline_away_price", ""),
        "h1_spread": row.get("h1_spread", ""),
        "h1_spread_price": row.get("h1_spread_price", ""),
        "h1_spread_home_price": row.get("h1_spread_home_price", row.get("h1_spread_price", "")),
        "h1_spread_away_price": row.get("h1_spread_away_price", ""),
        "h1_total": row.get("h1_total", ""),
        "h1_total_over_price": row.get("h1_total_over_price", ""),
        "h1_total_under_price": row.get("h1_total_under_price", ""),
        "is_march_madness": str(bool(is_mm_value)),
        "timestamp": row.get("timestamp", ""),
        "game_date": game_date,
        "season": season,
    }

    return normalized, []


def _matchup_to_team_rows(matchup: Dict[str, str]) -> List[Dict[str, str]]:
    spread = _to_float(matchup.get("spread"))
    h1_spread = _to_float(matchup.get("h1_spread"))
    spread_home_price = _to_float(matchup.get("spread_home_price") or matchup.get("spread_price"))
    spread_away_price = _to_float(matchup.get("spread_away_price"))
    h1_spread_home_price = _to_float(matchup.get("h1_spread_home_price") or matchup.get("h1_spread_price"))
    h1_spread_away_price = _to_float(matchup.get("h1_spread_away_price"))
    moneyline_home_price = _to_float(matchup.get("moneyline_home_price"))
    moneyline_away_price = _to_float(matchup.get("moneyline_away_price"))

    home_row = {
        "event_id": matchup.get("event_id", ""),
        "commence_time": matchup.get("commence_time", ""),
        "game_date": matchup.get("game_date", ""),
        "season": matchup.get("season", ""),
        "bookmaker": matchup.get("bookmaker", ""),
        "bookmaker_title": matchup.get("bookmaker_title", ""),
        "bookmaker_last_update": matchup.get("bookmaker_last_update", ""),
        "team": matchup.get("home_team", ""),
        "team_canonical": matchup.get("home_team_canonical", ""),
        "opponent": matchup.get("away_team", ""),
        "opponent_canonical": matchup.get("away_team_canonical", ""),
        "is_home": "1",
        "spread": matchup.get("spread", ""),
        "team_spread": _format_float(spread) if spread is not None else "",
        "team_spread_price": _format_float(spread_home_price) if spread_home_price is not None else "",
        "spread_home_price": _format_float(spread_home_price) if spread_home_price is not None else "",
        "spread_away_price": _format_float(spread_away_price) if spread_away_price is not None else "",
        "total": matchup.get("total", ""),
        "total_over_price": matchup.get("total_over_price", ""),
        "total_under_price": matchup.get("total_under_price", ""),
        "moneyline_home_price": _format_float(moneyline_home_price) if moneyline_home_price is not None else "",
        "moneyline_away_price": _format_float(moneyline_away_price) if moneyline_away_price is not None else "",
        "team_moneyline_price": _format_float(moneyline_home_price) if moneyline_home_price is not None else "",
        "h1_spread": matchup.get("h1_spread", ""),
        "team_h1_spread": _format_float(h1_spread) if h1_spread is not None else "",
        "team_h1_spread_price": _format_float(h1_spread_home_price) if h1_spread_home_price is not None else "",
        "h1_spread_home_price": _format_float(h1_spread_home_price) if h1_spread_home_price is not None else "",
        "h1_spread_away_price": _format_float(h1_spread_away_price) if h1_spread_away_price is not None else "",
        "h1_total": matchup.get("h1_total", ""),
        "h1_total_over_price": matchup.get("h1_total_over_price", ""),
        "h1_total_under_price": matchup.get("h1_total_under_price", ""),
        "is_march_madness": matchup.get("is_march_madness", ""),
        "timestamp": matchup.get("timestamp", ""),
    }

    away_row = {
        "event_id": matchup.get("event_id", ""),
        "commence_time": matchup.get("commence_time", ""),
        "game_date": matchup.get("game_date", ""),
        "season": matchup.get("season", ""),
        "bookmaker": matchup.get("bookmaker", ""),
        "bookmaker_title": matchup.get("bookmaker_title", ""),
        "bookmaker_last_update": matchup.get("bookmaker_last_update", ""),
        "team": matchup.get("away_team", ""),
        "team_canonical": matchup.get("away_team_canonical", ""),
        "opponent": matchup.get("home_team", ""),
        "opponent_canonical": matchup.get("home_team_canonical", ""),
        "is_home": "0",
        "spread": matchup.get("spread", ""),
        "team_spread": _format_float(-spread) if spread is not None else "",
        "team_spread_price": _format_float(spread_away_price) if spread_away_price is not None else "",
        "spread_home_price": _format_float(spread_home_price) if spread_home_price is not None else "",
        "spread_away_price": _format_float(spread_away_price) if spread_away_price is not None else "",
        "total": matchup.get("total", ""),
        "total_over_price": matchup.get("total_over_price", ""),
        "total_under_price": matchup.get("total_under_price", ""),
        "moneyline_home_price": _format_float(moneyline_home_price) if moneyline_home_price is not None else "",
        "moneyline_away_price": _format_float(moneyline_away_price) if moneyline_away_price is not None else "",
        "team_moneyline_price": _format_float(moneyline_away_price) if moneyline_away_price is not None else "",
        "h1_spread": matchup.get("h1_spread", ""),
        "team_h1_spread": _format_float(-h1_spread) if h1_spread is not None else "",
        "team_h1_spread_price": _format_float(h1_spread_away_price) if h1_spread_away_price is not None else "",
        "h1_spread_home_price": _format_float(h1_spread_home_price) if h1_spread_home_price is not None else "",
        "h1_spread_away_price": _format_float(h1_spread_away_price) if h1_spread_away_price is not None else "",
        "h1_total": matchup.get("h1_total", ""),
        "h1_total_over_price": matchup.get("h1_total_over_price", ""),
        "h1_total_under_price": matchup.get("h1_total_under_price", ""),
        "is_march_madness": matchup.get("is_march_madness", ""),
        "timestamp": matchup.get("timestamp", ""),
    }

    return [home_row, away_row]


def _write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Canonicalize historical odds and expand to team rows."
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Optional single CSV input file. Defaults to all CSVs in odds/raw.",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=str(ODDS_RAW_DIR),
        help="Directory containing odds CSV files (default: odds/raw).",
    )
    parser.add_argument(
        "--output-matchups",
        type=str,
        default=str(ODDS_NORMALIZED_DIR / "odds_canonical_matchups.csv"),
        help="Output file for canonicalized matchup rows.",
    )
    parser.add_argument(
        "--output-teams",
        type=str,
        default=str(ODDS_NORMALIZED_DIR / "odds_team_rows_canonical.csv"),
        help="Output file for team-level rows (two rows per matchup).",
    )
    parser.add_argument(
        "--tourney-start",
        type=str,
        help="Optional March Madness start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--tourney-end",
        type=str,
        help="Optional March Madness end date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--unmatched-output",
        type=str,
        help="Optional CSV to write unresolved team names and counts.",
    )
    parser.add_argument(
        "--prefer",
        type=str,
        choices=["earliest", "latest"],
        default="earliest",
        help=(
            "When duplicate event/book rows are found with different timestamps,"
            " prefer the 'earliest' (opening) or 'latest' (closing) snapshot."
            " Default: earliest"
        ),
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    input_path = Path(args.input) if args.input else None

    input_files = _iter_input_files(input_path, input_dir)
    if not input_files:
        print(f"[ERROR] No input CSV files found in {input_dir}")
        return 1

    resolver = ProductionTeamResolver()

    tourney_window = None
    if args.tourney_start or args.tourney_end:
        if not args.tourney_start or not args.tourney_end:
            print("[ERROR] Provide both --tourney-start and --tourney-end.")
            return 1
        try:
            start = datetime.strptime(args.tourney_start, "%Y-%m-%d").date()
            end = datetime.strptime(args.tourney_end, "%Y-%m-%d").date()
            tourney_window = (start, end)
        except ValueError:
            print("[ERROR] Invalid tourney date format (expected YYYY-MM-DD).")
            return 1

    stats = {
        "files_processed": 0,
        "rows_seen": 0,
        "rows_matched": 0,
        "rows_unmatched": 0,
        "duplicates_removed": 0,
    }
    unmatched_counts: Dict[str, int] = defaultdict(int)

    deduped: Dict[str, Tuple[Optional[datetime], Dict[str, str]]] = {}

    for csv_file in input_files:
        stats["files_processed"] += 1
        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats["rows_seen"] += 1

                    normalized, unresolved = _normalize_matchup_row(
                        row, resolver, tourney_window=tourney_window
                    )
                    if unresolved:
                        stats["rows_unmatched"] += 1
                        for team in unresolved:
                            if team:
                                unmatched_counts[team] += 1
                        continue

                    if not normalized:
                        stats["rows_unmatched"] += 1
                        continue

                    key = _dedupe_key(normalized)
                    ts = _parse_timestamp(normalized.get("timestamp", ""))

                    existing = deduped.get(key)
                    if not existing:
                        deduped[key] = (ts, normalized)
                        stats["rows_matched"] += 1
                        continue

                    stats["duplicates_removed"] += 1
                    existing_ts, existing_row = existing
                    prefer_incoming = False
                    if ts and existing_ts:
                        if args.prefer == "earliest":
                            prefer_incoming = ts < existing_ts
                        else:  # latest
                            prefer_incoming = ts > existing_ts
                    elif ts and not existing_ts:
                        # If existing has no timestamp, take the incoming regardless of preference
                        prefer_incoming = True

                    merged_row = _merge_rows(existing_row, normalized, prefer_incoming)
                    merged_ts = existing_ts
                    if prefer_incoming:
                        merged_ts = ts

                    deduped[key] = (merged_ts, merged_row)

        except Exception as exc:
            print(f"[WARN] Failed processing {csv_file}: {exc}")

    matchup_rows = [row for _ts, row in deduped.values()]
    matchup_rows.sort(key=lambda r: r.get("commence_time", ""))

    team_rows: List[Dict[str, str]] = []
    for matchup in matchup_rows:
        team_rows.extend(_matchup_to_team_rows(matchup))

    _write_csv(Path(args.output_matchups), MATCHUP_COLUMNS, matchup_rows)
    _write_csv(Path(args.output_teams), TEAM_COLUMNS, team_rows)

    print("=" * 72)
    print("HISTORICAL ODDS CANONICALIZATION SUMMARY")
    print("=" * 72)
    print(f"Files processed:     {stats['files_processed']}")
    print(f"Rows seen:           {stats['rows_seen']:,}")
    print(f"Rows matched:        {stats['rows_matched']:,}")
    print(f"Rows unmatched:      {stats['rows_unmatched']:,}")
    print(f"Duplicates removed:  {stats['duplicates_removed']:,}")
    print(f"Matchups output:     {len(matchup_rows):,}")
    print(f"Team rows output:    {len(team_rows):,}")

    if unmatched_counts:
        top_unmatched = sorted(unmatched_counts.items(), key=lambda x: -x[1])[:20]
        print("\nTop unresolved teams:")
        for team, count in top_unmatched:
            print(f"  {team}: {count}")

        if args.unmatched_output:
            unmatched_path = Path(args.unmatched_output)
            rows = [{"team": team, "count": count} for team, count in sorted(unmatched_counts.items())]
            _write_csv(unmatched_path, ["team", "count"], rows)
            print(f"\nUnmatched report: {unmatched_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
