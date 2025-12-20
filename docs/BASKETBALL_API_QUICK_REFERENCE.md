# Basketball API Quick Reference & Checklist
## NCAAM API Usage - Everything You Need to Know

**Date:** December 20, 2025  
**Branch:** basketball-api-endpoints  
**Status:** COMPLETE REFERENCE

---

## 🚀 Quick Start

### The One Endpoint You Use (Most of the Time)

```bash
GET https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds
  ?apiKey=YOUR_KEY
  &regions=us
  &markets=spreads,totals,h2h
  &oddsFormat=american
```

**What You Get Back:**
- All college basketball games today/this week
- Spreads, totals, and moneylines from all US sportsbooks
- Updated every 30 seconds

---

## 📊 API At a Glance

| Item | Value |
|------|-------|
| **Sport** | College Basketball (NCAAM) |
| **Sport Key** | `basketball_ncaab` |
| **Base URL** | `https://api.the-odds-api.com/v4` |
| **Primary Endpoint** | `/sports/basketball_ncaab/odds` |
| **Your API Tier** | Hobby (45 req/min, 2,000 req/month) |
| **Your Poll Frequency** | Every 30 seconds (120 polls/hour) |
| **Max Data Freshness** | 30 seconds |

⚠️ **WARNING:** 120 polls/hour × 24 hours = **2,880 requests/day**  
This **EXCEEDS** your 2,000/month quota!  
**Action:** Reduce to ~10-second polls or upgrade to Professional tier.

---

## 🎯 All Endpoints Available

### 1. Get All Games with Odds ⭐ **YOU USE THIS**

```
GET /sports/basketball_ncaab/odds
```

| Param | Type | Required | Example |
|-------|------|----------|---------|
| `apiKey` | string | ✅ YES | `abc123def...` |
| `regions` | string | ❌ Optional | `us` (default: all) |
| `markets` | string | ❌ Optional | `spreads,totals,h2h` |
| `oddsFormat` | string | ❌ Optional | `american` (default) |
| `bookmakers` | string | ❌ Optional | `fanduel,draftkings` |

**Rate Cost:** 1 request  
**Response:** Array of ~50-200 game objects

---

### 2. Get Game Schedule (No Odds)

```
GET /sports/basketball_ncaab/events
```

**Use When:** You only need game times/teams, not odds  
**Rate Cost:** 1 request  
**Response:** Lighter payload (no bookmakers)

---

### 3. Get Single Game Odds

```
GET /sports/basketball_ncaab/odds/{event_id}
```

**Use When:** You already know the game ID, want fresh odds only  
**Rate Cost:** 1 request  
**Response:** Single game object

---

### 4. Get Past Game Results

```
GET /sports/basketball_ncaab/scores
```

**Use When:** You need final scores from completed games  
**Rate Cost:** 1 request  
**Response:** Array of completed games with scores

---

### 5. List All Sports (Reference)

```
GET /sports
```

**Use When:** Discovering what sports are available  
**Rate Cost:** 1 request  
**Response:** Lists all sports (basketball_ncaab, nba, nfl, etc.)

---

## 🔑 Authentication

### Your API Key

```
Location: secrets/odds_api_key.txt
Docker: /run/secrets/odds_api_key
Env Var: THE_ODDS_API_KEY (fallback)
```

**How to Use:**
```python
params = {"apiKey": api_key}
```

**Do NOT:**
- ❌ Commit to git
- ❌ Log in code
- ❌ Send in GET URL visible in browser history
- ❌ Share in Slack/email

---

## 📈 Rate Limiting - CRITICAL

### Your Quota

| Metric | Value |
|--------|-------|
| Requests/minute | 45 |
| Requests/month | 2,000 |
| Requests remaining | Check headers: `x-requests-remaining` |
| Reset | Monthly (1st of month) |

### Monitor Your Quota

**Every response includes headers:**

```
x-requests-remaining: 1995  ← How many left this month
x-requests-used: 5          ← How many used this month
```

**Log these in your code:**

```python
remaining = response.headers.get("x-requests-remaining")
print(f"Requests remaining: {remaining}")

# Warn if low
if int(remaining) < 100:
    logger.warning("⚠️ Low API quota!")
```

### Calculate Your Daily Budget

```
2,000 requests/month ÷ 30 days = ~67 requests/day

If you poll every 30 seconds:
- 120 polls/hour × 24 hours = 2,880 requests/day
- This EXCEEDS quota by 4,320 requests/month!

Solution:
- Option A: Reduce poll to every 5 minutes (2,400 req/month)
- Option B: Upgrade to Professional tier ($20/month)
```

---

## ❌ Error Codes & What to Do

| Code | Meaning | Retry? | Action |
|------|---------|--------|--------|
| **200** | Success | ❌ | Parse and use data |
| **204** | No content | ❌ | No games scheduled |
| **400** | Bad request | ❌ | Check parameters (typo?) |
| **401** | Unauthorized | ❌ | Check API key |
| **403** | Forbidden | ❌ | Account issue, contact support |
| **429** | Rate limited | ✅ **YES** | Wait (see Retry-After header) |
| **500-599** | Server error | ✅ **YES** | Exponential backoff |

