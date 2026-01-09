# Data Matching Integrity Verification Guide

## Overview

This document explains how to **confirm that all data sources are matched correctly** by team, date, and season while **preventing data leakage and bias**.

---

## 1. TEAM MATCHING VERIFICATION

### Single Source of Truth: ProductionTeamResolver

All team name resolution uses **4-step exact matching** (no fuzzy matching to prevent false positives):

```python
from testing.production_parity.team_resolver import ProductionTeamResolver

resolver = ProductionTeamResolver()
result = resolver.resolve("Tennessee")  # Returns canonical name
```

**Resolution Steps (in order):**
1. **Step 1 (CANONICAL)**: Exact match on canonical name (case-insensitive)
   - "Tennessee" → "Tennessee" ✅
   
2. **Step 2 (ALIAS)**: Exact match on alias list (case-insensitive)
   - "Tennessee St" → "Tennessee St." ✅
   - "ETSU" → "East Tennessee St." ✅

3. **Step 3 (NORMALIZED)**: Match after removing punctuation/whitespace
   - "Tennessee   St." → "Tennessee St." ✅

4. **Step 4 (MASCOT_STRIPPED)**: Match after removing common mascot suffixes
   - "Tennessee Volunteers" → "Tennessee" ✅
   - "Alabama Crimson Tide" → "Alabama" ✅

**If all 4 steps fail: REJECT (return None)**
- "Tennessee State" ≠ "Tennessee" (prevents false match)
- "Random University" → None (not found)

### Cross-Source Team Matching Validation

**Run to verify all sources resolve correctly:**

```bash
# Validate canonicalization accuracy (exact matches across sources)
python testing/scripts/validate_team_canonicalization.py

# Audit team aliases for integrity (no conflicting aliases)
python testing/scripts/audit_team_aliases.py

# Test today's games across all sources
python services/prediction-service-python/scripts/test_today_team_matching.py
```

**What these validate:**
- ✅ All team names from Odds API resolve to canonical names
- ✅ All team names from ESPN resolve to canonical names
- ✅ All team names from Barttorvik resolve to canonical names
- ✅ For same game: All sources resolve to **SAME canonical names**
- ✅ No alias conflicts (same alias pointing to different canonicals)
- ✅ No orphan aliases (aliases pointing to non-existent canonicals)
- ✅ No duplicate canonical names
- ✅ No fuzzy matching false positives

---

## 2. DATE & SEASON MATCHING VERIFICATION

### Season Definition (Critical!)

**All data uses consistent season definition:**

```python
# Season = championship year
# NCAA basketball seasons run November - April

season = date.year + 1 if date.month >= 11 else date.year

# Examples:
# 2024-01-15 → Season 2024 (2023-24 season)
# 2023-11-25 → Season 2024 (2023-24 season)
# 2023-03-18 → Season 2023 (2022-23 season)
```

### Date-Season Alignment Audit

**Run to verify season assignment is consistent:**

```bash
# Check historical data for season consistency
python testing/scripts/validate_canonical_odds.py

# Verify games/odds/ratings have matching seasons
grep -r "season = " testing/production_parity/
```

**What this validates:**
- ✅ All games have correct season assignment (Nov-Apr → current season, May-Oct → next season)
- ✅ Odds data season matches game date season
- ✅ Ratings season matches game date season
- ✅ No games from future seasons used for past games
- ✅ Timestamp parsing is consistent (CST timezone)

### CST Timezone Standardization

**All timestamps standardized to America/Chicago (CST):**

```python
from testing.production_parity.timezone_utils import (
    parse_date_to_cst,
    get_season_for_game,
)

# Convert any timestamp to CST date
cst_date = parse_date_to_cst("2024-01-15T08:00:00Z")  # UTC → CST

# Determine game season from CST date
season = get_season_for_game("2024-01-15")  # Returns 2024
```

---

## 3. ANTI-LEAKAGE VERIFICATION (NO FUTURE DATA)

### The Critical Anti-Leakage Rule

**Season N games ONLY use Season N-1 FINAL ratings**

