# Basketball API Analysis - Critical Findings Report
## NCAAM Integration Review & Recommendations

**Date:** December 20, 2025  
**Branch:** basketball-api-endpoints  
**Status:** ANALYSIS COMPLETE

> **Update (manual-only mode):** The current stack is **manual-only** (no continuous polling).
> Odds/rates are synced **one-shot** when you run `predict.bat` / `run_today.py`.
> The quota math below is still useful if you ever re-enable polling, but it is **not the default behavior**.

---

## 🔴 CRITICAL ISSUES IDENTIFIED

### Issue #1: QUOTA EXCEEDING ⚠️ URGENT

**Status:** 🔴 **CRITICAL - Will fail production**

**Problem:**
Your current polling frequency **EXCEEDS your monthly quota by 4,320 requests!**

```
Legacy Polling Configuration (polling-enabled; **NOT** the manual-only default):
- Poll Interval: 30 seconds
- Requests/hour: 120 (30s × 60 min)
- Requests/day: 2,880 (120 × 24 hours)
- Requests/month (30 days): 86,400

Your API Tier:
- Monthly Quota: 2,000 requests
- Daily Budget: ~67 requests (2,000 ÷ 30)

Result:
86,400 actual ÷ 2,000 quota = 43.2x OVER LIMIT
Will hit monthly quota in ~12.5 hours of operation!
```

**Solution Options:**

**Option A: Reduce Poll Frequency (COST: $0)**
```
New interval: Every 5 minutes
- Requests/day: 288
- Requests/month: 8,640
- ✅ Still exceeds but by 4.3x (manageable with event filtering)

Better: Every 10 minutes
- Requests/day: 144
- Requests/month: 4,320
- ✅ Still exceeds but by 2.16x

Best: Every 15 minutes
- Requests/day: 96
- Requests/month: 2,880
- ✅ Still slightly over but close

OPTIMAL: Every 20 minutes
- Requests/day: 72
- Requests/month: 2,160
- ✅ Just under quota!
```

**Option B: Upgrade API Tier (COST: $20/month)**
```
Professional Tier:
- 100 requests/minute (vs 45)
- 10,000 requests/month (vs 2,000)
- Can keep 30-second polling
- Cost: ~$20/month
```

**Option C: Implement Event-Driven Polling (COST: $0, COMPLEXITY: High)**
```
Strategy:
1. Get events list first (lightweight)
2. Only fetch odds for NEW/UPCOMING games
3. Skip unchanged games

Estimated Reduction: 70-80% fewer requests
Result: Sustainable polling within quota
```

**Recommendation:** **IMPLEMENT OPTION C OR B BEFORE PRODUCTION**

---

### Issue #2: Missing Error Recovery Patterns ⚠️ HIGH

**Status:** 🟠 **HIGH - System will crash on API errors**

**Problem:**
Current Rust service has retry logic, but Python test script has basic handling.
Production code needs consistent, robust error handling across all components.

**What's Missing:**
1. ❌ Fallback to cached data when API fails
2. ❌ Circuit breaker for repeated failures
3. ❌ Graceful degradation (use stale data rather than crash)
4. ❌ Health check endpoint for monitoring
5. ❌ Detailed error logging for debugging

**Impact:**
- If API is down for 1 hour: Your system crashes
- If rate limited: System fails rather than backing off
- If network timeout: No retry, immediate failure

**Solution:**
See `BASKETBALL_API_IMPLEMENTATION.md` for production patterns including:
- Exponential backoff with jitter
- Circuit breaker pattern
- Cached data fallback
- Health monitoring

---

### Issue #3: Rate Limit Not Proactively Enforced ⚠️ MEDIUM

**Status:** 🟠 **MEDIUM - Will hit limits in production**

**Problem:**
Current code has rate limiter in Rust (45 req/min), but:
1. Doesn't prevent monthly quota exhaustion
2. No quota warning system
3. No alerting when approaching limits
4. No automatic poll frequency adjustment

**Example Scenario:**
```
Day 1: Use 2,000 quota
Day 2 (8:00 AM): All remaining quota exhausted
Day 2 (8:01 AM): All API calls start returning 403 errors
Rest of month: System completely broken
```

