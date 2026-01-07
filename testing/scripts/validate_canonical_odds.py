#!/usr/bin/env python3
"""
Validate canonicalized historical odds for accuracy and consistency.

Checks:
- All teams resolve to canonical names
- Canonical fields match resolver output
- Deduped matchup keys are unique and complete
- Team rows align with matchup rows (home/away, spread sign, totals)
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"

sys.path.insert(0, str(ROOT_DIR / "testing"))

from production_parity.team_resolver import ProductionTeamResolver

MATCHUP_REQUIRED = {
    "event_id",
    "commence_time",
    "home_team",
    "away_team",
    "home_team_canonical",
    "away_team_canonical",
    "bookmaker",
    "spread",
    "total",
    "h1_spread",
    "h1_total",
    "is_march_madness",
    "timestamp",
    "game_date",
    "season",
}

TEAM_REQUIRED = {
    "event_id",
    "commence_time",
    "game_date",
    "season",
    "bookmaker",
    "team",
    "team_canonical",
    "opponent",
    "opponent_canonical",
    "is_home",
    "spread",
    "team_spread",
    "total",
    "h1_spread",
    "team_h1_spread",
    "h1_total",
    "is_march_madness",
    "timestamp",
}


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
        except (TypeError, ValueError):
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
    return dt.year + 1 if dt.month >= 7 else dt.year


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


def _iter_raw_files(input_dir: Path) -> List[Path]:
    csv_files = sorted(input_dir.glob("*.csv"))
    exclude_prefixes = (
        "odds_consolidated_canonical",
        "odds_canonical_matchups",
        "odds_team_rows_canonical",
        "unmatched_teams",
    )
    filtered = []
    for path in csv_files:
        if path.name.startswith(exclude_prefixes):
            continue
        filtered.append(path)
    return filtered


def _matchup_key(
    event_id: str,
    home_canonical: str,
    away_canonical: str,
    game_date: str,
    bookmaker: str,
) -> str:
    if event_id:
        return f"event:{event_id}|book:{bookmaker}"
    return f"{home_canonical}|{away_canonical}|{game_date}|{bookmaker}"


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _validate_headers(path: Path, required: Set[str]) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [f"{path}: missing headers"]
        missing = [c for c in sorted(required) if c not in reader.fieldnames]
        if missing:
            return [f"{path}: missing columns {missing}"]
    return []


def _resolve_raw_input(
    input_files: Iterable[Path],
    resolver: ProductionTeamResolver,
) -> Tuple[Set[str], Dict[str, int], Dict[str, int], int]:
    resolved_keys: Set[str] = set()
    unmatched_counts: Dict[str, int] = defaultdict(int)
    stats = {
        "rows_seen": 0,
        "rows_resolved": 0,
        "rows_unresolved": 0,
    }

    for csv_file in input_files:
        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats["rows_seen"] += 1
                    home_team = (row.get("home_team") or "").strip()
                    away_team = (row.get("away_team") or "").strip()
                    if not home_team or not away_team:
                        stats["rows_unresolved"] += 1
                        if not home_team:
                            unmatched_counts["<missing_home>"] += 1
                        if not away_team:
                            unmatched_counts["<missing_away>"] += 1
                        continue

                    home_result = resolver.resolve(home_team)
                    away_result = resolver.resolve(away_team)
                    if not home_result.resolved or not away_result.resolved:
                        stats["rows_unresolved"] += 1
                        if not home_result.resolved:
                            unmatched_counts[home_team] += 1
                        if not away_result.resolved:
                            unmatched_counts[away_team] += 1
                        continue

                    commence_time = row.get("commence_time", "")
                    game_date = _game_date_from_commence(commence_time) or row.get("game_date", "")
                    event_id = (row.get("event_id") or "").strip()
                    bookmaker = (row.get("bookmaker") or "").strip()
                    if not game_date or not bookmaker:
                        stats["rows_unresolved"] += 1
                        if not game_date:
                            unmatched_counts["<missing_game_date>"] += 1
                        if not bookmaker:
                            unmatched_counts["<missing_bookmaker>"] += 1
                        continue

                    key = _matchup_key(
                        event_id=event_id,
                        home_canonical=home_result.canonical_name or "",
                        away_canonical=away_result.canonical_name or "",
                        game_date=game_date,
                        bookmaker=bookmaker,
                    )
                    resolved_keys.add(key)
                    stats["rows_resolved"] += 1

        except Exception as exc:
            unmatched_counts[f"<error:{csv_file.name}>"] += 1
            stats["rows_unresolved"] += 1

    return resolved_keys, unmatched_counts, stats, len(resolved_keys)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate canonical historical odds outputs."
    )
    parser.add_argument(
        "--matchups",
        type=str,
        default=str(DEFAULT_DIR / "odds_canonical_matchups.csv"),
        help="Canonical matchup CSV output to validate.",
    )
    parser.add_argument(
        "--teams",
        type=str,
        default=str(DEFAULT_DIR / "odds_team_rows_canonical.csv"),
        help="Canonical team rows CSV output to validate.",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(DEFAULT_DIR),
        help="Directory of raw odds CSV files used for canonicalization.",
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
        "--allow-unresolved",
        action="store_true",
        help="Do not fail validation if unresolved raw teams exist.",
    )

    args = parser.parse_args()
    matchups_path = Path(args.matchups)
    teams_path = Path(args.teams)
    raw_dir = Path(args.raw_dir)

    errors: List[str] = []
    warnings: List[str] = []

    if not matchups_path.exists():
        errors.append(f"Missing matchups file: {matchups_path}")
    if not teams_path.exists():
        errors.append(f"Missing team rows file: {teams_path}")
    if not raw_dir.exists():
        errors.append(f"Missing raw dir: {raw_dir}")

    if errors:
        for err in errors:
            print(f"[ERROR] {err}")
        return 1

    errors.extend(_validate_headers(matchups_path, MATCHUP_REQUIRED))
    errors.extend(_validate_headers(teams_path, TEAM_REQUIRED))

    resolver = ProductionTeamResolver()

    tourney_window = None
    if args.tourney_start or args.tourney_end:
        if not args.tourney_start or not args.tourney_end:
            errors.append("Provide both --tourney-start and --tourney-end.")
        else:
            try:
                start = datetime.strptime(args.tourney_start, "%Y-%m-%d").date()
                end = datetime.strptime(args.tourney_end, "%Y-%m-%d").date()
                tourney_window = (start, end)
            except ValueError:
                errors.append("Invalid tourney date format (expected YYYY-MM-DD).")

    if errors:
        for err in errors:
            print(f"[ERROR] {err}")
        return 1

    matchup_rows = _load_csv(matchups_path)
    team_rows = _load_csv(teams_path)

    matchup_by_key: Dict[str, Dict[str, str]] = {}
    matchup_by_event: Dict[str, Tuple[str, str]] = {}
    matchup_duplicates = 0
    mismatch_count = 0
    march_madness_mismatch = 0
    season_mismatch = 0

    for row in matchup_rows:
        home_team = (row.get("home_team") or "").strip()
        away_team = (row.get("away_team") or "").strip()
        home_canonical = (row.get("home_team_canonical") or "").strip()
        away_canonical = (row.get("away_team_canonical") or "").strip()
        event_id = (row.get("event_id") or "").strip()
        bookmaker = (row.get("bookmaker") or "").strip()
        commence_time = row.get("commence_time", "")
        game_date = row.get("game_date", "")

        if not home_canonical or not away_canonical:
            mismatch_count += 1
            continue

        resolved_home = resolver.resolve(home_team).canonical_name
        resolved_away = resolver.resolve(away_team).canonical_name
        if resolved_home != home_canonical or resolved_away != away_canonical:
            mismatch_count += 1

        computed_date = _game_date_from_commence(commence_time)
        if computed_date and computed_date != game_date:
            mismatch_count += 1

        expected_season = _season_from_commence(commence_time)
        if str(expected_season) != str(row.get("season", "")):
            season_mismatch += 1

        expected_mm = _detect_march_madness(commence_time, tourney_window=tourney_window)
        is_mm = str(row.get("is_march_madness", "")).strip().lower() in ("true", "1", "yes")
        if expected_mm != is_mm:
            march_madness_mismatch += 1

        key = _matchup_key(event_id, home_canonical, away_canonical, game_date, bookmaker)
        if key in matchup_by_key:
            matchup_duplicates += 1
        else:
            matchup_by_key[key] = row

        if event_id:
            existing = matchup_by_event.get(event_id)
            if existing and existing != (home_canonical, away_canonical):
                mismatch_count += 1
            else:
                matchup_by_event[event_id] = (home_canonical, away_canonical)

    team_by_key: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    team_duplicates = 0
    team_mismatch = 0

    for row in team_rows:
        event_id = (row.get("event_id") or "").strip()
        bookmaker = (row.get("bookmaker") or "").strip()
        game_date = row.get("game_date", "")
        is_home = row.get("is_home", "")
        team_canonical = (row.get("team_canonical") or "").strip()
        opponent_canonical = (row.get("opponent_canonical") or "").strip()

        if is_home not in ("0", "1"):
            team_mismatch += 1
            continue

        if not team_canonical or not opponent_canonical:
            team_mismatch += 1
            continue

        if is_home == "1":
            home_canonical = team_canonical
            away_canonical = opponent_canonical
        else:
            home_canonical = opponent_canonical
            away_canonical = team_canonical

        key = _matchup_key(event_id, home_canonical, away_canonical, game_date, bookmaker)
        team_by_key[key].append(row)

    for key, rows in team_by_key.items():
        if len(rows) != 2:
            team_mismatch += 1
            continue

        seen_home = set(r.get("is_home", "") for r in rows)
        if seen_home != {"0", "1"}:
            team_mismatch += 1
            continue

        matchup = matchup_by_key.get(key)
        if not matchup:
            team_mismatch += 1
            continue

        spread = _to_float(matchup.get("spread"))
        h1_spread = _to_float(matchup.get("h1_spread"))
        total = matchup.get("total", "")
        h1_total = matchup.get("h1_total", "")

        for row in rows:
            is_home = row.get("is_home") == "1"
            expected_team = matchup.get("home_team_canonical") if is_home else matchup.get("away_team_canonical")
            expected_opp = matchup.get("away_team_canonical") if is_home else matchup.get("home_team_canonical")

            if row.get("team_canonical") != expected_team:
                team_mismatch += 1
            if row.get("opponent_canonical") != expected_opp:
                team_mismatch += 1

            if spread is not None:
                team_spread = _to_float(row.get("team_spread"))
                expected_spread = spread if is_home else -spread
                if team_spread is None or abs(team_spread - expected_spread) > 1e-6:
                    team_mismatch += 1

            if h1_spread is not None:
                team_h1_spread = _to_float(row.get("team_h1_spread"))
                expected_h1_spread = h1_spread if is_home else -h1_spread
                if team_h1_spread is None or abs(team_h1_spread - expected_h1_spread) > 1e-6:
                    team_mismatch += 1

            if total != row.get("total"):
                team_mismatch += 1
            if h1_total != row.get("h1_total"):
                team_mismatch += 1

    raw_files = _iter_raw_files(raw_dir)
    raw_keys, unmatched_counts, raw_stats, raw_key_count = _resolve_raw_input(raw_files, resolver)

    missing_from_output = raw_keys - set(matchup_by_key.keys())
    extra_in_output = set(matchup_by_key.keys()) - raw_keys

    if mismatch_count:
        errors.append(f"Canonical mismatches in matchup rows: {mismatch_count}")
    if season_mismatch:
        errors.append(f"Season mismatches in matchup rows: {season_mismatch}")
    if march_madness_mismatch:
        errors.append(f"March Madness flag mismatches: {march_madness_mismatch}")
    if matchup_duplicates:
        errors.append(f"Duplicate matchup keys: {matchup_duplicates}")
    if team_mismatch:
        errors.append(f"Team row mismatches: {team_mismatch}")
    if len(team_rows) != len(matchup_by_key) * 2:
        errors.append(
            f"Team rows count mismatch: {len(team_rows)} rows vs {len(matchup_by_key) * 2} expected"
        )
    if missing_from_output:
        errors.append(f"Missing matchups in output: {len(missing_from_output)}")
    if extra_in_output:
        warnings.append(f"Extra matchups in output not found in raw input: {len(extra_in_output)}")

    unresolved_total = sum(unmatched_counts.values())
    if unresolved_total and not args.allow_unresolved:
        errors.append(f"Unresolved raw team names: {unresolved_total}")

    print("=" * 72)
    print("HISTORICAL ODDS VALIDATION SUMMARY")
    print("=" * 72)
    print(f"Matchup rows:         {len(matchup_rows):,}")
    print(f"Team rows:            {len(team_rows):,}")
    print(f"Raw rows seen:        {raw_stats['rows_seen']:,}")
    print(f"Raw rows resolved:    {raw_stats['rows_resolved']:,}")
    print(f"Raw rows unresolved:  {raw_stats['rows_unresolved']:,}")
    print(f"Matchup keys resolved:{raw_key_count:,}")

    if unresolved_total:
        top_unmatched = sorted(unmatched_counts.items(), key=lambda x: -x[1])[:20]
        print("\nTop unresolved raw teams:")
        for team, count in top_unmatched:
            print(f"  {team}: {count}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nValidation passed with no blocking issues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