### Error Recovery Pattern

```python
# ✅ DO THIS
for attempt in range(1, 5):
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()  # Success!
        
        elif response.status_code == 429:  # Rate limited
            wait = int(response.headers.get("Retry-After", 60))
            time.sleep(wait)
            continue  # Retry
        
        elif 500 <= response.status_code < 600:  # Server error
            wait = 2 ** (attempt - 1)  # Exponential: 1s, 2s, 4s, 8s
            time.sleep(wait)
            continue  # Retry
        
        else:
            raise Exception(f"Unrecoverable error: {response.status_code}")
    
    except requests.Timeout:
        if attempt < 4:
            time.sleep(2 ** (attempt - 1))
            continue
        raise

# ❌ DON'T DO THIS
response = requests.get(url)  # No retry, no error handling
data = response.json()  # Will crash if 429 or 5xx
```

---

## 📋 Response Data Structure

### Game Object

```json
{
  "id": "4bfc98ab9a0fc0b...",          // Unique game ID
  "sport_key": "basketball_ncaab",      // Always this for NCAAM
  "sport_title": "College Basketball",  // Human readable
  "commence_time": "2025-03-15T18:00:00Z",  // Game start (UTC)
  "home_team": "Duke Blue Devils",      // Home team name
  "away_team": "North Carolina Tar Heels",  // Away team name
  "bookmakers": [
    {
      "key": "fanduel",                 // Sportsbook ID
      "title": "FanDuel",               // Human readable
      "last_update": "2025-03-15T17:45:30Z",
      "markets": [
        {
          "key": "spreads",             // Market type
          "last_update": "2025-03-15T17:45:30Z",
          "outcomes": [
            {
              "name": "Duke Blue Devils",    // Team name (for spread)
              "price": -110,                 // Odds (American format)
              "point": -2.5                  // Spread (Duke favored)
            },
            {
              "name": "North Carolina Tar Heels",
              "price": -110,
              "point": 2.5
            }
          ]
        },
        {
          "key": "totals",
          "outcomes": [
            {
              "name": "Over",
              "price": -110,
              "point": 148.5             // Total points in game
            },
            {
              "name": "Under",
              "price": -110,
              "point": 148.5
            }
          ]
        },
        {
          "key": "h2h",                  // Moneyline/head-to-head
          "outcomes": [
            {
              "name": "Duke Blue Devils",
              "price": -140              // Moneyline odds
            },
            {
              "name": "North Carolina Tar Heels",
              "price": 120
            }
          ]
        }
      ]
    }
  ]
}
```

### Key Fields Explanation

| Field | Example | Meaning |
|-------|---------|---------|
| `id` | `abc123...` | Unique identifier for this game |
| `commence_time` | `2025-03-15T18:00:00Z` | When game starts (UTC) |
| `home_team` | `Duke Blue Devils` | Team playing at home |
| `away_team` | `North Carolina...` | Team playing away |
| `point` (spread) | `-2.5` | Duke favored by 2.5 points |
| `price` | `-110` | Odds (see American odds format below) |
| `point` (totals) | `148.5` | Total combined points |

### American Odds Format

- **Negative (favorite):** `-110` means bet $110 to win $100
- **Positive (underdog):** `+120` means bet $100 to win $120
- **Even odds:** `-100` means bet $100 to win $100

---

## 🛡️ Data Validation Checklist

Before storing data, verify:

```python
✅ Game has id, sport_key, commence_time, home_team, away_team
✅ sport_key == "basketball_ncaab"
✅ commence_time is valid ISO 8601 datetime
✅ home_team and away_team are non-empty strings
✅ bookmakers is a list
✅ Each bookmaker has key, title, markets
✅ Each market has key in ["spreads", "totals", "h2h"]
✅ Each outcome has name, price
✅ Spread/totals outcomes have point field
✅ All prices are integers (American odds)
✅ All points are floats
```

**Example Validation:**

```python
def validate_game(game):
    assert game["sport_key"] == "basketball_ncaab"
    assert game["id"], "Missing id"
    assert game["home_team"], "Missing home_team"
    assert game["away_team"], "Missing away_team"
    
    for bookmaker in game["bookmakers"]:
        assert bookmaker["key"], "Missing bookmaker key"
        assert isinstance(bookmaker["markets"], list)
        
        for market in bookmaker["markets"]:
            assert market["key"] in ["spreads", "totals", "h2h"]
            for outcome in market["outcomes"]:
                assert outcome["name"]
                assert isinstance(outcome["price"], int)
```

---

## 🧪 Testing Your Integration

### Test 1: Verify API Access

```bash
curl "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds?apiKey=YOUR_KEY"
```

**Expected:** Array of game objects (200 games = ~5KB)

