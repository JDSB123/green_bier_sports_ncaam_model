"""Canonical data window for backtesting and ingestion.

The canonical window is 2023-24 season onward (season 2024+).
All historical references must stay within this window.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, List

# NCAA season naming: season 2024 == 2023-24 (Nov 2023 through Apr 2024).
CANONICAL_START_SEASON = 2024
CANONICAL_START_DATE = date(2023, 11, 1)


def season_from_date(value: date) -> int:
    """Map a calendar date to NCAA season year."""
    return value.year + 1 if value.month >= 11 else value.year


def current_season(today: date | None = None) -> int:
    """Return current NCAA season year based on today's date."""
    return season_from_date(today or date.today())


def default_backtest_seasons(today: date | None = None) -> List[int]:
    """Return canonical seasons from the start window through current season."""
    end = current_season(today)
    return list(range(CANONICAL_START_SEASON, end + 1))


def enforce_min_season(seasons: Iterable[int]) -> List[int]:
    """Validate that all seasons are within the canonical window."""
    season_list = list(seasons)
    invalid = sorted({s for s in season_list if s < CANONICAL_START_SEASON})
    if invalid:
        raise ValueError(
            f"Seasons before {CANONICAL_START_SEASON} are out of scope: {invalid}"
        )
    return season_list
