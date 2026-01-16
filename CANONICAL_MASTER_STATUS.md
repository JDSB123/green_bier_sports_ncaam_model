# CANONICAL MASTER STATUS REPORT

**Date**: 2026-01-16
**Verified By**: Direct data inspection
**File**: `manifests/canonical_training_data_master.csv`

---

## EXECUTIVE SUMMARY

✅ **CONFIRMED**: Single source of truth architecture is correctly implemented
❌ **CRITICAL ISSUE**: Missing closing line data blocks CLV analysis
⚠️ **WARNING**: H1 data coverage insufficient for 2023 season
⚠️ **WARNING**: Team name canonicalization needs cleanup

---

## SINGLE SOURCE OF TRUTH - VERIFIED ✅

### Data File Status
- **Primary**: `manifests/canonical_training_data_master.csv` (4.1 MB)
- **Backup**: `manifests/canonical_training_data_master.bak_20260115_170639.csv` (timestamped, ignored)
- **No other CSV files** in manifests directory ✅

### Script References - ALL CORRECT ✅

All scripts correctly reference ONLY the canonical master:

1. **run_clv_backtest.py** (line 249)
   ```python
   local_master = self.root_dir / "manifests" / "canonical_training_data_master.csv"
   ```

2. **run_historical_backtest.py** (line 536)
   ```python
   local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
   ```

3. **train_independent_models.py** (line 36)
   ```python
   local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
   ```

4. **sync_canonical_master.py** (line 14)
   ```python
   LOCAL_PATH = "manifests/canonical_training_data_master.csv"
   AZURE_PATH = "canonical/canonical_training_data_master.csv"
   ```

5. **deploy_to_azure.py**
   ```python
   local_path = Path(__file__).resolve().parent / "manifests" / "canonical_training_data_master.csv"
   ```

**Result**: ✅ NO LEGACY FILE REFERENCES FOUND

---

## DATA COVERAGE ANALYSIS

### Dataset Overview
- **Total Games**: 3,339
- **Seasons**: 2023, 2024, 2025, 2026
- **Date Range**: 2022-11-07 to 2026-01-06
- **Columns**: 109

### Coverage by Season

| Season | Games | FG Odds | H1 Odds | Ratings |
|--------|-------|---------|---------|---------|
| 2023 | 1,095 | 81.2% ✓ | **0.0% ❌** | 89.3% ✓ |
| 2024 | 896 | 85.2% ✓ | 81.6% ✓ | 89.7% ✓ |
| 2025 | 932 | 84.3% ✓ | 82.8% ✓ | 85.9% ✓ |
| 2026 | 416 | 36.1% ⚠️ | 34.4% ⚠️ | 88.9% ✓ |

**Notes**:
- 2026 low coverage is expected (current/incomplete season)
- 2023 H1 data completely missing - CRITICAL GAP

### Market Coverage

| Market | Coverage | Status |
|--------|----------|--------|
| FG Spread | 2,588 / 3,339 (77.5%) | ✓ Good |
| FG Total | 2,580 / 3,339 (77.3%) | ✓ Good |
| FG Spread Prices | 2,588 / 3,339 (77.5%) | ✓ Good |
| FG Total Prices | 2,580 / 3,339 (77.3%) | ✓ Good |
| Moneyline Prices | 2,401 / 3,339 (71.9%) | ✓ Good |
| **H1 Spread** | 1,646 / 3,339 (49.3%) | ❌ Low |
| **H1 Total** | 1,634 / 3,339 (48.9%) | ❌ Low |
| **H1 Prices** | 1,646 / 3,339 (49.3%) | ❌ Low |

### Ratings Coverage (Barttorvik)

| Feature | Coverage | Status |
|---------|----------|--------|
| Adj Offensive Efficiency | 2,953 / 3,339 (88.4%) | ✓ Excellent |
| Adj Defensive Efficiency | 2,953 / 3,339 (88.4%) | ✓ Excellent |
| Barthag Rating | 2,953 / 3,339 (88.4%) | ✓ Excellent |
| Tempo | 2,953 / 3,339 (88.4%) | ✓ Excellent |
| eFG% | 2,953 / 3,339 (88.4%) | ✓ Excellent |
| Turnover Rate | 2,953 / 3,339 (88.4%) | ✓ Excellent |

**Data Leakage Check**: ✅ PASS - All ratings use prior season (N-1)

### Actual Results Coverage

