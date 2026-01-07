#!/usr/bin/env python3
"""Audit historical data coverage and schemas by endpoint/season."""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_ROOT = Path(
    os.environ.get("HISTORICAL_DATA_ROOT", ROOT_DIR / "ncaam_historical_data_local")
).resolve()

ODDS_RAW_DIR = Path(os.environ.get("HISTORICAL_ODDS_RAW_DIR", HISTORICAL_ROOT / "odds" / "raw")).resolve()
ODDS_NORMALIZED_DIR = Path(
    os.environ.get("HISTORICAL_ODDS_NORMALIZED_DIR", HISTORICAL_ROOT / "odds" / "normalized")
).resolve()
SCORES_FG_DIR = Path(os.environ.get("HISTORICAL_SCORES_FG_DIR", HISTORICAL_ROOT / "scores" / "fg")).resolve()
SCORES_H1_DIR = Path(os.environ.get("HISTORICAL_SCORES_H1_DIR", HISTORICAL_ROOT / "scores" / "h1")).resolve()
RATINGS_DIR = Path(os.environ.get("HISTORICAL_RATINGS_DIR", HISTORICAL_ROOT / "ratings" / "barttorvik")).resolve()

SCHEMAS_DIR = HISTORICAL_ROOT / "schemas"
MANIFESTS_DIR = HISTORICAL_ROOT / "manifests"


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _season_from_date(dt: datetime) -> int:
    return dt.year + 1 if dt.month >= 11 else dt.year


def _read_csv_header(path: Path) -> List[str]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader, [])


def _audit_csv_rows(
    path: Path,
    date_field: str,
    season_field: Optional[str] = None,
    h1_fields: Optional[Iterable[str]] = None,
    spread_field: Optional[str] = None,
    total_field: Optional[str] = None,
    price_fields: Optional[Iterable[str]] = None,
) -> Dict[int, Dict[str, Any]]:
    stats: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
        "rows": 0,
        "min_date": None,
        "max_date": None,
        "h1_rows": 0,
        "missing_spread": 0,
        "missing_total": 0,
        "has_prices": False,
    })

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = None
            if season_field and row.get(season_field):
                try:
                    season = int(row[season_field])
                except ValueError:
                    season = 0
            else:
                dt = _parse_date(row.get(date_field, ""))
                season = _season_from_date(dt) if dt else 0

            bucket = stats[season]
            bucket["rows"] += 1

            if dt is None:
                dt = _parse_date(row.get(date_field, ""))

            if dt:
                bucket["min_date"] = dt if bucket["min_date"] is None else min(bucket["min_date"], dt)
                bucket["max_date"] = dt if bucket["max_date"] is None else max(bucket["max_date"], dt)

            if spread_field and not row.get(spread_field):
                bucket["missing_spread"] += 1
            if total_field and not row.get(total_field):
                bucket["missing_total"] += 1

            if h1_fields:
                if any(row.get(field) for field in h1_fields):
                    bucket["h1_rows"] += 1

            if price_fields and not bucket["has_prices"]:
                if any(row.get(field) for field in price_fields):
                    bucket["has_prices"] = True

    return stats


def _emit_audit_rows(
    rows: List[Dict[str, Any]],
    endpoint: str,
    dataset: str,
    stats: Dict[int, Dict[str, Any]],
    source_file: Optional[str] = None,
) -> None:
    for season, bucket in stats.items():
        rows.append({
            "endpoint": endpoint,
            "dataset": dataset,
            "season": season,
            "rows": bucket["rows"],
            "min_date": bucket["min_date"].date().isoformat() if bucket["min_date"] else "",
            "max_date": bucket["max_date"].date().isoformat() if bucket["max_date"] else "",
            "h1_rows": bucket["h1_rows"],
            "missing_spread": bucket["missing_spread"],
            "missing_total": bucket["missing_total"],
            "has_prices": bucket["has_prices"],
            "source_file": source_file or "",
        })