**Solution:**
Implement quota tracking:
```python
# Monitor response headers
remaining = int(response.headers.get("x-requests-remaining", 0))

if remaining < 100:
    logger.warning("⚠️ LOW QUOTA: {} requests remaining".format(remaining))
    # Send alert to monitoring system

if remaining < 50:
    logger.critical("🔴 CRITICAL: {} requests remaining".format(remaining))
    # Automatically reduce poll frequency or pause
```

---

### Issue #4: Data Validation Gaps ⚠️ MEDIUM

**Status:** 🟠 **MEDIUM - Could corrupt database**

**Problem:**
Current code doesn't fully validate API responses before storing:
1. No check for malformed game objects
2. No validation of team names (could have typos)
3. No validation of odds values
4. No detection of duplicate games
5. No check for data freshness

**Impact:**
- Bad data in database
- Corrupted predictions
- Stale odds used for edge calculations
- Team name mismatches

**Solution:**
See validation patterns in `BASKETBALL_API_IMPLEMENTATION.md`:
```python
def validate_game(game):
    assert game["sport_key"] == "basketball_ncaab"
    assert game["id"]
    assert game["home_team"]
    assert game["away_team"]
    for bookmaker in game["bookmakers"]:
        for market in bookmaker["markets"]:
            assert market["key"] in ["spreads", "totals", "h2h"]
```

---

## 🟡 IMPORTANT OBSERVATIONS

### Observation #1: Multiple Endpoints Available But Underutilized

**Finding:**
The Odds API provides 5 main endpoints, but your system only uses 1:

| Endpoint | Your Usage |
|----------|-----------|
| `/odds` | ✅ ACTIVE (every 30s) |
| `/events` | ❌ UNUSED |
| `/odds/{id}` | ❌ UNUSED |
| `/scores` | ❌ UNUSED |
| `/sports` | ❌ UNUSED |

**Opportunity:**
Could optimize by:
1. Using `/events` first to find new games (cheaper)
2. Only fetching `/odds` for games that changed
3. Result: 70-80% fewer requests

**Example:**
```python
# Current (expensive): Fetch all odds every 30s
for i in range(1000):
    games = fetch_all_odds()  # 1 request each = 1000 total

# Optimized (cheap): Check for new games first
for i in range(1000):
    events = fetch_events()   # 1 request each = 1000 total
    new_games = filter_new(events)
    for game in new_games:
        odds = fetch_single_odds(game.id)  # 10-50 requests
```

### Observation #2: Sportsbook Consolidation Not Used

**Finding:**
API returns odds from multiple sportsbooks:
- FanDuel
- DraftKings
- BetMGM
- PointsBet
- Etc.

But your prediction system only cares about finding edges between YOUR predictions and MARKET odds. No need to process all sportsbooks.

**Opportunity:**
Could filter to just major sportsbooks in API request:
```python
params = {
    "bookmakers": "fanduel,draftkings"  # Only these
}
# Result: Smaller response, faster processing
```

### Observation #3: Market Type Filtering

**Finding:**
You request all markets: `spreads,totals,h2h`

But your CLV calculation uses:
- Spreads (to compare vs model point spread prediction)
- Totals (to compare vs model total prediction)
- Moneyline (less critical)

**Opportunity:**
Could optimize to just what's needed:
```python
params = {
    "markets": "spreads,totals"  # Skip h2h if not used
}
```

---

## ✅ WHAT'S WORKING WELL

### Positive #1: Error Handling in Rust Service

**Assessment:** ✅ **GOOD**

The Rust odds-ingestion service has solid error handling:
- Exponential backoff implemented correctly
- Respects Retry-After header
- Rate limiter in place
- Timeout handling
- Logging of errors

**Recommendation:** Model Python/database code after this pattern.

### Positive #2: Test Harness Ready

**Assessment:** ✅ **GOOD**

The `ingestion_healthcheck.py` script is well-written:
- Tests both APIs (Barttorvik + Odds)
- Good error messages
- Handles missing API keys gracefully
- Shows remaining quota