| Result Type | Coverage | Status |
|-------------|----------|--------|
| FG Home Score | 3,339 / 3,339 (100%) | ✓ Perfect |
| FG Away Score | 3,339 / 3,339 (100%) | ✓ Perfect |
| H1 Home Score | 3,339 / 3,339 (100%) | ✓ Perfect |
| H1 Away Score | 3,339 / 3,339 (100%) | ✓ Perfect |
| All Margins & Totals | 3,339 / 3,339 (100%) | ✓ Perfect |

---

## CRITICAL ISSUES

### 1. NO CLOSING LINE DATA ❌ CRITICAL

**Impact**: CLV backtests cannot calculate sharpness metric

**Current State**:
- Zero closing line columns exist in dataset
- CLV backtest shows 0.0 for all bets
- Cannot validate if predictions beat the market

**Required Columns**:
```
fg_spread_closing
fg_total_closing
h1_spread_closing
h1_total_closing
```

**Evidence**:
```bash
$ grep -i closing canonical_training_data_master.csv
# No results
```

**Fix Priority**: **IMMEDIATE** - This is your stated "gold standard" metric

---

### 2. H1 2023 DATA MISSING ❌ CRITICAL

**Impact**: Cannot backtest H1 models on 2023 data (1,095 games lost)

**Current State**:
- 2023: 0 / 1,095 games (0.0%)
- 2024: 731 / 896 games (81.6%) ✓
- 2025: 772 / 932 games (82.8%) ✓

**Fix Priority**: **HIGH** - Limits historical validation window

---

### 3. TEAM NAME CANONICALIZATION ⚠️ WARNING

**Impact**: Potential team name mismatches, data quality issues

**Current State**:
- 366 unique canonical teams (should be ~350 for D1)
- Multiple canonical columns causing confusion:
  - `home_canonical` / `away_canonical`
  - `home_team_canonical_x` / `away_team_canonical_x`
  - `home_team_canonical_y` / `away_team_canonical_y`
  - `home_team_canonical_odds` (worst: 374 unique!)

**Scripts have fallback logic**:
```python
# From run_historical_backtest.py and run_clv_backtest.py
def _normalize_team_columns(df):
    home_candidates = [
        "home_team", "home_team_canonical", "home_team_canonical_x",
        "home_team_canonical_y", "home_team_canonical_odds", ...
    ]
    # Tries multiple columns - indicates inconsistency
```

**Fix Priority**: **MEDIUM** - Cleanup needed for data quality

---

## WHAT'S WORKING WELL ✅

1. **Single source of truth**: Perfectly implemented
2. **No data leakage**: Ratings properly use N-1 season
3. **Actual results**: 100% coverage across all games
4. **FG markets**: Strong 77%+ coverage
5. **Ratings data**: Excellent 88% coverage
6. **Script references**: All point to canonical master only

---

## RECOMMENDED ACTION PLAN

### Phase 1: Critical Fixes (Do First)

**Priority 1: Add Closing Lines**
- Fetch closing line data from odds API
- Add columns: `fg_spread_closing`, `fg_total_closing`, etc.
- Target: 70%+ coverage for all markets
- **Impact**: Enables CLV analysis (your gold standard)

**Priority 2: Backfill 2023 H1 Data**
- Source historical H1 odds from archive
- Target: 70%+ coverage for 2023 season
- **Impact**: Adds 1,095 games to H1 backtest window

### Phase 2: Cleanup

**Priority 3: Consolidate Team Names**
- Audit team name duplicates
- Pick ONE canonical column (recommend: `home_canonical`)
- Update all scripts to use single column
- Remove redundant columns (_x, _y, _odds variants)
- **Impact**: Cleaner data, fewer bugs

**Priority 4: Remove Redundant Columns**
- Document authoritative columns
- Remove merge artifacts
- Update schema documentation
- **Impact**: Reduced file size, clearer schema

### Phase 3: Validation

**Priority 5: Verify & Deploy**
- Re-run verification script
- Validate all fixes applied
- Sync to Azure
- Run full backtests
- **Impact**: Confidence in data quality

---

## VERIFICATION SCRIPT

Run anytime to check data quality:

```bash
python verify_canonical_master_quality.py
```

Output saved to timestamped logs for tracking improvements.

---

## CONCLUSION

✅ **Architecture is CORRECT** - single source of truth properly enforced
❌ **Data has GAPS** - closing lines missing, H1 2023 coverage 0%
🎯 **Next Step**: Add closing line data to enable CLV tracking

The governance structure is solid. Now we need to **fix the data itself**.

---

**Last Updated**: 2026-01-16
**Verified By**: verify_canonical_master_quality.py