```
Game Date    Game Season    Ratings Season    Why
─────────────────────────────────────────────────────────
2024-01-15   2024          2023 FINAL        ✅ Use prior season
2023-11-20   2024          2023 FINAL        ✅ Use prior season
2023-03-18   2023          2022 FINAL        ✅ Use prior season
2023-04-15   2023          2022 FINAL        ✅ Use prior season (tournament is end of season)
```

### Why Anti-Leakage Matters

**Using wrong ratings causes artificial performance inflation:**

```
WRONG (Data Leakage):
  Predict game on Nov 15, 2024 using Barttorvik 2024 end-of-season ratings
  Problem: Ratings include games from Dec 2024 - Apr 2025 (future data!)
  Result: Win rate inflates by 5-10+ percentage points

CORRECT (No Leakage):
  Predict game on Nov 15, 2024 using Barttorvik 2023 final ratings
  Benefit: Simulates real betting conditions (current data only)
  Result: Honest performance metrics
```

### Anti-Leakage Implementation

**All backtests automatically enforce anti-leakage:**

```python
from testing.production_parity.ratings_loader import AntiLeakageRatingsLoader

loader = AntiLeakageRatingsLoader()

# AUTOMATIC: Converts game season to ratings season
ratings = loader.get_ratings_for_game(
    team_name="Duke",
    game_date="2024-01-15"  # Game is Season 2024
)
# Internally: Uses 2023 FINAL ratings (N-1 rule)
```

### Anti-Leakage Audit

**Verify anti-leakage enforcement:**

```bash
# Check that pre_backtest_gate includes anti-leakage validation
python testing/scripts/pre_backtest_gate.py --verbose

# Test Anti-Leakage ratings loader
python -c "
from testing.production_parity.ratings_loader import AntiLeakageRatingsLoader
loader = AntiLeakageRatingsLoader()
# Tests include checking game_season vs ratings_season
loader._test_anti_leakage()
"
```

**What this validates:**
- ✅ Game Season 2024 → Uses Ratings Season 2023
- ✅ Game Season 2023 → Uses Ratings Season 2022
- ✅ Nov-Dec 2023 games → Uses 2023 ratings (current season Nov-Dec)
- ✅ No ratings from after game date are used
- ✅ No forward-looking information in predictions

---

## 4. CROSS-SOURCE JOIN VERIFICATION

### Game Matching Keys

**Games are matched across sources using composite keys:**

```python
# Matchup key = unique game identifier
matchup_key = (
    home_team_canonical,      # Must match exactly
    away_team_canonical,      # Must match exactly
    game_date,                # Must match (within ±1 day for time zone)
    bookmaker,                # For odds-specific joins
    season                    # Must match
)
```

### Cross-Source Join Logic

**Example: Match odds data to game results**

```python
# Load data
odds_df = pd.read_csv("canonical_odds.csv")
scores_df = pd.read_csv("canonical_scores.csv")

# Join on composite key
joined = odds_df.merge(
    scores_df,
    on=["home_team_canonical", "away_team_canonical", "game_date", "season"],
    how="inner"  # INNER JOIN = only matches
)

# Validate join completeness
print(f"Odds records: {len(odds_df):,}")
print(f"Score records: {len(scores_df):,}")
print(f"Matched records: {len(joined):,}")

# Calculate match rate
match_rate = len(joined) / min(len(odds_df), len(scores_df))
assert match_rate > 0.98, f"Match rate {match_rate} < 98%!"  # Alert if <98% match
```

### Cross-Source Join Validation

**Run to verify all joins are correct:**

```bash
# Validate canonical odds (check matchup keys and team consistency)
python testing/scripts/validate_canonical_odds.py

# Check that all games can be joined
python testing/scripts/validate_game_matching.py
```

**What this validates:**
- ✅ Teams resolve consistently within each game
- ✅ Home/away assignment is correct
- ✅ Spread signs match home/away designation
- ✅ Totals match between odds and game results
- ✅ Half-time (H1) scores match between odds and game results
- ✅ No games are missing due to mismatched team names
- ✅ No duplicate records due to bad joins

---

## 5. PRE-BACKTEST VALIDATION GATE