def audit() -> None:
    audit_rows: List[Dict[str, Any]] = []

    # Odds raw
    if ODDS_RAW_DIR.exists():
        for path in sorted(ODDS_RAW_DIR.glob("*.csv")):
            stats = _audit_csv_rows(
                path,
                date_field="commence_time",
                season_field=None,
                h1_fields=("h1_spread", "h1_total"),
                spread_field="spread",
                total_field="total",
                price_fields=(
                    "spread_price",
                    "spread_home_price",
                    "spread_away_price",
                    "total_over_price",
                    "total_under_price",
                    "h1_spread_price",
                    "h1_spread_home_price",
                    "h1_spread_away_price",
                    "h1_total_over_price",
                    "h1_total_under_price",
                ),
            )
            _emit_audit_rows(
                audit_rows,
                endpoint="odds_api/historical/events+odds",
                dataset="odds_raw",
                stats=stats,
                source_file=path.name,
            )

    # Odds normalized
    if ODDS_NORMALIZED_DIR.exists():
        for name in ("odds_canonical_matchups.csv", "odds_team_rows_canonical.csv"):
            path = ODDS_NORMALIZED_DIR / name
            if not path.exists():
                continue
            stats = _audit_csv_rows(
                path,
                date_field="commence_time",
                season_field="season",
                h1_fields=("h1_spread", "h1_total"),
                spread_field="spread",
                total_field="total",
                price_fields=(
                    "spread_price",
                    "spread_home_price",
                    "spread_away_price",
                    "total_over_price",
                    "total_under_price",
                    "h1_spread_price",
                    "h1_spread_home_price",
                    "h1_spread_away_price",
                    "h1_total_over_price",
                    "h1_total_under_price",
                ),
            )
            _emit_audit_rows(
                audit_rows,
                endpoint="odds_api/historical/events+odds",
                dataset=f"odds_normalized/{name}",
                stats=stats,
            )

    # Scores (full game)
    if SCORES_FG_DIR.exists():
        for path in sorted(SCORES_FG_DIR.glob("games_*.csv")):
            stats = _audit_csv_rows(
                path,
                date_field="date",
                season_field=None,
            )
            _emit_audit_rows(
                audit_rows,
                endpoint="espn/scoreboard",
                dataset="scores_fg",
                stats=stats,
                source_file=path.name,
            )

    # Scores (1H)
    h1_path = SCORES_H1_DIR / "h1_games_all.csv"
    if h1_path.exists():
        stats = _audit_csv_rows(
            h1_path,
            date_field="date",
            season_field=None,
            h1_fields=("home_h1", "away_h1"),
        )
        _emit_audit_rows(
            audit_rows,
            endpoint="espn/summary",
            dataset="scores_h1",
            stats=stats,
            source_file=h1_path.name,
        )

    # Ratings (Barttorvik)
    if RATINGS_DIR.exists():
        for path in sorted(RATINGS_DIR.glob("barttorvik_*.json")):
            try:
                season = int(path.stem.split("_")[-1])
            except ValueError:
                season = 0
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = len(data) if isinstance(data, list) else 0
            audit_rows.append({
                "endpoint": "barttorvik/team_results",
                "dataset": "ratings_barttorvik",
                "season": season,
                "rows": rows,
                "min_date": "",
                "max_date": "",
                "h1_rows": "",
                "missing_spread": "",
                "missing_total": "",
                "has_prices": "",
                "source_file": path.name,
            })

    # Write audit manifest
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = MANIFESTS_DIR / "season_endpoint_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "endpoint",
            "dataset",
            "season",
            "rows",
            "min_date",
            "max_date",
            "h1_rows",
            "missing_spread",
            "missing_total",
            "has_prices",
            "source_file",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(audit_rows, key=lambda r: (r["endpoint"], r["dataset"], str(r["season"]))))

    # Schemas manifest
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    schemas: Dict[str, Any] = {}

    # Odds raw schema (first CSV if present)
    raw_files = sorted(ODDS_RAW_DIR.glob("*.csv")) if ODDS_RAW_DIR.exists() else []
    if raw_files:
        schemas["odds_raw"] = {
            "path": str(raw_files[0].relative_to(HISTORICAL_ROOT)),
            "columns": _read_csv_header(raw_files[0]),
        }

    # Odds normalized schemas
    for name in ("odds_canonical_matchups.csv", "odds_team_rows_canonical.csv"):
        path = ODDS_NORMALIZED_DIR / name
        if path.exists():
            schemas[f"odds_normalized/{name}"] = {
                "path": str(path.relative_to(HISTORICAL_ROOT)),
                "columns": _read_csv_header(path),
            }

    # Scores schemas
    fg_files = sorted(SCORES_FG_DIR.glob("games_*.csv")) if SCORES_FG_DIR.exists() else []
    if fg_files:
        schemas["scores_fg"] = {
            "path": str(fg_files[0].relative_to(HISTORICAL_ROOT)),
            "columns": _read_csv_header(fg_files[0]),
        }

    h1_file = SCORES_H1_DIR / "h1_games_all.csv"
    if h1_file.exists():
        schemas["scores_h1"] = {
            "path": str(h1_file.relative_to(HISTORICAL_ROOT)),
            "columns": _read_csv_header(h1_file),
        }

    # Barttorvik schema
    ratings_files = sorted(RATINGS_DIR.glob("barttorvik_*.json")) if RATINGS_DIR.exists() else []
    if ratings_files:
        sample = json.loads(ratings_files[0].read_text(encoding="utf-8"))
        sample_row = sample[0] if isinstance(sample, list) and sample else None
        schemas["ratings_barttorvik"] = {
            "path": str(ratings_files[0].relative_to(HISTORICAL_ROOT)),
            "format": "list",
            "sample_length": len(sample_row) if isinstance(sample_row, list) else None,
            "sample_row": sample_row,
            "notes": "Barttorvik historical JSON is an array of arrays; field names are not embedded.",
        }

    schemas_path = SCHEMAS_DIR / "fields_manifest.json"
    schemas_path.write_text(json.dumps(schemas, indent=2))

    print(f"[OK] Wrote audit to {audit_path}")
    print(f"[OK] Wrote schemas to {schemas_path}")


if __name__ == "__main__":
    audit()
