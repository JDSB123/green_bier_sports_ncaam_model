"""
SportsDataIO API Client for betting trends and public betting percentages.

This client fetches:
- Public bet percentages (spread/total, home/away, over/under)
- Money percentages (sharp vs public)
- ATS records and trends

API Docs: https://sportsdata.io/developers/api-documentation/ncaa-basketball
"""

import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.logging_config import get_logger
from app.metrics import increment_counter, Timer

logger = get_logger(__name__)

# SportsDataIO NCAAB base URL
DEFAULT_BASE_URL = "https://api.sportsdata.io/v3/cbb"


class SportsDataIOError(Exception):
    """Raised when SportsDataIO API call fails."""
    pass


@dataclass
class BettingSentiment:
    """
    Public betting sentiment for a game.
    
    All percentages are 0.0-1.0 (not 0-100).
    """
    game_id: str
    # Spread sentiment
    spread_bet_pct_home: Optional[float] = None   # % of tickets on home spread
    spread_bet_pct_away: Optional[float] = None   # % of tickets on away spread
    spread_money_pct_home: Optional[float] = None  # % of money on home spread
    spread_money_pct_away: Optional[float] = None  # % of money on away spread
    # Total sentiment
    total_bet_pct_over: Optional[float] = None    # % of tickets on over
    total_bet_pct_under: Optional[float] = None   # % of tickets on under
    total_money_pct_over: Optional[float] = None   # % of money on over
    total_money_pct_under: Optional[float] = None  # % of money on under
    # Metadata
    fetched_at: datetime = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()


