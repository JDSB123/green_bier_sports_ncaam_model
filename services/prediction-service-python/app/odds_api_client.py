import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_BASE_URL = "https://api.the-odds-api.com/v4"
DEFAULT_SPORT_KEY = os.getenv("SPORT_KEY", "basketball_ncaab")


class OddsApiError(Exception):
    pass


def _read_secret_file(path: str, name: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
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
        api_key: Optional[str] = None,
        sport_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        regions: Optional[str] = None,
        odds_format: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sport_key = sport_key or DEFAULT_SPORT_KEY
        
        # Priority: 1. Constructor arg, 2. Env var (if set), 3. Docker Secret File
        env_key = os.getenv("THE_ODDS_API_KEY")
        file_key = None
        try:
            file_key = _read_secret_file("/run/secrets/odds_api_key", "odds_api_key")
        except Exception:
            pass

        self.api_key = api_key or env_key or file_key

        if not self.api_key:
             raise OddsApiError("THE_ODDS_API_KEY not found in env vars or secrets/odds_api_key.txt")

        # Config defaults mirror Rust ingestion
        self.regions = regions or os.getenv("REGIONS", "us")
        self.odds_format = odds_format or os.getenv("ODDS_FORMAT", "american")

        self.markets_full = os.getenv("MARKETS_FULL", "spreads,totals,h2h")
        self.markets_h1 = os.getenv("MARKETS_H1", "spreads_h1,totals_h1,h2h_h1")
        self.markets_h2 = os.getenv("MARKETS_H2", "spreads_h2,totals_h2,h2h_h2")

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
                "THE_ODDS_API_KEY appears to be a placeholder value. "
                "Get your API key from https://the-odds-api.com/ and set it in: "
                "Docker Compose: secrets/odds_api_key.txt → /run/secrets/odds_api_key, "
                "or Azure: environment variable THE_ODDS_API_KEY"
            )

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_attempts: int = 5,
    ) -> Tuple[requests.Response, Dict[str, Optional[str]]]:
        url = f"{self.base_url}{path}"
        attempt = 0
        params = params or {}
        params.setdefault("apiKey", self.api_key)

        while True:
            try:
                resp = requests.request(method, url, params=params, timeout=30)
            except requests.RequestException as e:
                attempt += 1
                if attempt >= max_attempts:
                    raise OddsApiError(f"Network error after {max_attempts} attempts: {e}")
                time.sleep(2 ** attempt)
                continue

            status = resp.status_code
            if 200 <= status < 300:
                headers = {
                    "x-requests-remaining": resp.headers.get("x-requests-remaining"),
                    "x-requests-used": resp.headers.get("x-requests-used"),
                }
                return resp, headers

            # Retry on 429/5xx
            if status == 429 or 500 <= status < 600:
                attempt += 1
                if attempt >= max_attempts:
                    raise OddsApiError(
                        f"Odds API error after {max_attempts} attempts (status {status}): {resp.text}"
                    )
                delay = 2 ** attempt
                ra = resp.headers.get("Retry-After")
                if ra:
                    try:
                        delay = int(ra)
                    except ValueError:
                        pass
                time.sleep(delay)
                continue

            # Non-retryable
            raise OddsApiError(f"Odds API error (status {status}): {resp.text}")

    # Public methods
    def get_sports(self) -> List[Dict[str, Any]]:
        resp, _ = self._request("GET", "/sports")
        return resp.json()

    def get_events(self) -> List[Dict[str, Any]]:
        path = f"/sports/{self.sport_key}/events"
        resp, _ = self._request("GET", path)
        return resp.json()

    def get_odds_full(
        self,
        markets: Optional[str] = None,
        regions: Optional[str] = None,
        odds_format: Optional[str] = None,
        bookmakers: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
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
        markets: Optional[str] = None,
        bookmakers: Optional[str] = None,
        regions: Optional[str] = None,
        odds_format: Optional[str] = None,
    ) -> Dict[str, Any]:
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

    def get_scores(self, days_from: int = 1) -> List[Dict[str, Any]]:
        path = f"/sports/{self.sport_key}/scores"
        params = {"daysFrom": days_from}
        resp, _ = self._request("GET", path, params=params)
        return resp.json()

    # Convenience methods aligned with env-configured markets
    def get_odds_h1(self) -> List[Dict[str, Any]]:
        events = self.get_events()
        out: List[Dict[str, Any]] = []
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

    def get_odds_h2(self) -> List[Dict[str, Any]]:
        events = self.get_events()
        out: List[Dict[str, Any]] = []
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