### Run Complete Validation Pipeline

**Before any backtest, run the pre-backtest gate:**

```bash
# Run all validation audits at once
python testing/scripts/pre_backtest_gate.py --verbose

# Or with specific options
python testing/scripts/pre_backtest_gate.py \
    --verbose \
    --create-snapshot \
    --skip-coverage  # Skip slow cross-source validation if running frequently
```

**This runs 4 mandatory audits:**

1. **Score Integrity Audit**
   - Validates score data across sources
   - Checks for duplicate rows
   - Verifies score totals

2. **Dual Canonicalization Audit**
   - Tests ProductionTeamResolver on sample games
   - Verifies all sources resolve correctly
   - Checks cross-source consistency

3. **Cross-Source Coverage Validation** (Optional - slower)
   - Confirms every game has odds/ratings/H1 data
   - Checks date alignment
   - Validates season assignment

4. **Canonical Manifest Generation**
   - Creates reproducibility snapshot
   - Records file checksums
   - Documents data versions

**Exit codes:**
- `0` = All audits passed ✅
- `1` = One or more audits failed ❌

---

## 6. AUDIT LOGGING & TRACEABILITY

### Backtest Audit Logs

**Every backtest creates detailed audit logs:**

```
testing/production_parity/audit_logs/
├── backtest_YYYYMMDD_HHMMSS.log
├── game_resolutions_YYYYMMDD.csv
├── team_resolutions_YYYYMMDD.csv
└── error_summary_YYYYMMDD.txt
```

### Audit Log Structure

**Each game has an audit trail:**

```csv
game_id,date_cst,home_team_raw,home_team_canonical,home_resolution_step,home_has_ratings,
away_team_raw,away_team_canonical,away_resolution_step,away_has_ratings,
game_season,ratings_season,status,error_reason

abc123,2024-01-15,Duke,Duke,CANONICAL,true,
UNC,North Carolina,ALIAS,true,
2024,2023,SUCCESS,

def456,2024-01-16,Alabama St,NULL,UNRESOLVED,false,
Auburn,Auburn,CANONICAL,true,
2024,2023,SKIPPED,home_team_unresolved
```

### Audit Log Interpretation

**Use audit logs to verify integrity:**

```bash
# Find all unresolved teams
grep "UNRESOLVED" testing/production_parity/audit_logs/*.log

# Find all skipped games
grep "SKIPPED" testing/production_parity/audit_logs/*.log

# Check resolution step distribution
cut -d, -f5 testing/production_parity/audit_logs/game_resolutions_*.csv | sort | uniq -c

# Example output (shows most matches are CANONICAL):
#     5000 CANONICAL (Step 1)
#     1500 ALIAS (Step 2)
#      800 NORMALIZED (Step 3)
#      200 MASCOT_STRIPPED (Step 4)
#       10 UNRESOLVED (No match)
```

---

## 7. DATA QUALITY ACCEPTANCE CRITERIA

### Team Matching Quality

| Metric | Threshold | Status |
|--------|-----------|--------|
| Resolution rate | ≥ 99% | ✅ Pass if met |
| Unresolved teams | < 5 | ✅ Pass if met |
| False positives (fuzzy) | 0 | ✅ Must be zero |
| Cross-source consistency | 100% | ✅ Must be perfect |

### Date & Season Quality

| Metric | Threshold | Status |
|--------|-----------|--------|
| Season assignment errors | 0 | ✅ Must be zero |
| Timezone consistency | 100% CST | ✅ Must be perfect |
| Date parsing errors | < 0.1% | ✅ Pass if met |

### Anti-Leakage Quality

| Metric | Threshold | Status |
|--------|-----------|--------|
| Game Season N uses Ratings N-1 | 100% | ✅ Must be perfect |
| No future data in predictions | 100% | ✅ Must be perfect |
| Leakage-corrected vs raw bias | < ±2% | ✅ Pass if met |

### Cross-Source Join Quality

| Metric | Threshold | Status |
|--------|-----------|--------|
| Game join success rate | ≥ 98% | ✅ Pass if met |
| Team consistency within games | 100% | ✅ Must be perfect |
| Spread sign correctness | 100% | ✅ Must be perfect |
| Total alignment | ±0.5 points | ✅ Pass if met |