def _read_secret_file(path: str, name: str) -> str:
    """Read secret from Docker secret file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        raise SportsDataIOError(f"Secret file missing at {path} ({name}): {e}")


class SportsDataIOClient:
    """
    Client for SportsDataIO NCAAB betting data.
    
    Fetches betting trends including public bet/money percentages.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        
        # Priority: 1. Constructor arg, 2. Env var, 3. Docker Secret File
        env_key = os.getenv("SPORTSDATA_API_KEY")
        file_key = None
        try:
            file_key = _read_secret_file("/run/secrets/sportsdata_api_key", "sportsdata_api_key")
        except Exception:
            pass

        self.api_key = api_key or env_key or file_key

        if not self.api_key:
            logger.warning(
                "sportsdata_api_key_missing",
                message="SPORTSDATA_API_KEY not found - betting trends will be unavailable"
            )
        else:
            logger.info("sportsdata_client_initialized", has_key=True)

    def is_available(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> requests.Response:
        """Make authenticated request with retries."""
        if not self.api_key:
            raise SportsDataIOError("SPORTSDATA_API_KEY not configured")

        url = f"{self.base_url}{path}"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        attempt = 0
        params = params or {}

        with Timer("sportsdata_request_duration_seconds"):
            while True:
                try:
                    resp = requests.request(
                        method, url, headers=headers, params=params, timeout=30
                    )
                    increment_counter("sportsdata_requests_total")
                except requests.RequestException as e:
                    attempt += 1
                    increment_counter("sportsdata_errors_total")
                    logger.warning(
                        "sportsdata_request_failed",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(e),
                        path=path,
                    )
                    if attempt >= max_attempts:
                        raise SportsDataIOError(f"Network error after {max_attempts} attempts: {e}")
                    time.sleep(2 ** attempt)
                    continue

                status = resp.status_code
                if 200 <= status < 300:
                    increment_counter("sportsdata_success_total")
                    return resp

                # Retry on 429/5xx
                if status == 429 or 500 <= status < 600:
                    attempt += 1
                    increment_counter("sportsdata_retries_total")
                    logger.warning(
                        "sportsdata_retryable_error",
                        attempt=attempt,
                        status_code=status,
                        path=path,
                    )
                    if attempt >= max_attempts:
                        raise SportsDataIOError(
                            f"SportsDataIO error after {max_attempts} attempts (status {status})"
                        )
                    time.sleep(2 ** attempt)
                    continue

                # Non-retryable error
                increment_counter("sportsdata_errors_total")
                logger.error(
                    "sportsdata_non_retryable_error",
                    status_code=status,
                    path=path,
                    response_text=resp.text[:200],
                )
                raise SportsDataIOError(f"SportsDataIO error (status {status}): {resp.text}")

    def get_games_by_date(self, game_date: date) -> List[Dict[str, Any]]:
        """
        Get all NCAAB games for a specific date.
        
        Returns list of game objects with GameID, HomeTeam, AwayTeam, etc.
        """
        date_str = game_date.strftime("%Y-%m-%d")
        path = f"/scores/json/GamesByDate/{date_str}"
        resp = self._request("GET", path)
        return resp.json()

    def get_betting_trends_by_matchup(
        self,
        home_team: str,
        away_team: str,
        game_date: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Get betting trends for a specific matchup.
        
        This endpoint returns public betting percentages when available.
        
        Note: SportsDataIO uses team abbreviations (e.g., "DUKE", "UNC").
        """
        date_str = game_date.strftime("%Y-%m-%d")
        # Format: /BettingTrendsByMatchup/{date}/{team}
        # We'll try both home and away team to find the matchup
        path = f"/odds/json/BettingTrendsByMatchup/{date_str}/{home_team}"
        
        try:
            resp = self._request("GET", path)
            data = resp.json()
            if data and isinstance(data, list):
                # Find the specific matchup
                for trend in data:
                    if trend.get("Opponent") == away_team:
                        return trend
            return data if data else None
        except SportsDataIOError as e:
            logger.debug(
                "betting_trends_not_found",
                home_team=home_team,
                away_team=away_team,
                error=str(e),
            )
            return None

    def get_betting_events(self, game_date: date) -> List[Dict[str, Any]]:
        """
        Get betting events/odds for a specific date.
        
        This includes consensus lines and may have betting percentages.
        """
        date_str = game_date.strftime("%Y-%m-%d")
        path = f"/odds/json/BettingEventsByDate/{date_str}"
        
        try:
            resp = self._request("GET", path)
            return resp.json() or []
        except SportsDataIOError as e:
            logger.warning("betting_events_fetch_failed", date=date_str, error=str(e))
            return []

    def get_betting_market(self, game_id: int) -> Optional[Dict[str, Any]]:
        """
        Get betting market data for a specific game.
        
        This may include BettingBetPercentage and BettingMoneyPercentage fields.
        """
        path = f"/odds/json/BettingMarketsByGameID/{game_id}"
        
        try:
            resp = self._request("GET", path)
            return resp.json()
        except SportsDataIOError as e:
            logger.debug("betting_market_not_found", game_id=game_id, error=str(e))
            return None

    def get_betting_splits_for_date(self, game_date: date) -> Dict[str, BettingSentiment]:
        """
        Fetch betting sentiment (public splits) for all games on a date.
        
        Returns dict keyed by "{home_team} vs {away_team}".
        """
        result: Dict[str, BettingSentiment] = {}
        
        if not self.is_available():
            logger.debug("sportsdata_not_configured")
            return result

        try:
            events = self.get_betting_events(game_date)
            
            for event in events:
                game_id = event.get("GameID")
                home = event.get("HomeTeamName", event.get("HomeTeam", ""))
                away = event.get("AwayTeamName", event.get("AwayTeam", ""))
                
                if not home or not away:
                    continue
                
                key = f"{home} vs {away}"
                
                # Try to get detailed market data
                market_data = None
                if game_id:
                    market_data = self.get_betting_market(game_id)
                
                # Extract betting percentages from market data
                sentiment = self._extract_sentiment(str(game_id), event, market_data)
                if sentiment:
                    result[key] = sentiment
                    
            logger.info(
                "betting_splits_fetched",
                date=str(game_date),
                games_with_splits=len(result),
            )
            
        except SportsDataIOError as e:
            logger.error("betting_splits_fetch_error", error=str(e))
        
        return result

    def _extract_sentiment(
        self,
        game_id: str,
        event: Dict[str, Any],
        market_data: Optional[Dict[str, Any]],
    ) -> Optional[BettingSentiment]:
        """
        Extract betting sentiment from SportsDataIO response.
        
        Looks for BettingBetPercentage and BettingMoneyPercentage fields.
        """
        sentiment = BettingSentiment(game_id=game_id)
        has_data = False
        
        # Check event-level data first
        for source in [event, market_data or {}]:
            if not source:
                continue
                
            # Look for consensus betting percentages
            # SportsDataIO field names vary by endpoint
            bet_pct_home = source.get("BettingBetPercentageHome")
            bet_pct_away = source.get("BettingBetPercentageAway")
            money_pct_home = source.get("BettingMoneyPercentageHome")
            money_pct_away = source.get("BettingMoneyPercentageAway")
            
            bet_pct_over = source.get("BettingBetPercentageOver")
            bet_pct_under = source.get("BettingBetPercentageUnder")
            money_pct_over = source.get("BettingMoneyPercentageOver")
            money_pct_under = source.get("BettingMoneyPercentageUnder")
            
            # Also check nested "BettingMarkets" array
            markets = source.get("BettingMarkets") or []
            for market in markets:
                market_type = market.get("BettingMarketType", "")
                
                if "Spread" in market_type:
                    outcomes = market.get("BettingOutcomes") or []
                    for outcome in outcomes:
                        pct = outcome.get("BettingBetPercentage")
                        money = outcome.get("BettingMoneyPercentage")
                        participant = outcome.get("Participant", "")
                        
                        if "Home" in participant or outcome.get("IsHome"):
                            if pct is not None:
                                sentiment.spread_bet_pct_home = pct / 100.0
                                has_data = True
                            if money is not None:
                                sentiment.spread_money_pct_home = money / 100.0
                                has_data = True
                        elif "Away" in participant or outcome.get("IsAway"):
                            if pct is not None:
                                sentiment.spread_bet_pct_away = pct / 100.0
                                has_data = True
                            if money is not None:
                                sentiment.spread_money_pct_away = money / 100.0
                                has_data = True
                
                elif "Total" in market_type:
                    outcomes = market.get("BettingOutcomes") or []
                    for outcome in outcomes:
                        pct = outcome.get("BettingBetPercentage")
                        money = outcome.get("BettingMoneyPercentage")
                        outcome_type = outcome.get("BettingOutcomeType", "")
                        
                        if "Over" in outcome_type:
                            if pct is not None:
                                sentiment.total_bet_pct_over = pct / 100.0
                                has_data = True
                            if money is not None:
                                sentiment.total_money_pct_over = money / 100.0
                                has_data = True
                        elif "Under" in outcome_type:
                            if pct is not None:
                                sentiment.total_bet_pct_under = pct / 100.0
                                has_data = True
                            if money is not None:
                                sentiment.total_money_pct_under = money / 100.0
                                has_data = True
            
            # Simple field extraction
            if bet_pct_home is not None:
                sentiment.spread_bet_pct_home = bet_pct_home / 100.0
                has_data = True
            if bet_pct_away is not None:
                sentiment.spread_bet_pct_away = bet_pct_away / 100.0
                has_data = True
            if money_pct_home is not None:
                sentiment.spread_money_pct_home = money_pct_home / 100.0
                has_data = True
            if money_pct_away is not None:
                sentiment.spread_money_pct_away = money_pct_away / 100.0
                has_data = True
            if bet_pct_over is not None:
                sentiment.total_bet_pct_over = bet_pct_over / 100.0
                has_data = True
            if bet_pct_under is not None:
                sentiment.total_bet_pct_under = bet_pct_under / 100.0
                has_data = True
            if money_pct_over is not None:
                sentiment.total_money_pct_over = money_pct_over / 100.0
                has_data = True
            if money_pct_under is not None:
                sentiment.total_money_pct_under = money_pct_under / 100.0
                has_data = True
        
        return sentiment if has_data else None


# Singleton for reuse
_client: Optional[SportsDataIOClient] = None


def get_sportsdata_client() -> SportsDataIOClient:
    """Get or create singleton SportsDataIO client."""
    global _client
    if _client is None:
        _client = SportsDataIOClient()
    return _client