### Test 2: Check Remaining Quota

```python
import requests

response = requests.get(
    "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds",
    params={"apiKey": api_key}
)

print(f"Status: {response.status_code}")
print(f"Remaining: {response.headers.get('x-requests-remaining')}")
print(f"Used: {response.headers.get('x-requests-used')}")
print(f"Games: {len(response.json())}")
```

### Test 3: Test Error Handling

```python
# Test 429 rate limit handling
# Manual: Make 50 requests in rapid succession, verify backoff

# Test 5xx server error handling
# Manual: Inject random delay/timeout, verify retry

# Test invalid API key
wrong_key = "invalid_key_123"
response = requests.get(url, params={"apiKey": wrong_key})
assert response.status_code == 401  # Unauthorized
```

### Test 4: Data Validation

```python
from ingestion_healthcheck import check_odds_api

success, message = check_odds_api("basketball_ncaab")
print(f"Health: {'✅' if success else '❌'} - {message}")
```

---

## 🔄 Polling Strategy

### Current (❌ OVER QUOTA)

```
Poll every 30 seconds
= 120 polls/hour
= 2,880 polls/day
= 86,400 polls/month
❌ Exceeds 2,000/month quota by 42x!
```

### Recommended (✅ WITHIN QUOTA)

```
Option A: Poll every 5 minutes
= 288 polls/day
= 8,640 polls/month
✅ WITHIN quota, but stale data

Option B: Event-driven polling (advanced)
= Poll every 30s ONLY for upcoming games
= Fewer requests overall

Option C: Upgrade to Professional tier
= 100 req/min, 10,000 req/month
= Can do 30-second polling
= Cost: $20/month
```

---

## 📝 Implementation Checklist

### Before Going Live

- [ ] API key stored in Docker secrets, NOT in code
- [ ] Rate limiting code implemented (wait for quota)
- [ ] Error handling for 429 (rate limit)
- [ ] Error handling for 5xx (server errors)
- [ ] Timeout handling (set timeout=30)
- [ ] Retry logic with exponential backoff
- [ ] Quota monitoring (log remaining requests)
- [ ] Game data validation before storage
- [ ] Logging of all API calls
- [ ] Health check endpoint returns status
- [ ] Fallback to cached data if API fails
- [ ] Circuit breaker for repeated failures

### Monitoring

- [ ] Track `x-requests-remaining` over time
- [ ] Alert if approaching quota
- [ ] Monitor response times
- [ ] Track error rates (429, 5xx)
- [ ] Dashboard showing quota usage
- [ ] Daily email summary of API health

---

## 🚨 Common Mistakes (DON'T DO THESE!)

| Mistake | ❌ Wrong | ✅ Right |
|---------|---------|---------|
| Poll frequency | Every 30s (too fast) | Every 5 min or upgrade tier |
| Error handling | No retry | Exponential backoff + jitter |
| Rate limit handling | Ignore 429 | Wait for Retry-After |
| API key | Hardcoded in code | Docker secrets only |
| Data validation | None | Validate before storage |
| Timeout | No timeout set | timeout=30 |
| Logging | No logging | Log all requests + quota |
| Fallback | No fallback | Use cached data if API fails |

---

## 📞 Support & Resources

### Official Documentation

- **The Odds API Docs:** https://the-odds-api.com/api-details
- **Sport Keys:** https://the-odds-api.com/api-details#tag/sports/operation/listSports
- **Rate Limits:** https://the-odds-api.com/api-details#section/requests-limit

### Your System Documentation

- `docs/BASKETBALL_API_ENDPOINTS_GUIDE.md` — Complete endpoint reference
- `docs/BASKETBALL_API_IMPLEMENTATION.md` — Code patterns
- `testing/scripts/ingestion_healthcheck.py` — Health check script

### Commands

```bash
# Run health check
python testing/scripts/ingestion_healthcheck.py

# View git history
git log --oneline basketball-api-endpoints

# Check current branch
git status
```

---

## ✅ Summary

### What You Need to Know

1. **Endpoint:** `GET /sports/basketball_ncaab/odds`
2. **Auth:** Add `?apiKey=YOUR_KEY` to request
3. **Rate:** 45 req/min, 2,000 req/month (MONITOR THIS!)
4. **Errors:** Retry with exponential backoff on 429 and 5xx
5. **Data:** Validate before storage, extract spreads/totals/h2h
6. **Monitoring:** Log requests remaining, alert if low

### Next Steps

- [ ] Review `BASKETBALL_API_ENDPOINTS_GUIDE.md`
- [ ] Review `BASKETBALL_API_IMPLEMENTATION.md`
- [ ] Run `testing/scripts/ingestion_healthcheck.py`
- [ ] Implement error handling if missing
- [ ] Check current poll frequency vs quota
- [ ] Add quota monitoring to your dashboard

---

**Last Updated:** December 20, 2025  
**Branch:** basketball-api-endpoints  
**Version:** 1.0 - QUICK REFERENCE

