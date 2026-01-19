"""Utilities for working with Kaggle March Madness historical scores.

The implementation is intentionally standalone so the testing branch can run
legacy backtests without touching the production service code. Only light
pandas usage is required.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "kaggle"

COMPACT_RESULTS = DATA_DIR / "MRegularSeasonCompactResults.csv"
DETAILED_RESULTS = DATA_DIR / "MRegularSeasonDetailedResults.csv"
TEAM_MAP_FILE = DATA_DIR / "MTeams.csv"
TEAM_SPELLINGS_FILE = DATA_DIR / "MTeamSpellings.csv"
SEASONS_FILE = DATA_DIR / "MSeasons.csv"

GameKey = tuple[str, str, str]


class KaggleDataNotFoundError(RuntimeError):
    """Raised when the expected Kaggle CSV files are unavailable."""


@dataclass
class GameRecord:
    away_team: str
    home_team: str
    away_score: int
    home_score: int
    commence_time: datetime
    neutral: bool
    num_ot: int
    source: str = "kaggle"

    def as_dict(self) -> dict[str, object]:
        return {
            "away_team": self.away_team,
            "home_team": self.home_team,
            "away_score": self.away_score,
            "home_score": self.home_score,
            "commence_time": self.commence_time,
            "neutral": self.neutral,
            "num_ot": self.num_ot,
            "source": self.source,
        }


def _require_files(*files: Path) -> None:
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise KaggleDataNotFoundError(
            "Missing Kaggle dataset files: " + ", ".join(missing)
        )


def _load_team_names() -> dict[int, str]:
    _require_files(TEAM_MAP_FILE)
    frame = pd.read_csv(TEAM_MAP_FILE)
    if "TeamID" not in frame or "TeamName" not in frame:
        raise ValueError("MTeams.csv is missing expected columns TeamID/TeamName")
    return dict(zip(frame["TeamID"], frame["TeamName"], strict=False))


def _load_spellings() -> dict[int, list[str]]:
    if not TEAM_SPELLINGS_FILE.exists():
        return {}
    frame = pd.read_csv(TEAM_SPELLINGS_FILE)
    if "TeamID" not in frame or "TeamNameSpelling" not in frame:
        return {}
    return {
        team_id: group["TeamNameSpelling"].dropna().tolist()
        for team_id, group in frame.groupby("TeamID")
    }


def _load_season_start(season: int) -> date:
    _require_files(SEASONS_FILE)
    frame = pd.read_csv(SEASONS_FILE)
    if "Season" not in frame or "DayZero" not in frame:
        raise ValueError("MSeasons.csv missing Season/DayZero columns")

    match = frame.loc[frame["Season"] == season]
    if match.empty:
        raise ValueError(f"Season {season} not present in MSeasons.csv")

    day_zero = match.iloc[0]["DayZero"]
    return datetime.strptime(day_zero, "%Y-%m-%d").date()


def _day_to_date(season: int, day_num: int) -> date:
    start = _load_season_start(season)
    return start + timedelta(days=int(day_num))


def _winner_home_mapping(row: pd.Series) -> tuple[str, str, bool]:
    wloc = (row.get("WLoc") or "").upper()
    winner = str(row["WTeamID"])
    loser = str(row["LTeamID"])

    if wloc == "H":
        return winner, loser, False
    if wloc == "A":
        return loser, winner, False
    # Neutral site defaults winner to "home" for deterministic keying.
    return winner, loser, True


def load_kaggle_scores(
    season: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[GameKey, GameRecord]:
    """Load regular-season scores from Kaggle for the requested season."""
    _require_files(COMPACT_RESULTS, TEAM_MAP_FILE, SEASONS_FILE)

    teams = _load_team_names()
    results = pd.read_csv(COMPACT_RESULTS)

    if "Season" not in results or "DayNum" not in results:
        raise ValueError("Compact results file missing Season/DayNum columns")

    season_df = results.loc[results["Season"] == season].copy()
    if season_df.empty:
        return {}

    records: dict[GameKey, GameRecord] = {}

    for _, row in season_df.iterrows():
        home_id, away_id, neutral = _winner_home_mapping(row)
        home_name = teams.get(int(home_id))
        away_name = teams.get(int(away_id))

        if not home_name or not away_name:
            # Skip if team mapping is missing; legacy datasets sometimes exclude
            # small schools. Downstream tooling handles sparse gaps.
            continue

        game_day = _day_to_date(season, int(row["DayNum"]))
        commence = datetime.combine(game_day, datetime.min.time(), tzinfo=UTC)

        # Determine score assignment relative to the mapped home/away IDs.
        winner_score = int(row["WScore"])
        loser_score = int(row["LScore"])
        if str(row["WTeamID"]) == home_id:
            home_score, away_score = winner_score, loser_score
        else:
            home_score, away_score = loser_score, winner_score

        key = (away_name, home_name, game_day.isoformat())
        records[key] = GameRecord(
            away_team=away_name,
            home_team=home_name,
            away_score=away_score,
            home_score=home_score,
            commence_time=commence,
            neutral=neutral,
            num_ot=int(row.get("NumOT", 0)),
        )

    if start_date or end_date:
        to_delete: list[GameKey] = []
        for key, record in records.items():
            game_date = record.commence_time.date()
            if start_date and game_date < start_date or end_date and game_date > end_date:
                to_delete.append(key)
        for key in to_delete:
            records.pop(key, None)

    return records


def build_score_index(
    season: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, dict[str, object]]:
    """Flatten records into a single dictionary keyed by ISO strings."""
    data = load_kaggle_scores(season, start_date, end_date)
    index: dict[str, dict[str, object]] = {}
    for key, record in data.items():
        away, home, iso = key
        index_key = f"{iso}:{away} at {home}"
        index[index_key] = record.as_dict()
    return index


# ---------------------------------------------------------------------------
# CLI helpers


def _render_sample(records: dict[GameKey, GameRecord], sample_size: int) -> None:
    if not records:
        print("No games loaded for requested filters.")
        return

    print(f"Loaded {len(records)} games.")
    print("Sample:")
    for key in list(records.keys())[:sample_size]:
        record = records[key]
        print(
            f"  {record.away_team} {record.away_score} @ "
            f"{record.home_team} {record.home_score}"
            f"  ({record.commence_time.date()} neutral={record.neutral})"
        )


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect Kaggle historical scores (testing branch only)",
    )
    parser.add_argument("--season", type=int, required=True, help="Season year")
    parser.add_argument("--start", type=str, help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="Inclusive end date YYYY-MM-DD")
    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="Number of sample games to display",
    )

    args = parser.parse_args(argv)

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None

    records = load_kaggle_scores(args.season, start, end)
    _render_sample(records, max(1, args.sample))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(_cli())
