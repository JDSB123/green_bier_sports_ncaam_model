# CANONICAL MASTER DATA FIX PLAN

**Status**: Data verified via direct inspection on 2026-01-15
**Current File**: `manifests/canonical_training_data_master.csv` (3,339 rows, 109 columns)

## VERIFIED ISSUES

### 1. NO CLOSING LINE DATA (CRITICAL - BLOCKS CLV)
**Impact**: CLV backtests cannot measure sharpness (your "gold standard" metric)

**Current State**:
- No columns with "closing" in name exist
- CLV backtest shows 0.0 CLV for all bets
- Cannot validate if predictions beat the closing line

**Required Columns**:
```
fg_spread_closing
fg_total_closing
h1_spread_closing
h1_total_closing
moneyline_home_price_closing (optional)
moneyline_away_price_closing (optional)
```

**Action**:
- Fetch closing line data from odds API (The Odds API or similar)
- Join to canonical master by `canonical_game_id` or `event_id`
- Ensure closing lines are captured at/before `commence_time`

---

### 2. H1 COVERAGE TOO LOW (49.3% - CRITICAL)
**Impact**: H1 models unusable for 2023, unreliable for backtesting

**Current Coverage by Season**:
- 2023: 0 / 1,095 (0.0%) ❌ COMPLETELY MISSING
- 2024: 731 / 896 (81.6%) ✓ Good
- 2025: 772 / 932 (82.8%) ✓ Good
- 2026: 143 / 416 (34.4%) ⚠️ In progress (current season)

**Action**:
- Backfill 2023 H1 data from historical odds sources
- Priority: Get 2023 to 70%+ coverage
- Validate H1 actual results exist (currently at 100% - good)

---

### 3. TEAM NAME CANONICALIZATION (HIGH PRIORITY)
**Impact**: Team name mismatches cause model errors, data quality issues

**Current State**:
- 366 unique canonical teams (should be ~350 for D1)
- Multiple canonical columns exist:
  - `home_canonical` / `away_canonical` (366 unique)
  - `home_team_canonical_x` / `away_team_canonical_x` (333 unique)
  - `home_team_canonical_y` / `away_team_canonical_y` (291 unique)
  - `home_team_canonical_odds` (374 unique) ❌ Worst

**Scripts use different columns**:
- `run_historical_backtest.py` uses `home_team`, falls back to `home_team_canonical`
- `run_clv_backtest.py` uses `home_team`, falls back to `home_team_canonical`
- Inconsistent usage = potential bugs

**Action**:
1. **Audit team names**: Find duplicates (e.g., "Duke" vs "Duke Blue Devils")
2. **Pick ONE canonical column**: Recommend `home_canonical` / `away_canonical`
3. **Update all scripts**: Remove fallback logic, use only canonical columns
4. **Remove redundant columns**: Delete `_x`, `_y`, `_odds` variants
5. **Validate**: Should have exactly ~350 unique teams

---

### 4. REDUNDANT COLUMNS (CLEANUP)
**Impact**: Confusion, increased file size, merge artifacts

**Columns to investigate/remove**:
```
home_team_x vs home_team_original vs home_team_canonical_x/y
spread_price (redundant with fg_spread_home_price/away_price?)
h1_spread_price (redundant with h1_spread_home_price/away_price?)
```

**Action**:
- Document which column is authoritative
- Remove merge artifacts (_x, _y suffixes)
- Update schema documentation

---

## IMPLEMENTATION PLAN

### Phase 1: CRITICAL FIXES (Do First)
1. ✅ Verify current state (DONE - ran verification script)
2. ☐ Add closing line data columns
   - Fetch from odds API
   - Validate coverage >= 70% for each market
3. ☐ Backfill 2023 H1 data
   - Target: 70%+ coverage
4. ☐ Consolidate team canonicalization
   - Pick authoritative column
   - Update all scripts

### Phase 2: CLEANUP & VALIDATION
5. ☐ Remove redundant columns
6. ☐ Update all script references
7. ☐ Re-run verification script
8. ☐ Sync to Azure

### Phase 3: VALIDATION
9. ☐ Run full backtests with fixed data
10. ☐ Verify CLV calculations work
11. ☐ Document final schema

---

## SCRIPTS TO UPDATE

All scripts currently load canonical master correctly, but need updates for:

### Team Name References:
- `testing/scripts/run_clv_backtest.py:52-77` (_normalize_team_columns)
- `testing/scripts/run_historical_backtest.py:46-71` (_normalize_team_columns)
- Any script using `home_team` / `away_team` columns

### After fixes:
- Remove `_normalize_team_columns()` functions
- Use `home_canonical` / `away_canonical` directly
- No fallback logic needed

---

## CURRENT DATA QUALITY SUMMARY

| Metric | Coverage | Status |
|--------|----------|--------|
| Total Games | 3,339 | ✓ |
| Seasons | 2023-2026 | ✓ |
| FG Spread | 77.5% | ✓ Good |
| FG Total | 77.3% | ✓ Good |
| H1 Spread | 49.3% | ❌ Low |
| H1 Total | 48.9% | ❌ Low |
| Moneyline | 71.9% | ✓ Good |
| Ratings (Barttorvik) | 88.4% | ✓ Good |
| Actual Results | 100% | ✓ Perfect |
| Closing Lines | 0% | ❌ MISSING |
| Team Canonicalization | ~366 teams | ⚠️ High |

---

## SUCCESS CRITERIA

After fixes, verification script should show:

- ✓ Closing line coverage >= 70% for FG markets
- ✓ H1 spread/total coverage >= 70% for all seasons 2023+
- ✓ Exactly ~350 unique canonical teams
- ✓ Single team canonical column used everywhere
- ✓ No redundant/merge artifact columns
- ✓ CLV backtests show actual CLV values (not 0.0)

---

**Next Step**: Start with Phase 1, Item 2 - Add closing line data
