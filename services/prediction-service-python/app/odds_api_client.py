import contextlib
import os
import time
from pathlib import Path
from typing import Any

import requests

from app.logging_config import get_logger
from app.metrics import Timer, increment_counter

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.the-odds-api.com/v4"
DEFAULT_SPORT_KEY = os.getenv("SPORT_KEY", "basketball_ncaab")


class OddsApiError(Exception):
    pass


def _read_secret_file(path: str, name: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception as e:
        raise OddsApiError(f"Secret file missing at {path} ({name}): {e}")


class OddsApiClient:
    """
    Configurable client for The Odds API (v4).

    Supports full-game odds and per-event odds for configurable markets/bookmakers,
    aligned with the Rust service env variables for a repeatable path.
    """

    def __init__(
        self,
        api_key: str | None = None,
        sport_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        regions: str | None = None,
        odds_format: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sport_key = sport_key or DEFAULT_SPORT_KEY

        # Priority: 1) Constructor arg, 2) Env var, 3) Secret file (Docker Compose / other runtimes)
        env_key = (os.getenv("ODDS_API_KEY") or "").strip() or (os.getenv("THE_ODDS_API_KEY") or "").strip()

        file_key = None
        file_path = (
            (os.getenv("ODDS_API_KEY_FILE") or "").strip()
            or (os.getenv("THE_ODDS_API_KEY_FILE") or "").strip()
            or "/run/secrets/odds_api_key"
        )
        with contextlib.suppress(Exception):
            file_key = _read_secret_file(file_path, "odds_api_key")

        self.api_key = api_key or env_key or file_key

        if not self.api_key:
            raise OddsApiError(
                "Odds API key not found. Set ODDS_API_KEY (preferred) or THE_ODDS_API_KEY, "
                "or provide a secret file via ODDS_API_KEY_FILE/THE_ODDS_API_KEY_FILE (default /run/secrets/odds_api_key)."
            )

        # Config defaults mirror Rust ingestion
        self.regions = regions or os.getenv("REGIONS", "us")
        self.odds_format = odds_format or os.getenv("ODDS_FORMAT", "american")

        self.markets_full = os.getenv("MARKETS_FULL", "spreads,totals")
        self.markets_h1 = os.getenv("MARKETS_H1", "spreads_h1,totals_h1")
        self.markets_h2 = os.getenv("MARKETS_H2", "spreads_h2,totals_h2")

        self.bookmakers_h1 = os.getenv(
            "BOOKMAKERS_H1", "bovada,pinnacle,circa,bookmaker"
        )
        self.bookmakers_h2 = os.getenv(
            "BOOKMAKERS_H2", "draftkings,fanduel,pinnacle,bovada"
        )

        key_lower = self.api_key.strip().lower()
        if (
            not self.api_key
            or "change_me" in key_lower
            or key_lower.startswith("sample")
            or key_lower.startswith("your_")
            or key_lower.startswith("<your")
            or key_lower == "4a0b80471d1ebeeb74c358fa0fcc4a2"  # Known example/test key
        ):
            raise OddsApiError(
                "ODDS_API_KEY appears to be a placeholder value. "
                "Get your API key from https://the-odds-api.com/ and set it in: "
                "Docker Compose: secrets/odds_api_key.txt → /run/secrets/odds_api_key, "
                "or Azure: environment variable ODDS_API_KEY"
            )

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        max_attempts: int = 5,
    ) -> tuple[requests.Response, dict[str, str | None]]:
        url = f"{self.base_url}{path}"
        attempt = 0
        params = params or {}
        params.setdefault("apiKey", self.api_key)

        with Timer("odds_api_request_duration_seconds"):
            while True:
                try:
                    resp = requests.request(method, url, params=params, timeout=30)
                    increment_counter("odds_api_requests_total")
                except requests.RequestException as e:
                    attempt += 1
                    increment_counter("odds_api_errors_total", amount=1)
                    logger.warning(
                        "odds_api_request_failed",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(e),
                        path=path,
                    )
                    if attempt >= max_attempts:
                        increment_counter("odds_api_failures_total", amount=1)
                        raise OddsApiError(f"Network error after {max_attempts} attempts: {e}")
                    time.sleep(2 ** attempt)
                    continue

                status = resp.status_code
                if 200 <= status < 300:
                    headers = {
                        "x-requests-remaining": resp.headers.get("x-requests-remaining"),
                        "x-requests-used": resp.headers.get("x-requests-used"),
                    }
                    increment_counter("odds_api_success_total", amount=1)
                    logger.debug(
                        "odds_api_request_success",
                        path=path,
                        status_code=status,
                        requests_remaining=headers.get("x-requests-remaining"),
                    )
                    return resp, headers

                # Retry on 429/5xx
                if status == 429 or 500 <= status < 600:
                    attempt += 1
                    increment_counter("odds_api_retries_total", amount=1)
                    logger.warning(
                        "odds_api_retryable_error",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        status_code=status,
                        path=path,
                    )
                    if attempt >= max_attempts:
                        increment_counter("odds_api_failures_total", amount=1)
                        raise OddsApiError(
                            f"Odds API error after {max_attempts} attempts (status {status}): {resp.text}"
                        )
                    delay = 2 ** attempt
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        with contextlib.suppress(ValueError):
                            delay = int(ra)
                    time.sleep(delay)
                    continue

                # Non-retryable
                increment_counter("odds_api_errors_total", amount=1)
                increment_counter("odds_api_failures_total", amount=1)
                logger.error(
                    "odds_api_non_retryable_error",
                    status_code=status,
                    path=path,
                    response_text=resp.text[:200],
                )
                raise OddsApiError(f"Odds API error (status {status}): {resp.text}")

    # Public methods
    def get_sports(self) -> list[dict[str, Any]]:
        resp, _ = self._request("GET", "/sports")
        return resp.json()

    def get_events(self) -> list[dict[str, Any]]:
        path = f"/sports/{self.sport_key}/events"
        resp, _ = self._request("GET", path)
        return resp.json()

    def get_odds_full(
        self,
        markets: str | None = None,
        regions: str | None = None,
        odds_format: str | None = None,
        bookmakers: str | None = None,
    ) -> list[dict[str, Any]]:
        path = f"/sports/{self.sport_key}/odds"
        params = {
            "regions": regions or self.regions,
            "markets": markets or self.markets_full,
            "oddsFormat": odds_format or self.odds_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        resp, headers = self._request("GET", path, params=params)
        # You can log headers["x-requests-remaining"] if needed
        return resp.json()

    def get_event_odds(
        self,
        event_id: str,
        markets: str | None = None,
        bookmakers: str | None = None,
        regions: str | None = None,
        odds_format: str | None = None,
    ) -> dict[str, Any]:
        path = f"/sports/{self.sport_key}/events/{event_id}/odds"
        params = {
            "regions": regions or self.regions,
            "oddsFormat": odds_format or self.odds_format,
        }
        if markets:
            params["markets"] = markets
        if bookmakers:
            params["bookmakers"] = bookmakers
        resp, headers = self._request("GET", path, params=params)
        return resp.json()

    def get_scores(self, days_from: int = 1) -> list[dict[str, Any]]:
        path = f"/sports/{self.sport_key}/scores"
        params = {"daysFrom": days_from}
        resp, _ = self._request("GET", path, params=params)
        return resp.json()

    # Convenience methods aligned with env-configured markets
    def get_odds_h1(self) -> list[dict[str, Any]]:
        events = self.get_events()
        out: list[dict[str, Any]] = []
        for ev in events:
            ev_id = ev.get("id")
            if not ev_id:
                continue
            try:
                data = self.get_event_odds(
                    ev_id,
                    markets=self.markets_h1,
                    bookmakers=self.bookmakers_h1,
                )
                out.append(data)
            except OddsApiError:
                # Half markets may be unavailable; skip gracefully
                continue
        return out

    def get_odds_h2(self) -> list[dict[str, Any]]:
        events = self.get_events()
        out: list[dict[str, Any]] = []
        for ev in events:
            ev_id = ev.get("id")
            if not ev_id:
                continue
            try:
                data = self.get_event_odds(
                    ev_id,
                    markets=self.markets_h2,
                    bookmakers=self.bookmakers_h2,
                )
                # Some events may legitimately have no 2H markets; skip empty results
                if data.get("bookmakers"):
                    out.append(data)
            except OddsApiError:
                continue
        return out

    # ═══════════════════════════════════════════════════════════════════════════
    # PREMIUM MARKETS - Additional endpoints from The Odds API
    # ═══════════════════════════════════════════════════════════════════════════

    def get_alternate_lines(
        self,
        event_id: str,
        bookmakers: str | None = None,
    ) -> dict[str, Any]:
        """
        Get alternate spread and total lines for line shopping.

        These are all available point spread and total outcomes beyond
        the featured lines. Useful for finding +EV on alternate numbers.

        Markets: alternate_spreads, alternate_totals, alternate_spreads_h1, alternate_totals_h1
        """
        markets = "alternate_spreads,alternate_totals,alternate_spreads_h1,alternate_totals_h1"
        return self.get_event_odds(event_id, markets=markets, bookmakers=bookmakers)

    def get_team_totals(
        self,
        event_id: str,
        bookmakers: str | None = None,
    ) -> dict[str, Any]:
        """
        Get team totals (over/under on individual team scores).

        Markets: team_totals, alternate_team_totals
        """
        markets = "team_totals,alternate_team_totals"
        return self.get_event_odds(event_id, markets=markets, bookmakers=bookmakers)

    def get_sharp_vs_square_lines(
        self,
        event_id: str,
    ) -> dict[str, Any]:
        """
        Get lines from both sharp and square books for comparison.

        Sharp books: pinnacle, circa, bookmaker
        Square books: draftkings, fanduel, betmgm, caesars

        Use this for line shopping - bet where you get the best number,
        but validate against sharp book consensus.
        """
        all_books = "pinnacle,circa,bookmaker,draftkings,fanduel,betmgm,caesars,bovada"
        return self.get_event_odds(
            event_id,
            markets="spreads,totals,spreads_h1,totals_h1",
            bookmakers=all_books,
        )

    def get_all_game_markets(
        self,
        event_id: str,
        bookmakers: str | None = None,
    ) -> dict[str, Any]:
        """
        Get all game-level markets for an event (comprehensive pull).

        Includes featured lines, alternates, team totals, and moneylines.
        Warning: This is an expensive call that uses more API credits.
        """
        markets = (
            "spreads,totals,h2h,"
            "spreads_h1,totals_h1,h2h_h1,"
            "alternate_spreads,alternate_totals,"
            "alternate_spreads_h1,alternate_totals_h1,"
            "team_totals"
        )
        return self.get_event_odds(event_id, markets=markets, bookmakers=bookmakers)

    def get_closing_lines_for_event(
        self,
        event_id: str,
    ) -> dict[str, Any]:
        """
        Get current lines for CLV capture (pre-game closing line snapshot).

        Focuses on primary markets from sharp books (Pinnacle preferred).
        """
        markets = "spreads,totals,spreads_h1,totals_h1"
        return self.get_event_odds(
            event_id,
            markets=markets,
            bookmakers="pinnacle,bovada,circa",
        )
