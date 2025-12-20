# Basketball API Implementation Guide
## Reliable NCAAM Data Ingestion with Error Resilience

**Date:** December 20, 2025  
**Purpose:** Production-grade patterns for reliable Basketball API integration

---

## 1. Core Implementation Pattern

### Best Practice: Health-Checked Polling with Fallback

```python
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, List, Any
import aiohttp
import backoff

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BasketballApiClient:
    """Production-grade Basketball API client with resilience"""
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT_KEY = "basketball_ncaab"
    TIMEOUT = 30  # seconds
    MAX_RETRIES = 5
    
    def __init__(self, api_key: str, poll_interval: int = 30):
        """
        Args:
            api_key: The Odds API key
            poll_interval: Seconds between polls (respect 45 req/min limit)
        """
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_poll_time = None
        self.last_successful_poll = None
        self.error_count = 0
        self.consecutive_errors = 0
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_odds(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch current odds for all NCAAM games
        
        Returns:
            List of game objects with odds, or None if failed
        """
        self.last_poll_time = datetime.utcnow()
        
        try:
            url = f"{self.BASE_URL}/sports/{self.SPORT_KEY}/odds"
            params = {
                "apiKey": self.api_key,
                "regions": "us",
                "markets": "spreads,totals,h2h",
                "oddsFormat": "american"
            }
            
            async with self.session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
            ) as response:
                
                # Check remaining quota
                remaining = response.headers.get("x-requests-remaining")
                logger.info(f"Requests remaining: {remaining}")
                
                # Handle various response codes
                if response.status == 200:
                    data = await response.json()
                    self.consecutive_errors = 0
                    self.last_successful_poll = datetime.utcnow()
                    logger.info(f"✅ Fetched {len(data)} games")
                    return data
                
                elif response.status == 429:  # Rate limit
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"⚠️ Rate limited. Waiting {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    return await self.fetch_odds()  # Retry
                
                elif response.status in [500, 502, 503, 504]:  # Server error
                    self.consecutive_errors += 1
                    logger.error(f"❌ Server error {response.status}. "
                               f"Consecutive errors: {self.consecutive_errors}")
                    return None
                
                elif response.status == 401:  # Invalid key
                    logger.error("❌ Invalid API key!")
                    raise ValueError("Invalid API key")
                
                else:
                    logger.error(f"❌ Unexpected status {response.status}")
                    return None
        
        except asyncio.TimeoutError:
            self.consecutive_errors += 1
            logger.error(f"❌ Request timeout (>{self.TIMEOUT}s). "
                       f"Consecutive errors: {self.consecutive_errors}")
            return None
        
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"❌ Fetch failed: {e}. "
                       f"Consecutive errors: {self.consecutive_errors}")
            return None
    
    async def poll_continuously(self, callback):
        """
        Continuously poll the API at regular intervals
        
        Args:
            callback: Async function(games) called on successful fetch
        """
        logger.info(f"Starting continuous polling (interval: {self.poll_interval}s)")
        
        while True:
            try:
                games = await self.fetch_odds()
                
                if games:
                    await callback(games)
                elif self.consecutive_errors > 10:
                    logger.error("❌ Too many consecutive errors, entering fallback mode")
                    # Could implement fallback to cached data here
                
                await asyncio.sleep(self.poll_interval)
            
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(60)  # Back off on unexpected errors
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status for monitoring"""
        return {
            "last_poll": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "last_success": self.last_successful_poll.isoformat() if self.last_successful_poll else None,
            "consecutive_errors": self.consecutive_errors,
            "total_errors": self.error_count
        }


# Usage Example
async def process_games(games: List[Dict[str, Any]]):
    """Process fetched games (store in DB, etc.)"""
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        logger.info(f"Processing: {home} vs {away}")
        # TODO: Store in database
        # TODO: Calculate CLV edges
        # TODO: Publish to Redis


async def main():
    api_key = "your_api_key_here"
    
    async with BasketballApiClient(api_key, poll_interval=30) as client:
        await client.poll_continuously(process_games)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 2. Synchronous Version (For Non-Async Context)

```python
import requests
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SyncBasketballApiClient:
    """Synchronous Basketball API client"""
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT_KEY = "basketball_ncaab"
    TIMEOUT = 30
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.last_error_time = None
        self.consecutive_errors = 0
    
    def fetch_odds(self, max_retries: int = 4) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch odds with exponential backoff retry
        
        Args:
            max_retries: Number of retry attempts
        
        Returns:
            List of games or None
        """
        url = f"{self.BASE_URL}/sports/{self.SPORT_KEY}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american"
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Fetching odds (attempt {attempt}/{max_retries})...")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.TIMEOUT
                )
                
                # Log quota
                remaining = response.headers.get("x-requests-remaining")
                logger.info(f"Requests remaining: {remaining}")
                
                # Success
                if response.status_code == 200:
                    data = response.json()
                    self.consecutive_errors = 0
                    logger.info(f"✅ Fetched {len(data)} games")
                    return data
                
                # Rate limit - honor Retry-After
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"⚠️ Rate limited. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                # Server error - exponential backoff
                if 500 <= response.status_code < 600:
                    if attempt < max_retries:
                        wait = 2 ** (attempt - 1)  # 1s, 2s, 4s, 8s
                        logger.warning(f"⚠️ Server error {response.status_code}. "
                                      f"Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    else:
                        logger.error(f"❌ Server error {response.status_code} after {max_retries} attempts")
                
                # Non-retryable errors
                if response.status_code == 401:
                    logger.error("❌ Invalid API key!")
                    raise ValueError("Invalid API key")
                
                logger.error(f"❌ Unexpected status {response.status_code}")
                return None
            
            except requests.Timeout:
                if attempt < max_retries:
                    wait = 2 ** (attempt - 1)
                    logger.warning(f"⚠️ Timeout. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error("❌ Timeout after all retries")
                    return None
            
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                self.consecutive_errors += 1
                if attempt < max_retries:
                    wait = 2 ** (attempt - 1)
                    time.sleep(wait)
                else:
                    return None
        
        return None
    
    def fetch_single_game(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch odds for a single game (lower cost if you don't need all games)
        
        Args:
            event_id: Game ID from previous fetch
        
        Returns:
            Game object or None
        """
        url = f"{self.BASE_URL}/sports/{self.SPORT_KEY}/odds/{event_id}"
        
        try:
            response = self.session.get(
                url,
                params={"apiKey": self.api_key},
                timeout=self.TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                time.sleep(int(response.headers.get("Retry-After", 60)))
                return self.fetch_single_game(event_id)  # Retry
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch game {event_id}: {e}")
            return None
    
    def fetch_events(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch game schedule (no odds) - lightweight alternative
        
        Returns:
            List of upcoming games (without odds)
        """
        url = f"{self.BASE_URL}/sports/{self.SPORT_KEY}/events"
        
        try:
            response = self.session.get(
                url,
                params={"apiKey": self.api_key},
                timeout=self.TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return None
    
    def close(self):
        """Close session"""
        self.session.close()


# Usage Example
def main():
    api_key = "your_api_key_here"
    client = SyncBasketballApiClient(api_key)
    
    try:
        # Option 1: Get all games with odds (full data)
        games = client.fetch_odds()
        if games:
            for game in games:
                print(f"{game['home_team']} vs {game['away_team']}")
                for bookmaker in game["bookmakers"]:
                    print(f"  {bookmaker['title']}")
        
        # Option 2: Get just game schedule (lightweight)
        events = client.fetch_events()
        if events:
            print(f"Upcoming games: {len(events)}")
    
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

---

## 3. Data Parsing & Validation

```python
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GameDataValidator:
    """Validate and normalize Basketball API data"""
    
    @staticmethod
    def validate_game(game: Dict[str, Any]) -> bool:
        """
        Validate that a game object has all required fields
        
        Args:
            game: Game object from API
        
        Returns:
            True if valid, False otherwise
        """
        required = ["id", "sport_key", "commence_time", "home_team", "away_team"]
        
        for field in required:
            if field not in game:
                logger.warning(f"Missing field: {field}")
                return False
        
        # Validate sport
        if game["sport_key"] != "basketball_ncaab":
            logger.warning(f"Unexpected sport: {game['sport_key']}")
            return False
        
        # Validate bookmakers
        if not isinstance(game.get("bookmakers", []), list):
            logger.warning("Invalid bookmakers format")
            return False
        
        for bookmaker in game["bookmakers"]:
            if not all(k in bookmaker for k in ["key", "title", "markets"]):
                logger.warning(f"Invalid bookmaker: {bookmaker}")
                return False
            
            for market in bookmaker["markets"]:
                if market["key"] not in ["spreads", "totals", "h2h"]:
                    logger.warning(f"Unknown market type: {market['key']}")
                    return False
                
                # Validate outcomes
                for outcome in market["outcomes"]:
                    if "name" not in outcome:
                        logger.warning(f"Outcome missing name: {outcome}")
                        return False
        
        return True
    
    @staticmethod
    def parse_spreads(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract spread market from game
        
        Returns:
            {
                "game_id": str,
                "home_team": str,
                "away_team": str,
                "bookmakers": {
                    "fanduel": {
                        "home_spread": -2.5,
                        "home_price": -110,
                        "away_spread": 2.5,
                        "away_price": -110,
                        "last_update": datetime
                    }
                }
            }
        """
        spreads = {"game_id": game["id"], "bookmakers": {}}
        
        for bookmaker in game["bookmakers"]:
            # Find spreads market
            spreads_market = next(
                (m for m in bookmaker["markets"] if m["key"] == "spreads"),
                None
            )
            
            if not spreads_market:
                continue
            
            # Extract home/away spreads
            home_outcome = next(
                (o for o in spreads_market["outcomes"] if o["name"] == game["home_team"]),
                None
            )
            away_outcome = next(
                (o for o in spreads_market["outcomes"] if o["name"] == game["away_team"]),
                None
            )
            
            if home_outcome and away_outcome:
                spreads["bookmakers"][bookmaker["key"]] = {
                    "home_spread": home_outcome.get("point"),
                    "home_price": home_outcome.get("price"),
                    "away_spread": away_outcome.get("point"),
                    "away_price": away_outcome.get("price"),
                    "last_update": bookmaker.get("last_update")
                }
        
        return spreads if spreads["bookmakers"] else None
    
    @staticmethod
    def parse_totals(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract totals (over/under) market from game
        
        Returns:
            {
                "game_id": str,
                "bookmakers": {
                    "fanduel": {
                        "total_points": 148.5,
                        "over_price": -110,
                        "under_price": -110,
                        "last_update": datetime
                    }
                }
            }
        """
        totals = {"game_id": game["id"], "bookmakers": {}}
        
        for bookmaker in game["bookmakers"]:
            totals_market = next(
                (m for m in bookmaker["markets"] if m["key"] == "totals"),
                None
            )
            
            if not totals_market or not totals_market["outcomes"]:
                continue
            
            # Over/Under have same point value
            over_outcome = next(
                (o for o in totals_market["outcomes"] if o["name"] == "Over"),
                None
            )
            
            if over_outcome:
                totals["bookmakers"][bookmaker["key"]] = {
                    "total_points": over_outcome.get("point"),
                    "over_price": over_outcome.get("price"),
                    "under_price": over_outcome.get("price"),
                    "last_update": bookmaker.get("last_update")
                }
        
        return totals if totals["bookmakers"] else None
    
    @staticmethod
    def parse_moneyline(game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract head-to-head (moneyline) market from game
        
        Returns:
            {
                "game_id": str,
                "home_team": str,
                "away_team": str,
                "bookmakers": {
                    "fanduel": {
                        "home_price": -140,
                        "away_price": 120,
                        "last_update": datetime
                    }
                }
            }
        """
        h2h = {
            "game_id": game["id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "bookmakers": {}
        }
        
        for bookmaker in game["bookmakers"]:
            h2h_market = next(
                (m for m in bookmaker["markets"] if m["key"] == "h2h"),
                None
            )
            
            if not h2h_market:
                continue
            
            home = next(
                (o for o in h2h_market["outcomes"] if o["name"] == game["home_team"]),
                None
            )
            away = next(
                (o for o in h2h_market["outcomes"] if o["name"] == game["away_team"]),
                None
            )
            
            if home and away:
                h2h["bookmakers"][bookmaker["key"]] = {
                    "home_price": home.get("price"),
                    "away_price": away.get("price"),
                    "last_update": bookmaker.get("last_update")
                }
        
        return h2h if h2h["bookmakers"] else None


# Usage
def process_api_response(games: List[Dict[str, Any]]):
    """Process raw API response"""
    for game in games:
        # Validate
        if not GameDataValidator.validate_game(game):
            logger.warning(f"Skipping invalid game: {game.get('id')}")
            continue
        
        # Parse markets
        spreads = GameDataValidator.parse_spreads(game)
        totals = GameDataValidator.parse_totals(game)
        h2h = GameDataValidator.parse_moneyline(game)
        
        # Store in database
        print(f"Processed: {game['home_team']} vs {game['away_team']}")
        if spreads:
            print(f"  Spreads: {spreads}")
        if totals:
            print(f"  Totals: {totals}")
        if h2h:
            print(f"  Moneyline: {h2h}")
```

---

## 4. Monitoring & Health Checks

```python
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ApiHealthMonitor:
    """Monitor Basketball API health and quota"""
    
    def __init__(self, monthly_quota: int = 2000):
        self.monthly_quota = monthly_quota
        self.requests_used = 0
        self.requests_remaining = monthly_quota
        self.last_check = datetime.utcnow()
        self.error_log = []
        self.success_count = 0
    
    def record_request(self, response_headers: Dict[str, str], success: bool = True):
        """
        Record API request metrics
        
        Args:
            response_headers: HTTP response headers
            success: Whether request succeeded
        """
        if success:
            self.success_count += 1
        
        # Update from headers
        self.requests_remaining = int(response_headers.get("x-requests-remaining", 0))
        self.requests_used = int(response_headers.get("x-requests-used", 0))
        
        if not success:
            self.error_log.append({
                "time": datetime.utcnow(),
                "remaining": self.requests_remaining
            })
            
            # Warn if approaching quota
            if self.requests_remaining < 100:
                logger.warning(f"⚠️ Low quota: {self.requests_remaining} requests remaining")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "requests_remaining": self.requests_remaining,
            "requests_used": self.requests_used,
            "monthly_quota": self.monthly_quota,
            "quota_percent": (self.requests_used / self.monthly_quota) * 100,
            "success_count": self.success_count,
            "recent_errors": len(self.error_log[-10:]),  # Last 10 errors
            "last_check": self.last_check.isoformat()
        }
    
    def estimate_daily_usage(self) -> float:
        """Estimate daily request usage"""
        days_in_month = 30
        if self.requests_used == 0:
            return 0
        
        # Simple estimate based on current usage
        return self.requests_used / 1  # Update as more data collected
    
    def quota_at_risk(self) -> bool:
        """Check if current usage pattern will exceed quota"""
        daily_usage = self.estimate_daily_usage()
        days_remaining = 30 - (self.requests_used / self.monthly_quota * 30)
        
        projected_total = daily_usage * days_remaining
        
        if projected_total > self.requests_remaining:
            logger.warning(f"⚠️ Quota at risk! Projected usage: {projected_total}, "
                          f"Remaining: {self.requests_remaining}")
            return True
        
        return False


# Example usage
def health_check_endpoint():
    """Health check endpoint for monitoring"""
    monitor = ApiHealthMonitor()
    
    # Simulate some requests
    monitor.record_request({"x-requests-remaining": "1995", "x-requests-used": "5"})
    monitor.record_request({"x-requests-remaining": "1990", "x-requests-used": "10"})
    
    status = monitor.get_health_status()
    print(f"Health Status: {status}")
    
    if monitor.quota_at_risk():
        print("⚠️ Consider reducing poll frequency or upgrading API tier")
```

---

## 5. Complete Integration Example

```python
import asyncio
import logging
from typing import List, Dict, Any
import aiohttp

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Components from above
from basketball_api_client import BasketballApiClient
from game_validator import GameDataValidator
from health_monitor import ApiHealthMonitor

class NcaamIntegrationService:
    """Complete NCAAM integration with monitoring"""
    
    def __init__(self, api_key: str, db_handler, redis_handler):
        self.client = BasketballApiClient(api_key, poll_interval=30)
        self.db = db_handler
        self.redis = redis_handler
        self.monitor = ApiHealthMonitor()
    
    async def process_game(self, game: Dict[str, Any]):
        """Process single game"""
        if not GameDataValidator.validate_game(game):
            return
        
        # Extract markets
        spreads = GameDataValidator.parse_spreads(game)
        totals = GameDataValidator.parse_totals(game)
        h2h = GameDataValidator.parse_moneyline(game)
        
        # Store in database
        await self.db.save_game(game)
        if spreads:
            await self.db.save_spreads(spreads)
        if totals:
            await self.db.save_totals(totals)
        if h2h:
            await self.db.save_h2h(h2h)
        
        # Publish to Redis for real-time subscribers
        await self.redis.publish("games:updated", {
            "game_id": game["id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def handle_api_response(self, games: List[Dict[str, Any]]):
        """Handle successful API response"""
        logger.info(f"Processing {len(games)} games")
        
        for game in games:
            await self.process_game(game)
        
        # Record success
        self.monitor.record_request({"x-requests-remaining": "1995"}, success=True)
    
    async def run(self):
        """Run integration service"""
        async with self.client:
            await self.client.poll_continuously(self.handle_api_response)


# Usage
async def main():
    api_key = "your_api_key"
    
    # Initialize handlers (pseudo-code)
    db = DatabaseHandler()
    redis = RedisHandler()
    
    service = NcaamIntegrationService(api_key, db, redis)
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

**Last Updated:** December 20, 2025  
**Version:** 1.0 - PRODUCTION PATTERNS

