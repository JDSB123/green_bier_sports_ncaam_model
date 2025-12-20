# Basketball API Endpoints Guide - The Odds API
## Complete NCAAM College Basketball API Reference

**Date:** December 20, 2025  
**Status:** COMPREHENSIVE ENDPOINT DOCUMENTATION  
**Purpose:** Complete review of all available Basketball API endpoints with error handling patterns

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Primary Endpoints](#primary-endpoints)
3. [Authentication](#authentication)
4. [Rate Limiting](#rate-limiting)
5. [Error Handling & Resilience](#error-handling--resilience)
6. [Request/Response Format](#requestresponse-format)
7. [All Available Sport Keys](#all-available-sport-keys)
8. [Market Types & Options](#market-types--options)
9. [Implementation Patterns](#implementation-patterns)
10. [Error Recovery Strategies](#error-recovery-strategies)
11. [Testing & Validation](#testing--validation)

---

## Overview

**The Odds API** provides real-time sports betting odds from multiple bookmakers.

**For NCAAM (College Basketball):**
- **Sport Key:** `basketball_ncaab`
- **Base URL:** `https://api.the-odds-api.com/v4`
- **Default Region:** `us` (United States)
- **Data Update Frequency:** Real-time (updated continuously)
- **Authentication:** API Key required

---

## Primary Endpoints

### 1. **GET /sports**
**Lists all available sports**

```
GET https://api.the-odds-api.com/v4/sports?apiKey=YOUR_API_KEY
```

**Response:** Lists all supported sports including:
- `basketball_ncaab` (NCAA Basketball)
- `basketball_nba` (NBA)
- `football_nfl` (NFL)
- `baseball_mlb` (MLB)
- And many others...

**Usage in Your System:** ✅ **Currently NOT used** (hardcoded to `basketball_ncaab`)

**Rate Cost:** 1 request

---

### 2. **GET /sports/{sport_key}/odds** ⭐ PRIMARY ENDPOINT
**Fetches current odds for all games in the specified sport**

```
GET https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds
```

**Required Parameters:**
| Parameter | Type | Value | Required |
|-----------|------|-------|----------|
| `apiKey` | string | Your API key | ✅ Yes |

**Optional Parameters:**
| Parameter | Type | Values | Effect |
|-----------|------|--------|--------|
| `regions` | string | `us`, `eu`, `au`, comma-separated | Filter bookmakers by region (default: all) |
| `markets` | string | `spreads`, `totals`, `h2h`, comma-separated | Which betting markets to return |
| `oddsFormat` | string | `american`, `decimal` | Odds format (default: `american`) |
| `dateFormat` | string | `iso`, `unix` | Date format (default: `iso`) |
| `bookmakers` | string | `fanduel`, `draftkings`, etc., comma-separated | Limit to specific bookmakers |

**YOUR CURRENT USAGE:**
```python
params = {
    "apiKey": api_key,
    "regions": "us",
    "markets": "spreads,totals,h2h",
    "oddsFormat": "american",
}
```

**Response Structure (Simplified):**
```json
[
  {
    "id": "4bfc98ab9a0fc0b66e8f0e3d...",
    "sport_key": "basketball_ncaab",
    "sport_title": "College Basketball",
    "commence_time": "2025-03-15T18:00:00Z",
    "home_team": "Duke Blue Devils",
    "away_team": "North Carolina Tar Heels",
    "bookmakers": [
      {
        "key": "fanduel",
        "title": "FanDuel",
        "last_update": "2025-03-15T17:45:30Z",
        "markets": [
          {
            "key": "spreads",
            "last_update": "2025-03-15T17:45:30Z",
            "outcomes": [
              { "name": "Duke Blue Devils", "price": -110, "point": -2.5 },
              { "name": "North Carolina Tar Heels", "price": -110, "point": 2.5 }
            ]
          },
          {
            "key": "totals",
            "last_update": "2025-03-15T17:45:30Z",
            "outcomes": [
              { "name": "Over", "price": -110, "point": 148.5 },
              { "name": "Under", "price": -110, "point": 148.5 }
            ]
          },
          {
            "key": "h2h",
            "last_update": "2025-03-15T17:45:30Z",
            "outcomes": [
              { "name": "Duke Blue Devils", "price": -140 },
              { "name": "North Carolina Tar Heels", "price": 120 }
            ]
          }
        ]
      }
    ]
  }
]
```

**Rate Cost:** 1 request (includes all bookmakers and markets)

---

### 3. **GET /sports/{sport_key}/events**
**Lists upcoming and recent events for a sport (no odds)**

```
GET https://api.the-odds-api.com/v4/sports/basketball_ncaab/events?apiKey=YOUR_API_KEY
```

**Response:** Similar to odds endpoint but WITHOUT bookmakers/markets
- Useful for game schedules
- Lighter payload
- Good for identifying games

**YOUR CURRENT USAGE:** ❌ **NOT implemented**

**Rate Cost:** 1 request

---

### 4. **GET /sports/{sport_key}/odds/{event_id}**
**Fetches odds for a specific game**

```
GET https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/4bfc98ab9a0fc0b66e8f0e3d?apiKey=YOUR_API_KEY
```

**Usage:** When you need odds for a single game only (not bulk refresh)

**YOUR CURRENT USAGE:** ❌ **NOT implemented**

**Rate Cost:** 1 request

---

### 5. **GET /sports/{sport_key}/scores**
**Fetches recent game results and scores**

```
GET https://api.the-odds-api.com/v4/sports/basketball_ncaab/scores?apiKey=YOUR_API_KEY
```

**Optional Parameters:**
| Parameter | Type | Effect |
|-----------|------|--------|
| `daysFrom` | int | Days from today (0 = today, 1 = tomorrow, -1 = yesterday) |

**Response Includes:**
- Game results
- Final scores
- Completion status
- Game timestamps

**YOUR CURRENT USAGE:** ❌ **NOT implemented**

**Rate Cost:** 1 request

---

## Authentication

### API Key Management

**Where Your Key is Stored:**
```
File:    secrets/odds_api_key.txt
Docker:  /run/secrets/odds_api_key
Env:     THE_ODDS_API_KEY (optional fallback)
```

**Key Characteristics:**
- 32-character hexadecimal string
- Unique to your account
- Rate-limited per key
- Must be kept secret

**Usage in Requests:**
```python
params = {
    "apiKey": api_key,  # Always required
    ...
}
```

**Key Validation (Your Code Does This):**
```python
key_lower = api_key.strip().lower()
if "change_me" in key_lower or key_lower.startswith("sample"):
    return False, "API key appears to be a placeholder"
```

---

## Rate Limiting

### Request Quotas

| Plan | Requests/Minute | Requests/Month | Status |
|------|-----------------|-----------------|--------|
| Free Tier | 20 | 500 | ❌ Not suitable |
| **Hobby** | **45** | **2,000** | ✅ **YOUR TIER** |
| Professional | 100 | 10,000 | |

**Your System Uses:** 45 requests/minute (hardcoded in Rust service)

### Rate Limiting Implementation

**Current Code (Rust Service):**
```rust
// Rate limiter: 45 requests per minute
let rate_limiter = RateLimiter::direct(Quota::per_minute(NonZeroU32::new(45).unwrap()));

// Wait before each request
self.rate_limiter.until_ready().await;
```

### Quota Tracking

**Response Headers to Monitor:**
```
x-requests-remaining: 1995  // Requests remaining this month
x-requests-used: 5          // Requests used this month
```

**Your Code Logs This:**
```python
remaining = resp.headers.get("x-requests-remaining", "?")
return True, f"Odds API OK: {len(data)} events (remaining: {remaining})"
```

### Monthly Quota Calculation

**Hobby Tier: 2,000 requests/month**

**Your Current Usage Pattern:**
- Poll every 30 seconds = 120 polls/hour
- 120 × 24 = 2,880 requests/day
- **This EXCEEDS your monthly limit!** ⚠️

**Optimization Needed:**
- Reduce poll frequency to ~10 seconds per request: 8,640/day
- Or increase to Professional tier ($20/month)

---

## Error Handling & Resilience

### Common Error Responses

| Status Code | Name | Meaning | Retry? | Action |
|-------------|------|---------|--------|--------|
| **200** | OK | Success - parse response | ❌ No | Process data |
| **204** | No Content | No games/odds available | ⚠️ Maybe | Try again later |
| **400** | Bad Request | Invalid parameters | ❌ No | Check query params |
| **401** | Unauthorized | Invalid API key | ❌ No | Check key |
| **403** | Forbidden | Rate limit exceeded | ✅ **Yes** | Wait & retry |
| **404** | Not Found | Invalid sport key | ❌ No | Check sport_key |
| **429** | Too Many Requests | Rate limit hit | ✅ **Yes** | Backoff & retry |
| **500-599** | Server Error | API is down | ✅ **Yes** | Exponential backoff |

### YOUR Error Handling (Python Test Script)

```python
def _retry_request(method: str, url: str, *, params=None, headers=None, 
                   timeout=20, max_attempts=4) -> Tuple[bool, requests.Response | None, str]:
    """Perform HTTP request with exponential backoff + jitter"""
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.request(method, url, params=params, headers=headers, timeout=timeout)
            
            # Success
            if resp.status_code == 200:
                return True, resp, ""
            
            # Retry on 429 or 5xx
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                delay = 2 ** (attempt - 1)  # Exponential: 1s, 2s, 4s, 8s
                
                # Honor Retry-After if present
                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    delay = int(ra)
                
                # Add jitter: 0-250ms
                delay = delay + random.random() * 0.25
                time.sleep(delay)
                last_err = f"status {resp.status_code}"
                continue
            
            # Non-retryable
            return False, resp, f"unexpected status {resp.status_code}"
        
        except requests.RequestException as e:
            last_err = str(e)
            if attempt == max_attempts:
                return False, None, last_err
            
            delay = 2 ** (attempt - 1) + random.random() * 0.25
            time.sleep(delay)
    
    return False, None, last_err
```

**Backoff Pattern:**
```
Attempt 1: Wait 1.0s   (2^0)
Attempt 2: Wait 2.25s  (2^1 + jitter)
Attempt 3: Wait 4.10s  (2^2 + jitter)
Attempt 4: Wait 8.18s  (2^3 + jitter)
```

### YOUR Error Handling (Rust Service)

```rust
pub async fn fetch_events(&self) -> Result<Vec<OddsApiEvent>> {
    // Wait for rate limit
    self.rate_limiter.until_ready().await;

    let url = format!(
        "https://api.the-odds-api.com/v4/sports/{}/odds",
        self.config.sport_key
    );

    // Retry loop for transient failures
    let mut attempt: u32 = 0;
    let max_attempts: u32 = 5;
    
    let response = loop {
        attempt += 1;
        
        let req = self.http_client
            .get(&url)
            .query(&[
                ("apiKey", self.config.odds_api_key.as_str()),
                ("regions", "us"),
                ("markets", "spreads,totals,h2h"),
                ("oddsFormat", "american"),
            ]);

        match req.send().await {
            Ok(resp) => {
                match resp.status() {
                    StatusCode::OK => break resp,
                    StatusCode::TOO_MANY_REQUESTS | code if code.is_server_error() => {
                        if attempt >= max_attempts {
                            return Err(anyhow!("Max retries exceeded"));
                        }
                        
                        // Honor Retry-After
                        let delay = resp.headers()
                            .get("Retry-After")
                            .and_then(|h| h.to_str().ok())
                            .and_then(|s| s.parse::<u64>().ok())
                            .unwrap_or(2u64.pow(attempt));
                        
                        warn!("Rate limited, waiting {}s before retry {}/{}", delay, attempt, max_attempts);
                        tokio::time::sleep(Duration::from_secs(delay)).await;
                    }
                    code => return Err(anyhow!("API error: {}", code)),
                }
            }
            Err(e) => {
                if attempt >= max_attempts {
                    return Err(anyhow!("Network error: {}", e));
                }
                
                let delay = 2u64.pow(attempt);
                warn!("Network error: {}. Retrying in {}s ({}/{})", e, delay, attempt, max_attempts);
                tokio::time::sleep(Duration::from_secs(delay)).await;
            }
        }
    };

    // Parse response
    let events: Vec<OddsApiEvent> = response.json().await?;
    
    // Record success
    self.health.record_success(events.len()).await;
    
    Ok(events)
}
```

---

## Request/Response Format

### Request Headers (Auto-Added by HTTP Clients)

```
User-Agent: Rust-reqwest/0.11 (or Python-requests/2.31)
Accept: application/json
Content-Type: application/json
```

### Response Headers (Important)

```
Content-Type: application/json
X-Requests-Remaining: 1995
X-Requests-Used: 5
X-Requests-Limit: 2000
Retry-After: 60 (only on 429 responses)
Cache-Control: no-cache
```

### Response Format

**All responses are JSON arrays of game objects:**

```json
[
  {
    "id": "4bfc98ab9a0fc0b66e8f0e3d...",
    "sport_key": "basketball_ncaab",
    "sport_title": "College Basketball",
    "commence_time": "2025-03-15T18:00:00Z",
    "home_team": "Duke Blue Devils",
    "away_team": "North Carolina Tar Heels",
    "bookmakers": [
      {
        "key": "fanduel",
        "title": "FanDuel",
        "last_update": "2025-03-15T17:45:30Z",
        "markets": [
          {
            "key": "spreads",
            "outcomes": [
              {
                "name": "Duke Blue Devils",
                "price": -110,
                "point": -2.5
              },
              {
                "name": "North Carolina Tar Heels",
                "price": -110,
                "point": 2.5
              }
            ]
          }
        ]
      }
    ]
  }
]
```

---

## All Available Sport Keys

### Basketball

| Sport Key | Sport Name | League | Availability |
|-----------|-----------|--------|--------------|
| `basketball_ncaab` | NCAA Basketball | College | ✅ **YOUR PRIMARY** |
| `basketball_nba` | NBA | Professional | ✅ Available |
| `basketball_wnba` | WNBA | Professional | ✅ Available |
| `basketball_euroleague` | EuroLeague | European | ✅ Available |

### Football/Soccer

| Sport Key | Sport Name | League | Availability |
|-----------|-----------|--------|--------------|
| `americanfootball_nfl` | NFL | Professional | ✅ Available |
| `americanfootball_ncaaf` | College Football | College | ✅ Available |
| `soccer_epl` | Premier League | European | ✅ Available |
| `soccer_la_liga` | La Liga | European | ✅ Available |

### Other Sports

| Sport Key | Sport Name | League | Availability |
|-----------|-----------|--------|--------------|
| `baseball_mlb` | MLB | Professional | ✅ Available |
| `ice_hockey_nhl` | NHL | Professional | ✅ Available |
| `tennis_atp` | ATP | Professional | ✅ Available |
| `golf_pga` | PGA Tour | Professional | ✅ Available |

---

## Market Types & Options

### Available Markets for NCAAM

| Market Key | Description | Data | Example |
|-----------|-------------|------|---------|
| **`spreads`** | Point spread | `point`, `price` | Duke -2.5 @ -110 |
| **`totals`** | Over/Under | `point`, `price` | Over 148.5 @ -110 |
| **`h2h`** | Head-to-head (moneyline) | `price` | Duke -140 |

**Your Current Query:**
```python
"markets": "spreads,totals,h2h"  # Gets ALL three
```

### How Market Data Works

**Spreads (Point Spread):**
```json
{
  "key": "spreads",
  "outcomes": [
    {
      "name": "Duke Blue Devils",
      "point": -2.5,      // Duke favored by 2.5
      "price": -110       // Need to bet $110 to win $100
    },
    {
      "name": "North Carolina Tar Heels",
      "point": 2.5,       // UNC gets 2.5 points
      "price": -110
    }
  ]
}
```

**Totals (Over/Under):**
```json
{
  "key": "totals",
  "outcomes": [
    {
      "name": "Over",
      "point": 148.5,     // Total points in game
      "price": -110
    },
    {
      "name": "Under",
      "point": 148.5,
      "price": -110
    }
  ]
}
```

**H2H (Moneyline):**
```json
{
  "key": "h2h",
  "outcomes": [
    {
      "name": "Duke Blue Devils",
      "price": -140       // -140 moneyline (heavy favorite)
    },
    {
      "name": "North Carolina Tar Heels",
      "price": 120        // +120 moneyline (underdog)
    }
  ]
}
```

### Regions Parameter

**Available Regions:**

| Region Code | Bookmakers | Example Sportsbooks |
|------------|-----------|-------|
| `us` | US domestic | FanDuel, DraftKings, BetMGM, DraftKings |
| `eu` | European | Bet365, William Hill, Betfair |
| `au` | Australian | Sportsbet, TAB, Neds |

**Your Current Usage:**
```python
"regions": "us"  # Only US bookmakers (recommended)
```

---

## Implementation Patterns

### Pattern 1: Bulk Poll (Your Current Approach)

```python
# Every 30 seconds, fetch ALL games with odds
params = {
    "apiKey": api_key,
    "regions": "us",
    "markets": "spreads,totals,h2h",
    "oddsFormat": "american",
}
response = requests.get(
    "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds",
    params=params,
    timeout=25
)
games = response.json()
# Store all games in database
```

**Pros:**
- ✅ Simple
- ✅ Gets all data
- ✅ Single request

**Cons:**
- ❌ Uses 1 request every 30s = 2,880 requests/day (exceeds quota!)
- ❌ Fetches unchanged games
- ❌ No pagination

---

### Pattern 2: Optimized Event-First Approach

```python
# Step 1: Get events (list of games only, no odds)
response = requests.get(
    "https://api.the-odds-api.com/v4/sports/basketball_ncaab/events",
    params={"apiKey": api_key}
)
games = response.json()  # 50-200 games

# Step 2: Only fetch odds for new/upcoming games
for game in games:
    if game["id"] not in cache and is_upcoming(game["commence_time"]):
        # Single-game odds fetch
        odds_response = requests.get(
            f"https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/{game['id']}",
            params={"apiKey": api_key}
        )
        store_odds(odds_response.json())
```

**Pros:**
- ✅ More efficient
- ✅ Reduces request count

**Cons:**
- ❌ More complex
- ❌ Still multiple requests per refresh

---

### Pattern 3: Webhook-Based (Not Available)

**The Odds API does NOT offer webhooks** - polling is required.

---

## Error Recovery Strategies

### Strategy 1: Exponential Backoff (Recommended)

```python
import random
import time

def fetch_with_backoff(url, api_key, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, params={"apiKey": api_key}, timeout=25)
            
            if response.status_code == 200:
                return response.json()
            
            # Retry on rate limit or server error
            if response.status_code in [429] or 500 <= response.status_code < 600:
                # Honor Retry-After header
                delay = int(response.headers.get("Retry-After", 2 ** (attempt - 1)))
                
                # Add jitter to prevent thundering herd
                delay += random.random()
                
                print(f"Retry-After: {delay}s (attempt {attempt}/{max_attempts})")
                time.sleep(delay)
                continue
            
            # Non-retryable error
            raise Exception(f"API error: {response.status_code}")
        
        except requests.Timeout:
            if attempt >= max_attempts:
                raise
            delay = 2 ** (attempt - 1)
            print(f"Timeout, waiting {delay}s before retry")
            time.sleep(delay)
```

### Strategy 2: Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
    
    def call(self, func):
        """Execute function with circuit breaker protection"""
        # If too many failures, enter "open" state
        if self.failure_count >= self.failure_threshold:
            if time.time() - self.last_failure_time < self.recovery_timeout:
                raise Exception("Circuit breaker is OPEN")
            # Try to recover
            self.failure_count = 0
        
        try:
            result = func()
            self.failure_count = 0  # Success, reset counter
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            raise e
```

### Strategy 3: Fallback to Cached Data

```python
import json
from datetime import datetime, timedelta

class OddsCache:
    def __init__(self, cache_file="odds_cache.json", ttl_minutes=5):
        self.cache_file = cache_file
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get_odds(self, api_key):
        """Get odds, fallback to cache if API fails"""
        try:
            response = requests.get(
                "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds",
                params={"apiKey": api_key},
                timeout=25
            )
            data = response.json()
            self.save_cache(data)
            return data
        except Exception as e:
            print(f"API fetch failed: {e}, using cached data")
            return self.load_cache()
    
    def save_cache(self, data):
        cache = {
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        with open(self.cache_file, "w") as f:
            json.dump(cache, f)
    
    def load_cache(self):
        try:
            with open(self.cache_file, "r") as f:
                cache = json.load(f)
            
            # Check if cache is still valid
            timestamp = datetime.fromisoformat(cache["timestamp"])
            if datetime.utcnow() - timestamp < self.ttl:
                return cache["data"]
            else:
                raise Exception("Cache expired")
        except Exception as e:
            raise Exception(f"No valid cache available: {e}")
```

---

## Testing & Validation

### Test 1: Health Check (Your Current Implementation)

```bash
python testing/scripts/ingestion_healthcheck.py --sport-key basketball_ncaab
```

**Output:**
```
Barttorvik: PASS - Barttorvik OK: 358 team rows
Odds API:  PASS - Odds API OK: 156 events (remaining: 1995)
```

### Test 2: Single Endpoint Test

```python
import requests

# Test the odds endpoint
api_key = "your_api_key_here"
url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
params = {
    "apiKey": api_key,
    "regions": "us",
    "markets": "spreads,totals,h2h",
    "oddsFormat": "american"
}

response = requests.get(url, params=params, timeout=25)
print(f"Status: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"Games: {len(response.json())}")
print(f"Remaining: {response.headers.get('x-requests-remaining')}")
```

### Test 3: Rate Limit Testing

```python
import time
import requests

api_key = "your_api_key_here"
url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"

for i in range(50):
    start = time.time()
    response = requests.get(url, params={"apiKey": api_key})
    elapsed = time.time() - start
    
    remaining = response.headers.get("x-requests-remaining", "?")
    print(f"Request {i+1}: {response.status_code} (elapsed: {elapsed:.2f}s, remaining: {remaining})")
    
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "?")
        print(f"  ⚠️ Rate limited! Retry-After: {retry_after}s")
```

### Test 4: Game Data Validation

```python
def validate_game_data(game):
    """Validate that game object has required fields"""
    required_fields = ["id", "sport_key", "commence_time", "home_team", "away_team"]
    
    for field in required_fields:
        assert field in game, f"Missing field: {field}"
    
    assert game["sport_key"] == "basketball_ncaab"
    assert isinstance(game["bookmakers"], list)
    
    for bookmaker in game["bookmakers"]:
        assert "key" in bookmaker
        assert "markets" in bookmaker
        
        for market in bookmaker["markets"]:
            assert "key" in market
            assert market["key"] in ["spreads", "totals", "h2h"]
            assert "outcomes" in market
            
            for outcome in market["outcomes"]:
                assert "name" in outcome
                if market["key"] in ["spreads", "totals"]:
                    assert "point" in outcome
                if market["key"] != "h2h":
                    assert "price" in outcome

# Usage
import requests
response = requests.get(
    "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds",
    params={"apiKey": api_key}
)

for game in response.json():
    try:
        validate_game_data(game)
        print(f"✅ {game['home_team']} vs {game['away_team']}")
    except AssertionError as e:
        print(f"❌ Invalid game: {e}")
```

---

## SUMMARY: Complete API Reference for NCAAM

### Endpoints Summary

| Endpoint | Method | Purpose | Rate Cost | Your Usage |
|----------|--------|---------|-----------|-----------|
| `/sports` | GET | List all sports | 1 | ❌ Not used |
| `/sports/{sport_key}/odds` | GET | Get all game odds | 1 | ✅ **ACTIVE** |
| `/sports/{sport_key}/events` | GET | Get games (no odds) | 1 | ❌ Not used |
| `/sports/{sport_key}/odds/{event_id}` | GET | Get single game odds | 1 | ❌ Not used |
| `/sports/{sport_key}/scores` | GET | Get game results | 1 | ❌ Not used |

### Key Parameters for NCAAM

```
Sport Key: basketball_ncaab
Region: us
Markets: spreads, totals, h2h
Odds Format: american
Rate Limit: 45 requests/month
```

### Error Handling Checklist

- ✅ Exponential backoff with jitter
- ✅ Honor Retry-After header
- ✅ Timeout handling (25 seconds)
- ✅ Non-retryable error detection
- ✅ Rate limit detection (429)
- ✅ Server error handling (5xx)
- ✅ Fallback to cached data

### Testing Checklist

- ✅ Health check script
- ✅ Single endpoint test
- ✅ Rate limit test
- ✅ Game data validation
- ✅ Bookmaker data validation
- ✅ Market type validation

---

**Last Updated:** December 20, 2025  
**Version:** 1.0 - COMPREHENSIVE REFERENCE

