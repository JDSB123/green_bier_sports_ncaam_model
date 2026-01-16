# DATA ACQUISITION PLAN

**Date**: 2026-01-16
**Status**: Action Required - API Access Needed

---

## CRITICAL DATA GAPS

### 1. Closing Line Data (HIGHEST PRIORITY)

**Impact**: Blocks CLV (Closing Line Value) metric - your "gold standard" for model sharpness

**Current State**:
- 0 closing line columns in canonical master
- Only opening lines captured
- CLV backtests show 0.0 for all bets

**What's Needed**:
```
fg_spread_closing
fg_total_closing
fg_spread_closing_home_price
fg_spread_closing_away_price
fg_total_closing_over_price
fg_total_closing_under_price
h1_spread_closing
h1_total_closing
h1_spread_closing_home_price
h1_spread_closing_away_price
h1_total_closing_over_price
h1_total_closing_under_price
moneyline_closing_home_price
moneyline_closing_away_price
```

**Data Source Options**:

1. **The Odds API** (https://the-odds-api.com/)
   - Current infrastructure ready (OddsApiClient exists)
   - Requires API key: `secrets/odds_api_key.txt`
   - **Problem**: Historical closing lines not available in free tier
   - **Solution**: Upgrade to premium tier or capture prospectively

2. **Bovada** (via scraping/archive)
   - Known to have historical closing lines
   - May require scraping or third-party archive access
   - Legal/ToS considerations

3. **Pinnacle** (Closes sharp)
   - Gold standard for closing lines
   - Historical data may be available via specialized providers
   - Premium access likely required

4. **ActionNetwork** (credentials in secrets/)
   - May have historical closing line data
   - Already configured: `action_network_username.txt`, `action_network_password.txt`
   - Worth investigating their API

**Recommended Approach**:
1. Check if ActionNetwork API has historical closing lines
2. If not, obtain The Odds API premium key
3. Start capturing closing lines prospectively for 2026+ season
4. For historical (2023-2025), may need to accept limitation or find specialized provider

---

### 2. 2023 H1 (First Half) Data

**Impact**: Limits H1 model backtesting window by 1,095 games (33% of dataset)

**Current State**:
- 2023: 0 / 1,095 games (0.0%)
- 2024: 731 / 896 games (81.6%) ✓
- 2025: 772 / 932 games (82.8%) ✓
- 2026: 143 / 416 games (34.4%) (in-progress)

**What's Needed**:
```
h1_spread
h1_total
h1_spread_home_price
h1_spread_away_price
h1_total_over_price
h1_total_under_price
```
For all 1,095 games in 2023 season (2022-11-07 to 2023-04-03)

**Data Source Options**:

1. **The Odds API Historical**
   - May have 2023 H1 odds if captured at the time
   - Check with support if historical H1 data available

2. **Bovada Archive**
   - Sometimes has historical first-half lines
   - May require manual reconstruction

3. **Accept Limitation**
   - Use 2024-2026 for H1 model validation (2,508 games)
   - Still 75% of dataset available

**Recommended Approach**:
1. Contact The Odds API support to check historical H1 availability for 2023
2. If not available, document limitation and use 2024+ for H1 models
3. Prioritize prospective capture for 2026+ season

---

## IMPLEMENTATION STEPS

### Phase 1: Immediate (API Access Required)

1. **Obtain The Odds API Key**
   ```bash
   # Get key from https://the-odds-api.com/
   echo -n "YOUR_API_KEY" > secrets/odds_api_key.txt
   chmod 600 secrets/odds_api_key.txt
   ```

2. **Test API Access**
   ```python
   from services.prediction_service_python.app.odds_api_client import OddsApiClient
   client = OddsApiClient()
   events = client.get_events()
   print(f"Found {len(events)} upcoming games")
   ```

3. **Check Historical Data Availability**
   - Contact The Odds API support
   - Ask: "Do you have historical closing line data for NCAAB 2023-2025?"
   - Ask: "Do you have historical first-half lines for NCAAB 2023?"

### Phase 2: Prospective Capture (Can Start Immediately)

4. **Enable Closing Line Capture**
   - Modify odds ingestion pipeline to capture closing lines
   - Store alongside opening lines in canonical master
   - Run before game commence time

5. **Verify H1 Capture for 2026**
   - Ensure H1 lines being captured for current season
   - Target 80%+ coverage like 2024-2025

### Phase 3: Backfill (If Data Available)

6. **Backfill 2023-2025 Closing Lines**
   - If historical data available, create backfill script
   - Join to canonical master by game_id + event_id
   - Validate no data leakage (closing captured before commence)

7. **Backfill 2023 H1 Lines**
   - If historical data available, add to canonical master
   - Target 70%+ coverage

---

## ALTERNATIVE: WORK WITHOUT CLOSING LINES

If closing line data proves too expensive/unavailable:

**Option A: Use Opening Lines as Proxy**
- Rename `fg_spread` → `fg_spread_opening`
- Add `fg_spread_closing` = `fg_spread_opening` (assume unchanged)
- **Limitation**: CLV metric less meaningful if lines don't move

**Option B: Focus on Win Rate / ROI Only**
- Skip CLV metric entirely
- Validate models on actual win rate and ROI
- Document that sharpness (CLV) not measurable

**Option C: Synthetic Closing Lines**
- For games where we have results, reverse-engineer likely closing lines
- Use betting market efficiency assumptions
- **Limitation**: Synthetic, not actual market data

---

## COST ESTIMATE

**The Odds API Pricing** (as of 2025):
- Free tier: 500 requests/month (opening lines only)
- Premium: $99-199/month (historical + closing lines likely extra)
- Enterprise: Custom pricing (full historical archive)

**Recommendation**:
- Start with free tier for prospective capture
- Evaluate premium if historical data needed
- May be worth $100-200/month for quality closing line data

---

## ACTION ITEMS

**Required Before Proceeding**:
- [ ] Obtain The Odds API key (free or premium)
- [ ] Add key to `secrets/odds_api_key.txt`
- [ ] Test API access
- [ ] Confirm historical data availability with support

**Once API Access Confirmed**:
- [ ] Create script: `add_closing_lines_to_canonical.py`
- [ ] Create script: `backfill_2023_h1_odds.py`
- [ ] Update canonical master schema
- [ ] Re-deploy to Azure
- [ ] Re-run CLV backtests

---

**Next Step**: User needs to obtain The Odds API key before data acquisition can proceed.
