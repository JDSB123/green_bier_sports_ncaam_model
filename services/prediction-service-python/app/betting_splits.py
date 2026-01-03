"""
Action Network Betting Splits Client.

Fetches public betting percentages and money splits from Action Network.
Works with or without premium credentials - gracefully degrades to public data.

Authentication Flow:
1. Check for ACTION_NETWORK_USERNAME and ACTION_NETWORK_PASSWORD
2. If credentials exist, POST to /web/v1/auth/login
3. If login succeeds, use authenticated /web/v1/games/ncaab endpoint
4. If no credentials or login fails, fallback to /web/v1/scoreboard/ncaab
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)

# Try to import requests, provide helpful error if missing
try:
    import requests
except ImportError:
    requests = None  # type: ignore


@dataclass
class BettingSplits:
    """Betting splits data for a single game."""
    
    # Game identification
    home_team: str
    away_team: str
    game_time: Optional[datetime] = None
    
    # Spread betting splits
    spread_home_public: Optional[float] = None  # % of tickets on home
    spread_away_public: Optional[float] = None  # % of tickets on away
    spread_home_money: Optional[float] = None   # % of money on home
    spread_away_money: Optional[float] = None   # % of money on away
    spread_line: Optional[float] = None         # Current spread
    
    # Total betting splits
    total_over_public: Optional[float] = None   # % of tickets on over
    total_under_public: Optional[float] = None  # % of tickets on under
    total_over_money: Optional[float] = None    # % of money on over
    total_under_money: Optional[float] = None   # % of money on under
    total_line: Optional[float] = None          # Current total
    
    @property
    def has_spread_splits(self) -> bool:
        """Returns True if spread split data is available."""
        return self.spread_home_public is not None and self.spread_home_money is not None
    
    @property
    def has_total_splits(self) -> bool:
        """Returns True if total split data is available."""
        return self.total_over_public is not None and self.total_over_money is not None
    
    @property
    def is_sharp_spread_home(self) -> bool:
        """
        Detect if sharp money is on home spread.
        Sharp indicator: Less tickets but more money.
        """
        if not self.has_spread_splits:
            return False
        # Home has < 50% of tickets but > 50% of money
        return (
            self.spread_home_public is not None
            and self.spread_home_money is not None
            and self.spread_home_public < 50.0
            and self.spread_home_money > 50.0
        )
    
    @property
    def is_sharp_spread_away(self) -> bool:
        """Detect if sharp money is on away spread."""
        if not self.has_spread_splits:
            return False
        return (
            self.spread_away_public is not None
            and self.spread_away_money is not None
            and self.spread_away_public < 50.0
            and self.spread_away_money > 50.0
        )
    
    @property
    def is_sharp_over(self) -> bool:
        """Detect if sharp money is on over."""
        if not self.has_total_splits:
            return False
        return (
            self.total_over_public is not None
            and self.total_over_money is not None
            and self.total_over_public < 50.0
            and self.total_over_money > 50.0
        )
    
    @property
    def is_sharp_under(self) -> bool:
        """Detect if sharp money is on under."""
        if not self.has_total_splits:
            return False
        return (
            self.total_under_public is not None
            and self.total_under_money is not None
            and self.total_under_public < 50.0
            and self.total_under_money > 50.0
        )


class ActionNetworkError(Exception):
    """Error from Action Network API."""
    pass


class ActionNetworkClient:
    """
    Client for Action Network betting splits API.
    
    Supports both authenticated (premium) and public (free) access.
    """
    
    BASE_URL = "https://api.actionnetwork.com"
    SPORT_KEY = "ncaab"  # NCAAM basketball
    
    # Cache TTL in seconds (2 hours as specified)
    CACHE_TTL = 2 * 60 * 60
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        secrets_dir: Optional[Path] = None,
    ):
        """
        Initialize the Action Network client.
        
        Args:
            username: Action Network username (or reads from env/secret file)
            password: Action Network password (or reads from env/secret file)
            secrets_dir: Directory containing secret files (default: /run/secrets)
        """
        if requests is None:
            raise ActionNetworkError(
                "requests library not installed. Run: pip install requests"
            )
        
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GreenBierSports/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        
        self._secrets_dir = secrets_dir or Path("/run/secrets")
        self._username = username or self._load_credential("ACTION_NETWORK_USERNAME")
        self._password = password or self._load_credential("ACTION_NETWORK_PASSWORD")
        self._auth_token: Optional[str] = None
        self._is_premium = False
        
        # In-memory cache
        self._cache: Dict[str, tuple[datetime, Any]] = {}
    
    def _load_credential(self, key: str) -> Optional[str]:
        """Load credential from environment or secret file."""
        # Try environment variable first
        value = os.environ.get(key)
        if value:
            return value
        
        # Try secret file
        secret_file = self._secrets_dir / f"{key.lower()}.txt"
        if secret_file.exists():
            return secret_file.read_text().strip()
        
        return None
    
    def _authenticate(self) -> bool:
        """
        Authenticate with Action Network to get premium access.
        
        Returns:
            True if authentication succeeded, False otherwise.
        """
        if not self._username or not self._password:
            logger.debug("action_network_no_credentials")
            return False
        
        try:
            resp = self._session.post(
                f"{self.BASE_URL}/web/v1/auth/login",
                json={
                    "email": self._username,
                    "password": self._password,
                },
                timeout=30,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self._auth_token = data.get("token")
                self._is_premium = True
                logger.info("action_network_auth_success", premium=True)
                return True
            else:
                logger.warning(
                    "action_network_auth_failed",
                    status=resp.status_code,
                    reason=resp.text[:200],
                )
                return False
                
        except requests.RequestException as e:
            logger.warning("action_network_auth_error", error=str(e))
            return False
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key from endpoint and params."""
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{endpoint}?{param_str}"
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached response if still valid."""
        if cache_key in self._cache:
            cached_time, data = self._cache[cache_key]
            age = (datetime.now(timezone.utc) - cached_time).total_seconds()
            if age < self.CACHE_TTL:
                return data
        return None
    
    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Cache response."""
        self._cache[cache_key] = (datetime.now(timezone.utc), data)
    
    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            endpoint: API endpoint (e.g., "/web/v1/scoreboard/ncaab")
            params: Query parameters
            use_cache: Whether to use cached response
            
        Returns:
            JSON response as dict
        """
        params = params or {}
        cache_key = self._get_cache_key(endpoint, params)
        
        # Check cache
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                logger.debug("action_network_cache_hit", endpoint=endpoint)
                return cached
        
        # Make request
        headers = {}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        
        try:
            resp = self._session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                headers=headers,
                timeout=30,
            )
            
            if resp.status_code == 401:
                # Token expired, try to re-authenticate
                if self._authenticate():
                    return self._request(endpoint, params, use_cache=False)
                raise ActionNetworkError("Authentication failed")
            
            if resp.status_code == 403:
                raise ActionNetworkError(
                    "Premium subscription required for this endpoint"
                )
            
            resp.raise_for_status()
            data = resp.json()
            
            # Cache successful response
            self._set_cache(cache_key, data)
            
            return data
            
        except requests.RequestException as e:
            raise ActionNetworkError(f"API request failed: {e}")
    
    def get_betting_splits(
        self,
        target_date: Optional[datetime] = None,
    ) -> List[BettingSplits]:
        """
        Fetch betting splits for NCAAB games.
        
        Args:
            target_date: Date to fetch (defaults to today)
            
        Returns:
            List of BettingSplits for each game
        """
        if target_date is None:
            target_date = datetime.now(timezone.utc)
        
        date_str = target_date.strftime("%Y-%m-%d")
        
        # Try to authenticate for premium access
        if not self._auth_token and self._username:
            self._authenticate()
        
        # Choose endpoint based on authentication status
        if self._is_premium:
            endpoint = f"/web/v1/games/{self.SPORT_KEY}"
        else:
            endpoint = f"/web/v1/scoreboard/{self.SPORT_KEY}"
        
        try:
            data = self._request(endpoint, {"date": date_str})
        except ActionNetworkError as e:
            logger.warning(
                "action_network_fetch_failed",
                endpoint=endpoint,
                error=str(e),
            )
            # Try fallback to public endpoint
            if self._is_premium:
                self._is_premium = False
                endpoint = f"/web/v1/scoreboard/{self.SPORT_KEY}"
                data = self._request(endpoint, {"date": date_str})
            else:
                raise
        
        return self._parse_games(data)
    
    def _parse_games(self, data: Dict[str, Any]) -> List[BettingSplits]:
        """Parse games from API response."""
        results = []
        
        games = data.get("games") or data.get("events") or []
        
        for game in games:
            try:
                splits = self._parse_game(game)
                if splits:
                    results.append(splits)
            except Exception as e:
                logger.warning(
                    "action_network_parse_error",
                    game_id=game.get("id"),
                    error=str(e),
                )
                continue
        
        logger.info(
            "action_network_fetch_complete",
            games_found=len(results),
            premium=self._is_premium,
        )
        
        return results
    
    def _parse_game(self, game: Dict[str, Any]) -> Optional[BettingSplits]:
        """Parse a single game from API response."""
        # Extract teams
        teams = game.get("teams") or []
        if len(teams) < 2:
            return None
        
        # Find home and away teams
        home_team = None
        away_team = None
        for team in teams:
            if team.get("is_home"):
                home_team = team.get("full_name") or team.get("name")
            else:
                away_team = team.get("full_name") or team.get("name")
        
        if not home_team or not away_team:
            # Fallback: first team is away, second is home (common convention)
            away_team = teams[0].get("full_name") or teams[0].get("name")
            home_team = teams[1].get("full_name") or teams[1].get("name")
        
        # Parse game time
        game_time = None
        if game.get("start_time"):
            try:
                game_time = datetime.fromisoformat(
                    game["start_time"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        splits = BettingSplits(
            home_team=home_team,
            away_team=away_team,
            game_time=game_time,
        )
        
        # Extract betting data from odds/markets
        odds = game.get("odds") or {}
        
        # Spread data
        spread_data = odds.get("spread") or odds.get("spreads") or {}
        if spread_data:
            splits.spread_line = self._safe_float(spread_data.get("line"))
            
            # Public betting percentages
            public = spread_data.get("public") or {}
            splits.spread_home_public = self._safe_float(public.get("home"))
            splits.spread_away_public = self._safe_float(public.get("away"))
            
            # Money percentages (sharp indicator)
            money = spread_data.get("money") or spread_data.get("handle") or {}
            splits.spread_home_money = self._safe_float(money.get("home"))
            splits.spread_away_money = self._safe_float(money.get("away"))
        
        # Total data
        total_data = odds.get("total") or odds.get("totals") or {}
        if total_data:
            splits.total_line = self._safe_float(total_data.get("line"))
            
            # Public betting percentages
            public = total_data.get("public") or {}
            splits.total_over_public = self._safe_float(public.get("over"))
            splits.total_under_public = self._safe_float(public.get("under"))
            
            # Money percentages
            money = total_data.get("money") or total_data.get("handle") or {}
            splits.total_over_money = self._safe_float(money.get("over"))
            splits.total_under_money = self._safe_float(money.get("under"))
        
        # Alternative structure: betting data at game level
        if not splits.has_spread_splits:
            betting = game.get("betting") or game.get("action") or {}
            
            spread_betting = betting.get("spread") or {}
            if spread_betting:
                splits.spread_home_public = self._safe_float(
                    spread_betting.get("home_tickets") or spread_betting.get("home_pct")
                )
                splits.spread_away_public = self._safe_float(
                    spread_betting.get("away_tickets") or spread_betting.get("away_pct")
                )
                splits.spread_home_money = self._safe_float(
                    spread_betting.get("home_money") or spread_betting.get("home_handle_pct")
                )
                splits.spread_away_money = self._safe_float(
                    spread_betting.get("away_money") or spread_betting.get("away_handle_pct")
                )
            
            total_betting = betting.get("total") or {}
            if total_betting:
                splits.total_over_public = self._safe_float(
                    total_betting.get("over_tickets") or total_betting.get("over_pct")
                )
                splits.total_under_public = self._safe_float(
                    total_betting.get("under_tickets") or total_betting.get("under_pct")
                )
                splits.total_over_money = self._safe_float(
                    total_betting.get("over_money") or total_betting.get("over_handle_pct")
                )
                splits.total_under_money = self._safe_float(
                    total_betting.get("under_money") or total_betting.get("under_handle_pct")
                )
        
        return splits
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def get_betting_splits_for_games(
    games: List[Dict[str, Any]],
    target_date: Optional[datetime] = None,
) -> Dict[str, BettingSplits]:
    """
    Fetch betting splits and match to games by team names.
    
    Args:
        games: List of game dicts with 'home' and 'away' keys
        target_date: Date to fetch (defaults to today)
        
    Returns:
        Dict mapping game_key (home_vs_away) to BettingSplits
    """
    try:
        client = ActionNetworkClient()
        splits_list = client.get_betting_splits(target_date)
    except ActionNetworkError as e:
        logger.warning("betting_splits_fetch_failed", error=str(e))
        return {}
    
    # Build lookup by normalized team names
    def normalize(name: str) -> str:
        """Normalize team name for matching."""
        return name.lower().strip().replace("state", "st").replace(".", "")
    
    splits_by_teams: Dict[str, BettingSplits] = {}
    for splits in splits_list:
        home_norm = normalize(splits.home_team)
        away_norm = normalize(splits.away_team)
        key = f"{home_norm}_vs_{away_norm}"
        splits_by_teams[key] = splits
    
    # Match to input games
    result: Dict[str, BettingSplits] = {}
    for game in games:
        home = game.get("home") or game.get("home_team") or ""
        away = game.get("away") or game.get("away_team") or ""
        
        home_norm = normalize(home)
        away_norm = normalize(away)
        key = f"{home_norm}_vs_{away_norm}"
        
        if key in splits_by_teams:
            game_key = f"{home}_vs_{away}"
            result[game_key] = splits_by_teams[key]
        else:
            # Try fuzzy match - require BOTH teams to match (not substring)
            # This prevents "iowa" from matching "iowa_state_vs_clemson"
            for splits_key, splits in splits_by_teams.items():
                splits_parts = splits_key.split("_vs_")
                if len(splits_parts) == 2:
                    splits_home, splits_away = splits_parts
                    # Require exact word boundary match, not substring
                    home_match = (home_norm == splits_home or 
                                  home_norm == splits_away)
                    away_match = (away_norm == splits_home or 
                                  away_norm == splits_away)
                    if home_match and away_match:
                        game_key = f"{home}_vs_{away}"
                        result[game_key] = splits
                        break
    
    logger.info(
        "betting_splits_matched",
        games_input=len(games),
        games_matched=len(result),
    )
    
    return result
