"""
Unified Schedule Sources - ESPN + Basketball API (Cross-Validation)

Fetches full season schedule from multiple sources for data integrity.
Both sources are fetched in parallel and cross-validated, not used as fallbacks.

ESPN API: Free, no key required
Basketball API: Requires BASKETBALL_API_KEY

v33.11.0: Part of unified orchestrator architecture.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

try:
    import requests
except ImportError:
    requests = None


@dataclass
class ScheduledGame:
    """Normalized game from any schedule source."""

    # Identifiers
    external_id: str
    source: str  # 'espn' or 'basketball_api'

    # Teams (as provided by source - needs resolution)
    home_team_raw: str
    away_team_raw: str

    # Resolved names (populated after team matching)
    home_team: str | None = None
    away_team: str | None = None

    # Game info
    game_date: date = field(default_factory=date.today)
    game_time: datetime | None = None
    venue: str | None = None
    is_neutral: bool = False

    # Status
    status: str = 'scheduled'  # scheduled, in_progress, final, postponed, cancelled

    # Scores (if final)
    home_score: int | None = None
    away_score: int | None = None

    # Conference info
    home_conference: str | None = None
    away_conference: str | None = None


class ESPNScheduleClient:
    """
    ESPN API client for NCAAM schedule.

    ESPN's public API doesn't require authentication.
    Endpoint: https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard
    """

    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"

    def __init__(self):
        if requests is None:
            raise ImportError("requests library required")
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "GreenBierSports/1.0 NCAAM-Prediction-Model",
            "Accept": "application/json",
        })

    def get_schedule_for_date(self, target_date: date) -> list[ScheduledGame]:
        """Fetch schedule for a specific date."""
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/scoreboard"

        try:
            resp = self._session.get(url, params={"dates": date_str}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_scoreboard(data, target_date)
        except requests.RequestException as e:
            logger.warning("espn_schedule_fetch_failed", date=date_str, error=str(e))
            return []

    def get_season_schedule(self, season_year: int = 2025) -> list[ScheduledGame]:
        """
        Fetch full season schedule.

        ESPN doesn't have a single endpoint for full season, so we fetch by date range.
        Season runs roughly November 1 to April 10.

        Args:
            season_year: The year the season ENDS (e.g., 2025 for 2024-25 season)
        """
        games = []

        # Season start: November 1 of previous year
        # Season end: April 15 of season year (covers tournament)
        start_date = date(season_year - 1, 11, 1)
        end_date = date(season_year, 4, 15)

        # ESPN calendar endpoint gives us dates with games
        try:
            calendar_url = f"{self.BASE_URL}/scoreboard"
            resp = self._session.get(
                calendar_url,
                params={"dates": f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            # Get calendar info
            calendar = data.get("leagues", [{}])[0].get("calendar", [])

            # Extract dates that have games
            game_dates = []
            for entry in calendar:
                if isinstance(entry, dict):
                    date_str = entry.get("value", "")[:8]
                elif isinstance(entry, str):
                    date_str = entry[:8]
                else:
                    continue

                if date_str:
                    try:
                        game_dates.append(datetime.strptime(date_str, "%Y%m%d").date())
                    except ValueError:
                        continue

            logger.info("espn_season_dates_found", count=len(game_dates), season=season_year)

            # Fetch each date (in batches to be nice to API)
            for game_date in game_dates:
                day_games = self.get_schedule_for_date(game_date)
                games.extend(day_games)

        except requests.RequestException as e:
            logger.warning("espn_season_fetch_failed", season=season_year, error=str(e))

        return games

    def _parse_scoreboard(self, data: dict[str, Any], target_date: date) -> list[ScheduledGame]:
        """Parse ESPN scoreboard response."""
        games = []
        events = data.get("events", [])

        for event in events:
            try:
                game = self._parse_event(event, target_date)
                if game:
                    games.append(game)
            except Exception as e:
                logger.warning("espn_parse_event_failed", event_id=event.get("id"), error=str(e))
                continue

        return games

    def _parse_event(self, event: dict[str, Any], target_date: date) -> ScheduledGame | None:
        """Parse a single ESPN event."""
        event_id = str(event.get("id", ""))

        competitions = event.get("competitions", [])
        if not competitions:
            return None

        competition = competitions[0]
        competitors = competition.get("competitors", [])

        if len(competitors) < 2:
            return None

        # Find home and away
        home_team = None
        away_team = None
        home_score = None
        away_score = None

        for comp in competitors:
            team_data = comp.get("team", {})
            team_name = team_data.get("displayName") or team_data.get("name", "")
            is_home = comp.get("homeAway") == "home"
            score = comp.get("score")

            if is_home:
                home_team = team_name
                home_score = int(score) if score and score.isdigit() else None
            else:
                away_team = team_name
                away_score = int(score) if score and score.isdigit() else None

        if not home_team or not away_team:
            return None

        # Parse game time
        game_time = None
        date_str = event.get("date", "")
        if date_str:
            try:
                game_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Status
        status_data = event.get("status", {}).get("type", {})
        status_name = status_data.get("name", "STATUS_SCHEDULED")

        status_map = {
            "STATUS_SCHEDULED": "scheduled",
            "STATUS_IN_PROGRESS": "in_progress",
            "STATUS_FINAL": "final",
            "STATUS_POSTPONED": "postponed",
            "STATUS_CANCELED": "cancelled",
        }
        status = status_map.get(status_name, "scheduled")

        # Venue / neutral site
        venue = competition.get("venue", {}).get("fullName")
        is_neutral = competition.get("neutralSite", False)

        return ScheduledGame(
            external_id=f"espn:{event_id}",
            source="espn",
            home_team_raw=home_team,
            away_team_raw=away_team,
            game_date=target_date,
            game_time=game_time,
            venue=venue,
            is_neutral=is_neutral,
            status=status,
            home_score=home_score,
            away_score=away_score,
        )


class BasketballAPIScheduleClient:
    """
    Basketball API (api-sports.io) client for NCAAM schedule.

    Requires BASKETBALL_API_KEY environment variable.
    """

    BASE_URL = "https://v1.basketball.api-sports.io"
    NCAAM_LEAGUE_ID = 116  # NCAA Men's Basketball

    def __init__(self, api_key: str | None = None):
        if requests is None:
            raise ImportError("requests library required")

        self.api_key = api_key or os.environ.get("BASKETBALL_API_KEY", "")
        if not self.api_key:
            logger.warning("basketball_api_no_key", msg="BASKETBALL_API_KEY not set")

        self._session = requests.Session()
        self._session.headers.update({
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        })

    def get_schedule_for_date(self, target_date: date) -> list[ScheduledGame]:
        """Fetch schedule for a specific date."""
        if not self.api_key:
            return []

        date_str = target_date.strftime("%Y-%m-%d")
        url = f"{self.BASE_URL}/games"

        try:
            resp = self._session.get(
                url,
                params={"league": self.NCAAM_LEAGUE_ID, "date": date_str},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_games(data.get("response", []), target_date)
        except requests.RequestException as e:
            logger.warning("basketball_api_fetch_failed", date=date_str, error=str(e))
            return []

    def get_season_schedule(self, season_year: int = 2025) -> list[ScheduledGame]:
        """
        Fetch full season schedule.

        Basketball API uses season format like "2024-2025".
        """
        if not self.api_key:
            logger.warning("basketball_api_skipped", reason="no API key")
            return []

        season_str = f"{season_year - 1}-{season_year}"
        url = f"{self.BASE_URL}/games"

        try:
            resp = self._session.get(
                url,
                params={"league": self.NCAAM_LEAGUE_ID, "season": season_str},
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            games = self._parse_games(data.get("response", []))
            logger.info("basketball_api_season_fetched", season=season_str, games=len(games))
            return games
        except requests.RequestException as e:
            logger.warning("basketball_api_season_failed", season=season_str, error=str(e))
            return []

    def _parse_games(self, games_data: list[dict], default_date: date | None = None) -> list[ScheduledGame]:
        """Parse Basketball API games response."""
        games = []

        for game_data in games_data:
            try:
                game = self._parse_game(game_data, default_date)
                if game:
                    games.append(game)
            except Exception as e:
                logger.warning("basketball_api_parse_failed", game_id=game_data.get("id"), error=str(e))
                continue

        return games

    def _parse_game(self, game_data: dict, default_date: date | None = None) -> ScheduledGame | None:
        """Parse a single game."""
        game_id = str(game_data.get("id", ""))

        teams = game_data.get("teams", {})
        home_data = teams.get("home", {})
        away_data = teams.get("away", {})

        home_team = home_data.get("name", "")
        away_team = away_data.get("name", "")

        if not home_team or not away_team:
            return None

        # Parse date/time
        date_str = game_data.get("date", "")[:10]
        game_date = default_date or date.today()
        game_time = None

        if date_str:
            try:
                game_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        full_date_str = game_data.get("date", "")
        if full_date_str:
            try:
                game_time = datetime.fromisoformat(full_date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Status
        status_data = game_data.get("status", {})
        status_long = status_data.get("long", "Not Started")

        status_map = {
            "Not Started": "scheduled",
            "In Progress": "in_progress",
            "Game Finished": "final",
            "Postponed": "postponed",
            "Cancelled": "cancelled",
        }
        status = status_map.get(status_long, "scheduled")

        # Scores
        scores = game_data.get("scores", {})
        home_score = scores.get("home", {}).get("total")
        away_score = scores.get("away", {}).get("total")

        return ScheduledGame(
            external_id=f"bball_api:{game_id}",
            source="basketball_api",
            home_team_raw=home_team,
            away_team_raw=away_team,
            game_date=game_date,
            game_time=game_time,
            status=status,
            home_score=home_score,
            away_score=away_score,
        )


def fetch_schedules_parallel(
    target_date: date | None = None,
    season_year: int | None = None,
) -> tuple[list[ScheduledGame], list[ScheduledGame]]:
    """
    Fetch schedules from ESPN and Basketball API in parallel.

    Args:
        target_date: Specific date to fetch (for daily runs)
        season_year: Full season to fetch (for initial load)

    Returns:
        Tuple of (espn_games, basketball_api_games)
    """
    espn_client = ESPNScheduleClient()
    bball_client = BasketballAPIScheduleClient()

    espn_games = []
    bball_games = []

    def fetch_espn():
        nonlocal espn_games
        try:
            if season_year:
                espn_games = espn_client.get_season_schedule(season_year)
            elif target_date:
                espn_games = espn_client.get_schedule_for_date(target_date)
            logger.info("espn_fetch_complete", games=len(espn_games))
        except Exception as e:
            logger.error("espn_fetch_error", error=str(e))

    def fetch_bball():
        nonlocal bball_games
        try:
            if season_year:
                bball_games = bball_client.get_season_schedule(season_year)
            elif target_date:
                bball_games = bball_client.get_schedule_for_date(target_date)
            logger.info("basketball_api_fetch_complete", games=len(bball_games))
        except Exception as e:
            logger.error("basketball_api_fetch_error", error=str(e))

    # Run in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        espn_future = executor.submit(fetch_espn)
        bball_future = executor.submit(fetch_bball)
        espn_future.result()
        bball_future.result()

    return espn_games, bball_games


def cross_validate_schedules(
    espn_games: list[ScheduledGame],
    bball_games: list[ScheduledGame],
) -> dict[str, Any]:
    """
    Cross-validate schedules from both sources.

    Identifies:
    - Games in both sources (matched)
    - Games only in ESPN
    - Games only in Basketball API
    - Conflicts (different info for same game)

    Returns validation report.
    """
    # Build lookup by date + team names (normalized)
    def normalize(name: str) -> str:
        return name.lower().strip().replace("state", "st").replace(".", "").replace("-", " ")

    def game_key(game: ScheduledGame) -> str:
        home = normalize(game.home_team_raw)
        away = normalize(game.away_team_raw)
        return f"{game.game_date}:{away}@{home}"

    espn_by_key = {game_key(g): g for g in espn_games}
    bball_by_key = {game_key(g): g for g in bball_games}

    all_keys = set(espn_by_key.keys()) | set(bball_by_key.keys())

    matched = []
    espn_only = []
    bball_only = []
    conflicts = []

    for key in all_keys:
        in_espn = key in espn_by_key
        in_bball = key in bball_by_key

        if in_espn and in_bball:
            espn_game = espn_by_key[key]
            bball_game = bball_by_key[key]

            # Check for conflicts
            if espn_game.status == "final" and bball_game.status == "final":
                if espn_game.home_score != bball_game.home_score or \
                   espn_game.away_score != bball_game.away_score:
                    conflicts.append({
                        "key": key,
                        "espn": espn_game,
                        "bball": bball_game,
                        "reason": "score_mismatch",
                    })
                else:
                    matched.append({"key": key, "espn": espn_game, "bball": bball_game})
            else:
                matched.append({"key": key, "espn": espn_game, "bball": bball_game})
        elif in_espn:
            espn_only.append(espn_by_key[key])
        else:
            bball_only.append(bball_by_key[key])

    return {
        "matched": len(matched),
        "espn_only": len(espn_only),
        "bball_only": len(bball_only),
        "conflicts": len(conflicts),
        "total_espn": len(espn_games),
        "total_bball": len(bball_games),
        "match_rate": len(matched) / max(len(all_keys), 1),
        "matched_games": matched,
        "espn_only_games": espn_only,
        "bball_only_games": bball_only,
        "conflict_games": conflicts,
    }


if __name__ == "__main__":
    # CLI for testing

    print("=" * 60)
    print("Schedule Sources Test")
    print("=" * 60)

    # Test today's schedule
    today = date.today()
    print(f"\nFetching schedules for {today}...")

    espn_games, bball_games = fetch_schedules_parallel(target_date=today)

    print(f"\nESPN: {len(espn_games)} games")
    for g in espn_games[:5]:
        print(f"  {g.away_team_raw} @ {g.home_team_raw} ({g.status})")

    print(f"\nBasketball API: {len(bball_games)} games")
    for g in bball_games[:5]:
        print(f"  {g.away_team_raw} @ {g.home_team_raw} ({g.status})")

    # Cross-validate
    print("\nCross-validation:")
    report = cross_validate_schedules(espn_games, bball_games)
    print(f"  Matched: {report['matched']}")
    print(f"  ESPN only: {report['espn_only']}")
    print(f"  Basketball API only: {report['bball_only']}")
    print(f"  Conflicts: {report['conflicts']}")
    print(f"  Match rate: {report['match_rate']:.1%}")