**Recommendation:** Keep and extend this for continuous monitoring.

### Positive #3: Data Structure Well Understood

**Assessment:** ✅ **GOOD**

Your Rust code correctly models the Odds API response:
```rust
pub struct OddsApiEvent {
    pub id: String,
    pub sport_key: String,
    pub home_team: String,
    pub away_team: String,
    pub bookmakers: Vec<Bookmaker>,
}
```

This matches the actual API response perfectly.

---

## 🎯 IMPLEMENTATION PRIORITIES

### Priority 1: URGENT (Before Next Launch)

1. **[ ] FIX QUOTA ISSUE** (Issue #1)
   - Implement Option C (event-driven) OR Option B (upgrade tier)
   - Add quota monitoring and alerting
   - Test under sustained load

2. **[ ] ADD ERROR RECOVERY** (Issue #2)
   - Implement circuit breaker
   - Add fallback to cached data
   - Add health check endpoint
   - Comprehensive error logging

### Priority 2: HIGH (This Week)

1. **[ ] DATA VALIDATION** (Issue #4)
   - Validate all game objects before storage
   - Detect and skip malformed data
   - Log validation failures

2. **[ ] MONITORING DASHBOARD** (Issue #3)
   - Display remaining API quota
   - Show request rates and errors
   - Alert on approaching limits
   - Daily quota report

### Priority 3: MEDIUM (This Month)

1. **[ ] OPTIMIZE POLLING** (Observation #1)
   - Implement event-driven polling
   - Test quota reduction
   - Measure request savings

2. **[ ] CONSOLIDATE SPORTSBOOKS** (Observation #2)
   - Analyze which sportsbooks you actually use
   - Filter API request to just those
   - Measure response size reduction

---

## 📋 Deployment Checklist

Before deploying to production:

```
CRITICAL (MUST FIX):
[ ] Quota issue resolved (polling frequency optimized)
[ ] Rate limit enforcement in place
[ ] Error handling covers all failure modes
[ ] Fallback to cached data implemented

HIGH PRIORITY:
[ ] Data validation before storage
[ ] Quota monitoring active
[ ] Health check endpoint working
[ ] Error logging comprehensive

NICE TO HAVE:
[ ] Event-driven polling implemented
[ ] Sportsbook filtering optimized
[ ] Market type filtering optimized
[ ] Monitoring dashboard live

TESTING:
[ ] Health check passes
[ ] Rate limit tested (make 50 rapid requests)
[ ] Error handling tested (simulate 429, 5xx)
[ ] Quota tracking verified
[ ] Data validation catches bad data
[ ] Fallback cache works
[ ] System runs 24 hours without failure
[ ] Monthly quota not exceeded
```

---

## 📊 Current State vs. Target State

### Current State (As of December 20, 2025)

```
✅ API endpoint implemented
✅ Basic retry logic in place
✅ Rust service has rate limiting
❌ Monthly quota will be exceeded
❌ No fallback on API failure
❌ Minimal error recovery
❌ No quota monitoring
❌ No health checks
❌ Limited data validation
```

### Target State (Production Ready)

```
✅ API optimized (event-driven or upgraded tier)
✅ Robust error handling with multiple retries
✅ Circuit breaker for repeated failures
✅ Monthly quota guaranteed not exceeded
✅ Fallback to cached data when API fails
✅ Quota monitoring and alerts
✅ Health check endpoint
✅ Comprehensive data validation
✅ Detailed logging and monitoring
✅ Tested under sustained load
```

---

## 🚀 Next Steps

### Immediate (Today)

1. ✅ **Review all 3 new documentation files:**
   - `BASKETBALL_API_ENDPOINTS_GUIDE.md` (complete endpoint reference)
   - `BASKETBALL_API_IMPLEMENTATION.md` (code patterns)
   - `BASKETBALL_API_QUICK_REFERENCE.md` (quick lookup)

2. ✅ **Understand the quota problem:**
   - Current polling: 43x over quota
   - Need to reduce frequency OR upgrade tier

3. ✅ **Verify test script works:**
   ```bash
   python testing/scripts/ingestion_healthcheck.py
   ```

### This Week

1. **Choose quota solution:**
   - Option A: Event-driven polling (recommend)
   - Option B: Reduce poll frequency to 20 minutes
   - Option C: Upgrade to Professional tier ($20/month)

2. **Implement error recovery:**
   - Copy patterns from `BASKETBALL_API_IMPLEMENTATION.md`
   - Add circuit breaker
   - Add quota monitoring

3. **Add data validation:**
   - Use validation patterns from implementation guide
   - Test with both valid and invalid data

### Before Production Deployment

1. Test full error scenarios
2. Verify quota tracking
3. Confirm fallback cache works
4. Run 24-hour soak test
5. Monitor quota usage carefully
6. Have rollback plan ready

---

## 📞 Questions & Support

### For Understanding the Endpoints

See: `docs/BASKETBALL_API_ENDPOINTS_GUIDE.md`
- All 5 endpoints documented
- Parameters explained
- Response structures detailed
- Error codes referenced

### For Implementation Code

See: `docs/BASKETBALL_API_IMPLEMENTATION.md`
- Async client (Python)
- Sync client (Python)
- Data validation
- Error handling patterns
- Complete examples

### For Quick Lookup

See: `docs/BASKETBALL_API_QUICK_REFERENCE.md`
- Common error codes
- Data structure reference
- Rate limit info
- Testing procedures
- Checklist

---

## Summary Table

| Issue | Severity | Fix | Effort | Timeline |
|-------|----------|-----|--------|----------|
| Quota exceeded | 🔴 CRITICAL | Reduce poll OR upgrade | Medium | Today |
| Error recovery missing | 🟠 HIGH | Implement patterns | Medium | This week |
| Data validation gaps | 🟠 MEDIUM | Add validation | Low | This week |
| Quota monitoring missing | 🟠 MEDIUM | Add tracking | Low | This week |
| Polling not optimized | 🟡 MEDIUM | Event-driven | High | Next month |

---

**Last Updated:** December 20, 2025  
**Analysis Complete:** ✅  
**Documentation:** 3 comprehensive guides created  
**Branch:** basketball-api-endpoints

**Status:** Ready for review and implementation

# NCAAM Odds API Pipeline (Repeatable Path)

This guide defines a clear, configurable, and repeatable path to pull all available NCAAM markets from your Premium The Odds API subscription. It uses the existing Rust ingestion service with environment-driven settings, keeping the pipeline robust and easy to extend.

## Overview
- Service: services/odds-ingestion-rust (Rust)
- Entry points:
  - Full-game odds: /v4/sports/{sport_key}/odds
  - Per-event odds (1H/2H): /v4/sports/{sport_key}/events/{event_id}/odds
- Storage: PostgreSQL/TimescaleDB (`odds_snapshots`), joined to `games` and `teams`
- Streaming: Redis Streams (`odds.live`)
- Orchestration: run via Python `run_today.py` or container start script

## Sport & Markets
- Default `sport_key`: `basketball_ncaab`
- Full-game markets: spreads, totals, h2h
- First half markets (premium): spreads_h1, totals_h1, h2h_h1
- Second half markets: spreads_h2, totals_h2, h2h_h2
- Bookmaker preferences:
  - H1: `bovada,pinnacle,circa,bookmaker`
  - H2: `draftkings,fanduel,pinnacle,bovada`

All of the above are now configurable via environment variables to cover additional/remaining markets as your subscription allows.

## Configuration (Env Vars)
Set these to tailor coverage without code changes:
- `SPORT_KEY`: override sport key (default: `basketball_ncaab`)
- `REGIONS`: odds regions (default: `us`)
- `ODDS_FORMAT`: odds format (default: `american`)
- `MARKETS_FULL`: full-game markets comma list (default: `spreads,totals,h2h`)
- `MARKETS_H1`: first-half markets (default: `spreads_h1,totals_h1,h2h_h1`)
- `MARKETS_H2`: second-half markets (default: `spreads_h2,totals_h2,h2h_h2`)
- `BOOKMAKERS_H1`: preferred books for H1 (default: `bovada,pinnacle,circa,bookmaker`)
- `BOOKMAKERS_H2`: preferred books for H2 (default: `draftkings,fanduel,pinnacle,bovada`)
- `RUN_ONCE`: **manual-only** (always `true` in this repo; service runs once and exits)
- `POLL_INTERVAL_SECONDS`: **unused** (continuous polling is disabled)

Secrets are read from Docker secrets or environment variables:

**Docker Compose (default):**
- `/run/secrets/odds_api_key` → The Odds API key (from `secrets/odds_api_key.txt`)
- `/run/secrets/db_password` → database password (from `secrets/db_password.txt`)
- `/run/secrets/redis_password` → redis password (from `secrets/redis_password.txt`)

**Azure Container Apps:**
- Environment variable `THE_ODDS_API_KEY` → The Odds API key
- Environment variable `DATABASE_URL` → PostgreSQL connection string
- Environment variable `REDIS_URL` → Redis connection string

Get your The Odds API key from: https://the-odds-api.com/

## Repeatable Run Paths

### One-shot (fast CLI run)
- Purpose: Pull full-game markets rapidly for daily predictions.
- Behavior: Skips per-event half markets to avoid long runs/timeouts.
- How to run:
```bash
export RUN_ONCE=true
# Optional overrides
export MARKETS_FULL="spreads,totals,h2h" # add/remove markets as needed
python services/prediction-service-python/run_today.py
```

### Continuous (daemon)
- **Not supported in this repo** (manual-only mode; no background polling/daemons).
- How to run (in container):
```bash
# Example overrides; adjust to cover remaining markets/books supported by premium plan
export REGIONS="us"
export ODDS_FORMAT="american"
export MARKETS_FULL="spreads,totals,h2h"
export MARKETS_H1="spreads_h1,totals_h1,h2h_h1"
export MARKETS_H2="spreads_h2,totals_h2,h2h_h2"
export BOOKMAKERS_H1="bovada,pinnacle,circa,bookmaker"
export BOOKMAKERS_H2="draftkings,fanduel,pinnacle,bovada"
# Start app per your orchestrator (Compose/K8s/ACA)
```

## Extending Coverage (Remaining Endpoints/Markets)
- To add new markets (e.g., alternates or other period-specific markets), set the corresponding env var lists:
  - Include supported market keys in `MARKETS_FULL`, `MARKETS_H1`, `MARKETS_H2`.
  - Optionally refine `BOOKMAKERS_H1`/`BOOKMAKERS_H2` to target books known to publish those markets.
- If your premium plan includes additional per-event markets beyond 1H/2H, add them to the appropriate env list. The ingestion service will normalize them when keys match the Odds API market naming conventions.
- If props or other specialty markets are enabled for NCAAM on your plan, create a separate run profile with dedicated env vars listing those market keys to avoid exceeding rate limits.

## Rate Limits & Reliability
- Built-in rate limiting: 45 req/min (per The Odds API guidance)
- Retries: Exponential backoff; honors `Retry-After` when provided
- H1/H2 handling: gracefully skips events where half markets are unavailable
- Diagnostics: health server exposes `/health` (port via `HEALTH_PORT`, default 8083)

## Data Flow & Storage
- Normalize teams before writing games and odds; aliases stored from The Odds API names
- Snapshots stored in `odds_snapshots` with unique key on `(time, game_id, bookmaker, market_type, period)` and upsert semantics
- Preferred bookmaker selection happens at query time in `run_today.py` using `latest_odds` CTEs

## Validation & Health
- Run ingestion health check:
```bash
python testing/scripts/ingestion_healthcheck.py --sport-key basketball_ncaab
```
- Inspect health endpoint:
```bash
curl http://localhost:8083/health
```

## Notes
- Avoid hardcoding markets/bookmakers in code; use env vars for flexibility.
- For high coverage of all remaining markets under your premium plan, maintain a documented set of env var profiles (e.g., full-game only, full+1H, full+1H+2H, specialty markets) and schedule runs accordingly.
- Keep an eye on The Odds API rate limits; split runs or stagger per-event requests if expanding market lists significantly.
