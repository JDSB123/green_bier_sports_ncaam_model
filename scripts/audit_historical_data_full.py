#!/usr/bin/env python3
"""Deep audit of historical backtest data for duplicates and drift (Azure-only)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from typing import Dict, List, Tuple

import pandas as pd

from testing.azure_data_reader import AzureDataReader


def _normalize_alias(alias: str) -> str:
    alias = alias.lower().strip()
    alias = re.sub(r"[^a-z0-9]+", " ", alias)
    return re.sub(r"\s+", " ", alias).strip()


def _dup_stats(df: pd.DataFrame, subset: List[str]) -> Dict[str, object]:
    dup_mask = df.duplicated(subset=subset, keep=False)
    dup_count = int(dup_mask.sum())
    sample = (
        df.loc[dup_mask, subset]
        .drop_duplicates()
        .head(5)
        .to_dict(orient="records")
    )
    return {"count": dup_count, "sample": sample}


def _date_range(df: pd.DataFrame, column: str) -> Tuple[str, str]:
    series = pd.to_datetime(df[column], errors="coerce").dropna()
    if series.empty:
        return ("", "")
    return (str(series.min().date()), str(series.max().date()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit historical data integrity.")
    parser.add_argument(
        "--azure-container",
        default="ncaam-historical-data",
        help="Azure canonical container name.",
    )
    parser.add_argument(
        "--cutoff-days",
        type=int,
        default=3,
        help="Days to subtract from today for leakage cutoff checks.",
    )
    parser.add_argument(
        "--output",
        default="manifests/historical_data_audit.json",
        help="Output JSON report path.",
    )
    args = parser.parse_args()

    cutoff_date = date.today() - timedelta(days=args.cutoff_days)
    report: Dict[str, object] = {"cutoff_date": str(cutoff_date)}

    reader = AzureDataReader(container_name=args.azure_container)

    # Azure inventory snapshot (names only, no local comparison).
    all_files = reader.list_files()
    report["azure_inventory"] = {
        "azure_total": len(all_files),
        "sample_files": all_files[:20],
    }

    # Data audits (Azure-only).
    scores_fg = reader.read_csv(
        "scores/fg/games_all.csv",
        usecols=["game_id", "date", "home_team", "away_team"],
    )
    scores_h1 = reader.read_csv(
        "scores/h1/h1_games_all.csv",
        usecols=["game_id", "date", "home_team", "away_team"],
    )
    odds = reader.read_csv(
        "odds/normalized/odds_consolidated_canonical.csv",
        usecols=[
            "event_id",
            "game_date",
            "home_team_canonical",
            "away_team_canonical",
            "bookmaker",
            "spread",
            "total",
            "h1_spread",
            "h1_total",
        ],
    )
    master = reader.read_csv(
        "backtest_datasets/backtest_master.csv",
        usecols=["game_id", "game_date", "home_team", "away_team", "season"],
    )

    report["scores_fg"] = {
        "rows": int(len(scores_fg)),
        "date_range": _date_range(scores_fg, "date"),
        "dup_game_id": _dup_stats(scores_fg, ["game_id"]),
        "dup_matchup": _dup_stats(scores_fg, ["date", "home_team", "away_team"]),
    }
    report["scores_h1"] = {
        "rows": int(len(scores_h1)),
        "date_range": _date_range(scores_h1, "date"),
        "dup_game_id": _dup_stats(scores_h1, ["game_id"]),
        "dup_matchup": _dup_stats(scores_h1, ["date", "home_team", "away_team"]),
    }
    report["odds_consolidated"] = {
        "rows": int(len(odds)),
        "date_range": _date_range(odds, "game_date"),
        "dup_event_id": _dup_stats(odds, ["event_id"]),
        "dup_event_book": _dup_stats(
            odds,
            [
                "event_id",
                "bookmaker",
                "spread",
                "total",
                "h1_spread",
                "h1_total",
            ],
        ),
    }
    report["backtest_master"] = {
        "rows": int(len(master)),
        "date_range": _date_range(master, "game_date"),
        "dup_game_id": _dup_stats(master, ["game_id"]),
        "dup_matchup": _dup_stats(master, ["game_date", "home_team", "away_team"]),
    }

    # Leakage cutoff checks
    for key, column in [
        ("scores_fg", "date"),
        ("scores_h1", "date"),
        ("odds_consolidated", "game_date"),
        ("backtest_master", "game_date"),
    ]:
        max_date = report[key]["date_range"][1]
        if max_date:
            report[key]["cutoff_ok"] = max_date <= str(cutoff_date)

    # Alias collisions
    alias_data = reader.read_json("backtest_datasets/team_aliases_db.json")
    norm_map: Dict[str, str] = {}
    collisions: List[Dict[str, str]] = []
    for alias, canonical in alias_data.items():
        norm = _normalize_alias(alias)
        if norm in norm_map and norm_map[norm] != canonical:
            collisions.append(
                {"alias": alias, "canonical": canonical, "canonical_existing": norm_map[norm]}
            )
        else:
            norm_map[norm] = canonical
    report["alias_db"] = {
        "aliases": len(alias_data),
        "normalized_collisions": collisions[:20],
    }

    report["legacy_paths"] = {
        "canonicalized_present": bool(reader.list_files("canonicalized/")),
        "odds_canonical_present": bool(reader.list_files("odds/canonical/")),
    }

    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