---

## 8. QUICK VERIFICATION CHECKLIST

Use this checklist before running backtests:

### Team Matching ✅
- [ ] Run `validate_team_canonicalization.py`
- [ ] Check output shows ≥ 99% resolution rate
- [ ] Verify cross-source matches (Odds ∩ ESPN ≥ 95%)
- [ ] Run `audit_team_aliases.py` - should show zero issues
- [ ] Check `test_today_team_matching.py` - all sources resolve same

### Dates & Seasons ✅
- [ ] Verify season assignment: Nov-Apr → N, May-Oct → N+1
- [ ] Run `validate_canonical_odds.py` - check season columns
- [ ] Verify all timestamps are CST (not UTC or mixed)
- [ ] Check date ranges: Should be Nov YYYY to Apr YYYY+1

### Anti-Leakage ✅
- [ ] Confirm ratings_loader uses Season N-1 for Season N games
- [ ] Run test: `python -c "from testing.production_parity.ratings_loader import AntiLeakageRatingsLoader; AntiLeakageRatingsLoader()._test_anti_leakage()"`
- [ ] Verify game_season ≠ ratings_season in audit logs
- [ ] Check that Nov games use prior season ratings

### Cross-Source Joins ✅
- [ ] Run `pre_backtest_gate.py` - all audits should pass
- [ ] Check join success rate ≥ 98%
- [ ] Verify no duplicate records after join
- [ ] Confirm team consistency (no team_canonical mismatches)

### Backtest Ready ✅
- [ ] All checklist items completed
- [ ] No blockers in validation output
- [ ] Audit logs generated and reviewed
- [ ] Version tag created (e.g., v33.15.0)
- [ ] Ready to execute: `python testing/production_parity/run_backtest.py`

---

## 9. TROUBLESHOOTING

### Problem: Team not resolving

```bash
# Check if team exists in aliases
python -c "
from testing.production_parity.team_resolver import ProductionTeamResolver
r = ProductionTeamResolver()
result = r.resolve('Your Team Name')
print(f'Resolved: {result.canonical_name}')
print(f'Step: {result.step_used}')
"

# If None, add to testing/production_parity/team_aliases.json
```

### Problem: Cross-source mismatch

```bash
# Find which teams don't match
python testing/scripts/validate_team_canonicalization.py 2>&1 | grep "CRITICAL"

# Example output: "Tennessee → Tenn" in one source but "Tennessee State" in another
# Solution: Add alias to team_aliases.json
```

### Problem: Season mismatch

```bash
# Check dates in your data
python -c "
import pandas as pd
df = pd.read_csv('your_data.csv')
df['date'] = pd.to_datetime(df['date'])
df['month'] = df['date'].dt.month
print('Month distribution:')
print(df['month'].value_counts().sort_index())
"

# If months are all 11-4: seasons are correct
# If months are 1-9: check for mixed year data
```

### Problem: Data leakage suspected

```bash
# Compare results with anti-leakage
python testing/production_parity/run_backtest.py --verbose 2>&1 | grep "ratings_season"

# All games should show: game_season N → ratings_season N-1
```

---

## 10. CONCLUSION

Your data is **ready for backtesting** when:

✅ **Team Matching:**
- All sources resolve correctly (≥ 99%)
- Cross-source consistency (same game = same canonical names)
- No fuzzy matching (exact only)
- All aliases validated (no conflicts)

✅ **Date & Season:**
- Season assignment consistent (Nov-Apr window)
- All timestamps CST
- No mixed timezones

✅ **Anti-Leakage:**
- Season N games use Season N-1 ratings
- No forward-looking data
- Audit logs confirm N vs N-1 separation

✅ **Cross-Source Joins:**
- ≥ 98% match rate
- Team consistency within games
- Spreads/totals/scores align

**Execute pre-backtest gate to confirm all validations pass:**

```bash
python testing/scripts/pre_backtest_gate.py --verbose
```

Once all checks pass, your backtest results are **trustworthy and reproducible**.
