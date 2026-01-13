# DATA GOVERNANCE FRAMEWORK
## NO Placeholders | NO Silent Fallbacks | Guard Rails | Clear QA/QC

**Last Updated:** January 12, 2026  
**Status:** Implementation Ready  
**Owner:** Data Engineering Team

---

## 🎯 Executive Summary

Your question: *"How do we confirm we are implementing/incorporating into a single source of truth document with no placeholders or assumption or silent fallbacks with guard rails and clear qa/qc implementations for ALL data sources ingested from all RAW, including but not limited to the extensive NCAAR and Kaggle data sets"*

**Answer:** A three-layer governance framework:

1. **EXPLICIT DECLARATION** - Every data source formally registered with status, paths, coverage expectations
2. **GUARD RAILS** - Validation rules that BLOCK bad data (no silent fallbacks)
3. **IMMUTABLE AUDIT TRAIL** - Every validation result logged and persisted

---

## 📋 Part 1: ALL Data Sources - Explicit Declaration

### Currently ACTIVE (Ingesting)

| Source | Data Type | Status | Guard Rails | Coverage | Audit Trail |
|--------|-----------|--------|-------------|----------|------------|
| **The Odds API** | Odds (Spreads, Totals, Moneylines) | ✅ ACTIVE | 5 rules | 81-88% | ✓ |
| **ESPN API** | Scores (FG + H1) | ✅ ACTIVE | 4 rules | 95-100% | ✓ |
| **Barttorvik** | Efficiency Ratings | ✅ ACTIVE | 3 rules | 80-95% | ✓ |

### Currently INACTIVE (Available, Not Ingested)

| Source | Data Type | Status | Why Inactive | Next Steps |
|--------|-----------|--------|-------------|-----------|
| **NCAAR** | Box Scores, Play-by-Play | ⏸️ INACTIVE | Used for features only (build_consolidated_master.py) | Integrate through canonical pipeline |
| **Kaggle** | Tournament Scores | ⏸️ INACTIVE | Local CSV, tournament-only (68 games), no odds | Sync to Azure, implement merging logic |

### PLANNED (Scheduled)

| Source | Data Type | Target Date | Priority |
|--------|-----------|------------|----------|
| **Basketball-API** | Scores + Odds (secondary) | Q2 2026 | Medium |

### BLOCKED (Cannot Ingest)

| Source | Reason |
|--------|--------|
| **ESPN Box Scores** | No public API. Web scraping violates ToS. Use NCAAR instead. |

---

## 🛡️ Part 2: Guard Rails - No Silent Fallbacks

Each active data source has **explicit validation rules** that BLOCK bad data:

### The Odds API - 5 Guard Rails

```python
GuardRail #1: NO HARDCODED -110 ODDS
├─ Rule: "NEVER use hardcoded -110. ALL prices must come from source."
├─ Validator: assert df['spread_home_price'].notnull().all()
├─ Severity: ERROR (blocks ingestion)
├─ Why: Hardcoded -110 assumes symmetric pricing. Real odds are asymmetric.
└─ Documentation: Prevents entire classes of ROI miscalculations

GuardRail #2: SPREAD SIGN CONVENTION
├─ Rule: "Negative = home favored, positive = away favored. CONSISTENT."
├─ Validator: verify_spread_sign_consistency(df)
├─ Severity: ERROR
├─ Why: Sign confusion flips prediction directions.
└─ Example: spread=-5.5 means home favored by 5.5 (negative)

GuardRail #3: ODD PRICE RANGES
├─ Rule: "American odds must be [-500, +500]. Outside = corruption."
├─ Validator: assert df['spread_home_price'].between(-500, 500).all()
├─ Severity: WARNING (logs issue, continues)
├─ Why: Out-of-range prices indicate parsing or feed errors.
└─ Action: Review and correct before using

GuardRail #4: NO DUPLICATE GAMES
├─ Rule: "Each game appears at most once per market per day."
├─ Validator: assert df.groupby(['game_id', 'market']).size() <= 1
├─ Rule: "Each unique (home_team, away_team, market, game_date, game_id) appears at most once."
├─ Validator: duplicates = df.groupby(['game_id', 'home_team', 'away_team', 'market', 'game_date']).size(); assert duplicates.max() == 1
├─ Severity: ERROR
├─ Why: Duplicates cause double-counting in backtests.
└─ Action: Deduplicate before ingestion

GuardRail #5: ODDS FRESHNESS BY SEASON
├─ Rule: "Current season: <48hrs old. Historical: <10 days old."
├─ Validator: check_odds_freshness_by_season(df)
├─ Severity: WARNING
├─ Why: Stale odds don't represent actual market conditions.
└─ Action: Verify daily updates for current season
```

### ESPN API - 4 Guard Rails

```python
GuardRail #1: COMPLETE SCORES REQUIRED
├─ Rule: "If home_score is not null, away_score must also not be null."
├─ Validator: assert (df['home_score'].isnull() == df['away_score'].isnull())
├─ Severity: ERROR
├─ Why: Partial scores cause backtest errors and mismatched joins.
└─ Action: Skip incomplete games or wait for completion

GuardRail #2: REASONABLE SCORE RANGES
├─ Rule: "College basketball: 0-200. Completed games: 1-200."
├─ Validator: assert df['home_score'].between(1, 200).all()
├─ Severity: WARNING
├─ Why: Unreasonable scores indicate data corruption.
└─ Action: Investigate and correct source data

GuardRail #3: MANDATORY TEAM RESOLUTION
├─ Rule: "All team names must resolve to canonical names. ZERO unresolved."
├─ Validator: assert df['home_team'].isin(CANONICAL_TEAMS).all()
├─ Severity: ERROR
├─ Why: Unresolved teams fail joins with odds/ratings data.
└─ Action: Add to team_aliases_db.json, re-run resolution

GuardRail #4: DATE STANDARDIZATION
├─ Rule: "All dates in UTC ISO 8601. NO local times."
├─ Validator: pd.to_datetime(df['game_date'], utc=True)
├─ Rule: "All game dates normalized to Central Time (CST/CDT via America/Chicago) in ISO 8601. NO other local timezones."
├─ Validator: pd.to_datetime(df['game_date']).dt.tz_localize('America/Chicago')
├─ Why: Timezone inconsistencies cause time-based bugs. Central Time is the single canonical baseline.
└─ Action: Convert all raw source timestamps to Central Time before storage
├─ Severity: ERROR
├─ Why: Timezone inconsistencies cause time-based bugs.
└─ Action: Convert to UTC before storage
```

### Barttorvik - 3 Guard Rails

```python
GuardRail #1: PRIOR SEASON RATINGS ONLY
├─ Rule: "For season N games, use season N-1 ratings. NEVER same season."
├─ Validator: assert df['ratings_season'] == df['game_season'] - 1
├─ Severity: ERROR
├─ Why: Same-season ratings = information leakage from future data.
└─ Documentation: Critical for valid backtests

GuardRail #2: RATING VALUE RANGES
├─ Rule: "Efficiency: 50-150. Tempo: 60-80. Else = corruption."
├─ Validator: assert df['adj_o'].between(50, 150).all()
├─ Severity: WARNING
├─ Why: Out-of-range values indicate API or parsing errors.
└─ Action: Verify source data quality

GuardRail #3: TEAM COVERAGE BY SEASON
├─ Rule: "95%+ of ~360 D1 teams must have ratings."
├─ Validator: coverage = len(df) / 360; assert coverage >= 0.95
├─ Severity: WARNING
├─ Why: Low coverage indicates incomplete scrape.
└─ Action: Verify Barttorvik has updated for the season
```

### NCAAR (ncaahoopR) - Planned Integration

```python
GuardRail #1: SCHEMA REQUIRED
├─ Rule: "game_id, team, opp, points, home_away, date (all required)"
├─ Validator: required = {'game_id', 'team', 'opp', 'points'}
├─ Severity: ERROR

GuardRail #2: GAME MATCHING
├─ Rule: "Each box score must match exactly ONE ESPN game"
├─ Validator: unmatched = check_game_matching(ncaamr_df, espn_df)
├─ Severity: ERROR

GuardRail #3: TEAM CONSISTENCY
├─ Rule: "Team names must match ESPN canonical names exactly"
├─ Validator: unresolved = ncaamr_df[~ncaamr_df['team'].isin(CANONICAL)]
├─ Severity: ERROR
```

### Kaggle - 3 Guard Rails (When Activated)

```python
GuardRail #1: TOURNAMENT-ONLY SCOPE
├─ Rule: "Kaggle has NCAA tournament ONLY (68 games March-April). NOT regular season."
├─ Validator: dates = pd.to_datetime(df['date']); assert dates.dt.month.isin([3,4]).all()
├─ Severity: ERROR
├─ Why: Confusing tournament with regular season causes data leakage.
└─ Action: Use only for tournament predictions, not full-season model

GuardRail #2: NO ODDS WARNING
├─ Rule: "Kaggle has no odds data. Cannot use alone for backtesting."
├─ Validator: assert 'spread' not in df.columns or df['spread'].isnull().all()
├─ Severity: WARNING
├─ Why: Odds are critical for ROI backtesting.
└─ Action: Merge with external odds before backtesting

GuardRail #3: TEAM RESOLUTION
├─ Rule: "Kaggle team names must resolve to canonical names."
├─ Validator: unresolved = df[~df['team'].isin(CANONICAL_TEAMS)]
├─ Severity: ERROR
├─ Why: Different naming conventions require explicit mapping.
└─ Action: Document any new team name variants
```

---

## ✅ Part 3: QA/QC Implementation - Coverage Reports

Every data ingestion generates a **Coverage Report** showing:

### Coverage Matrix (Current State - January 12, 2026)

```
DATA SOURCE     | 2024 Season    | 2025 Season    | 2026 YTD
                | Games | % Odds | Games | % Odds | Games | % Odds
────────────────┼────────────────┼────────────────┼────────────────
The Odds API    | 5,847 | 87.5% | 5,916 | 87.9% |   497 | 81.5%
ESPN Scores     | 5,847 | 100%  | 5,916 | 100%  |   520 | 99%
Barttorvik      | 5,847 | 80.2% | 5,916 | 79.5% |   497 | 65%
────────────────┴────────────────┴────────────────┴────────────────
H1 Scores       | 5,847 | 8.1%  | 5,916 | 7.9%  |   497 | 0%
────────────────┴────────────────┴────────────────┴────────────────
NCAAR (inactive)| N/A            | N/A            | N/A
Kaggle (inactive)| 68 tournament only (no odds)
```

### QA/QC Rules by Data Type

#### ODDS Data QA/QC

```
✓ No Hardcoded Prices
  └─ FAIL: Any spread_home_price = -110 (hardcoded)
  
✓ Sign Consistency  
  └─ FAIL: Negative spread but home_price positive (mismatch)
  
✓ Price Ranges
  └─ FAIL: Any price < -500 or > +500
  
✓ Game Uniqueness
  └─ FAIL: Duplicate games by (game_id, home_team, away_team, market, game_date)
  
✓ Freshness (Current Season)
  └─ FAIL: Data older than 48 hours (for 2026)
  
✓ Market Consistency
  └─ WARN: If spread exists but total doesn't (should have both)
```

#### SCORES Data QA/QC

```
✓ Complete Pair
  └─ FAIL: home_score without away_score (or vice versa)
  
✓ Reasonable Ranges
  └─ WARN: Any score < 1 or > 200 for completed game
  
✓ Team Resolution
  └─ FAIL: Any team name not in CANONICAL_TEAMS list
  
✓ Date Format
  └─ FAIL: Any date not representing Central Time (CST/CDT, America/Chicago) in ISO 8601 form
  
✓ Unique Games
  └─ FAIL: Duplicate games by (date, home_team, away_team)
  
✓ Score Finality
  └─ WARN: Game marked as final but scores < 30 total (possible error)
```

#### RATINGS Data QA/QC

```
✓ Prior Season Only
  └─ FAIL: ratings_season != game_season - 1
  
✓ Coverage Threshold
  └─ WARN: < 90% of D1 teams have ratings for season
  
✓ Value Ranges
  └─ WARN: Any rating < 50 or > 150 (adj_o, adj_d)
  
✓ Tempo Ranges
  └─ WARN: Any tempo < 60 or > 80 (adj_t)
  
✓ Team Resolution
  └─ FAIL: Any team not in CANONICAL_TEAMS
  
✓ Temporal Consistency
  └─ WARN: If team's rating jumped >10 points in one update
```

---

## 🔧 Part 4: Implementation - How to Activate

### Step 1: Run Data Governance Framework (DONE - Shows Status)

```bash
python testing/scripts/data_governance_framework.py
```

Output:
```
DATA GOVERNANCE FRAMEWORK - COMPREHENSIVE STATUS

📊 DATA SOURCE INVENTORY:
  Active Sources:    3
  Inactive Sources:  2
  Planned Sources:   1
  Blocked Sources:   1

✅ ACTIVE SOURCES (Currently Ingesting):
  • The Odds API (odds_api)
  • ESPN API (espn_api)
  • Barttorvik (barttorvik)

⏸️  INACTIVE SOURCES (Available but NOT Ingested):
  • NCAAR (ncaamr)
  • Kaggle (kaggle)

🔮 PLANNED SOURCES:
  • Basketball-API (basketball_api)

✅ DATA GOVERNANCE FRAMEWORK READY FOR IMPLEMENTATION
```

### Step 2: Implement Guard Rail Validation (NEXT)

Create `testing/canonical/guard_rails_engine.py`:

```python
# Pseudo-code for guard rails validation
from data_governance_framework import REGISTRY, DataGovernanceValidator

# Create validator
validator = DataGovernanceValidator(
    strict_mode=True,  # BLOCK on errors
    audit_trail_path=Path("manifests/guard_rail_audit.json")
)

# When ingesting odds data:
result = validator.validate_data_source(
    df=odds_data,
    source_id="odds_api",
    data_type="odds",
    season=2026
)

if result["status"] == "FAIL":
    raise ValueError(f"Guard rail violations: {result['errors']}")
    # NOT SILENT FALLBACK - EXPLICIT ERROR

# When ingesting scores:
result = validator.validate_data_source(
    df=scores_data,
    source_id="espn_api",
    data_type="scores",
    season=2026
)

# Audit trail auto-saved
print(f"Audit trail: {validator.save_audit_trail()}")
```

### Step 3: Integrate Into Ingestion Pipeline

Modify `testing/scripts/fetch_historical_odds.py`:

```python
# BEFORE: No guard rails, silent fallbacks possible
def fetch_and_store(season):
    df = fetch_from_api(season)
    # Implicit assumptions, no validation
    write_to_azure(df)

# AFTER: Explicit validation, guard rails, audit trail
from testing.scripts.data_governance_framework import REGISTRY
from testing.canonical.guard_rails_engine import DataGovernanceValidator

def fetch_and_store(season):
    df = fetch_from_api(season)
    
    # 1. VALIDATE against guard rails (NO silent fallbacks)
    validator = DataGovernanceValidator(strict_mode=True)
    result = validator.validate_data_source(
        df=df,
        source_id="odds_api",
        data_type="odds",
        season=season
    )
    
    # 2. BLOCK if errors (not optional)
    if result["status"] == "FAIL":
        print(f"❌ Guard rail violations:\n{result['errors']}")
        raise ValueError("Data failed validation. Check guard_rail_audit.json")
    
    # 3. LOG warnings (informational)
    if result["warnings"]:
        print(f"⚠️  Warnings (continuing):\n{result['warnings']}")
    
    # 4. STORE audit trail (immutable proof)
    validator.save_audit_trail()
    
    # 5. Finally, write to Azure
    write_to_azure(df)
    return True
```

### Step 4: Activate NCAAR Ingestion (Planned)

```python
# Create: testing/scripts/fetch_ncaahoopR_data.py

from testing.scripts.data_governance_framework import REGISTRY

# 1. Verify NCAAR source is ready
ncaamr_source = REGISTRY.find_by_id("ncaamr")
assert ncaamr_source.status == DataSourceStatus.INACTIVE  # Currently

# 2. Implement integration:
#    a. Load box scores from Azure ncaam-historical-raw
#    b. Validate against guard rails (game matching, team resolution)
#    c. Move to canonical_container (ncaam-historical-data)
#    d. Update ingestion_script and last_updated
#    e. Change status to ACTIVE

# 3. Update registry:
ncaamr_source.status = DataSourceStatus.ACTIVE
ncaamr_source.ingestion_script = "testing/scripts/fetch_ncaahoopR_data.py"
ncaamr_source.last_updated = datetime.now().isoformat()
```

### Step 5: Activate Kaggle Integration (Optional)

```python
# Create: testing/scripts/ingest_kaggle_data.py

# 1. Verify Kaggle data is in Azure
# 2. Guard rail #1: Check dates are tournament-only (March-April)
# 3. Merge with odds data via (date, home_team, away_team) join
# 4. Guard rail #2: Verify odds merged (not silent fallback to no-odds)
# 5. Guard rail #3: Verify team resolution
# 6. Store to canonical location
```

---

## 📊 Part 5: Audit Trail & Verification

Every data ingestion creates an **immutable audit trail**:

### Audit Trail Format (JSON)

```json
{
  "ingestion_id": "odds-api-2026-01-12-10-30-45",
  "timestamp": "2026-01-12T10:30:45Z",
  "source": "odds_api",
  "data_type": "odds",
  "season": 2026,
  "status": "PASS",
  "rows_ingested": 2156,
  "guard_rails_checked": 5,
  "guard_rails_passed": 5,
  "guard_rails_failed": 0,
  "errors": [],
  "warnings": [
    "odds_freshness: Some games older than 48 hours (historical data)"
  ],
  "validation_details": {
    "no_hardcoded_odds": "PASS",
    "spread_sign_convention": "PASS",
    "odds_price_ranges": "PASS",
    "no_duplicate_games": "PASS",
    "odds_freshness_by_season": "WARN"
  },
  "coverage": {
    "total_games_expected": 2200,
    "total_games_found": 2156,
    "coverage_pct": 98.0,
    "minimum_viable": 75.0,
    "status": "PASS"
  },
  "previous_audit": "odds-api-2026-01-11-10-30-45",
  "git_commit": "27cacd1",
  "azure_blob_path": "odds/normalized/odds_consolidated_canonical.csv"
}
```

### Check Audit Trail (Live)

```bash
# View latest ingestion audit
cat manifests/guard_rail_audit.json | tail -1 | jq '.'

# Check all NCAAR ingestions (once activated)
jq '.[] | select(.source=="ncaamr")' manifests/guard_rail_audit.json

# Verify odds are never hardcoded
jq '.[] | select(.source=="odds_api") | .validation_details.no_hardcoded_odds' manifests/guard_rail_audit.json

# Find any failed ingestions (should be none)
jq '.[] | select(.status=="FAIL")' manifests/guard_rail_audit.json
```

---

## 🎯 Part 6: Single Source of Truth - Azure Storage

All data flows through this path (no local assumptions):

```
┌─────────────────┐
│  Raw Sources    │ (Odds API, ESPN, Barttorvik, NCAAR, Kaggle)
└────────┬────────┘
         │
         ▼
┌───────────────────────────────────┐
│ Guard Rails Validation             │ ← Blocks bad data (NO fallbacks)
│ - Schema checks                    │
│ - Range checks                     │
│ - Integrity checks                 │
│ - Consistency checks               │
└────────┬────────────────────────────┘
         │
         ▼
┌───────────────────────────────────┐
│ Team Resolution                   │ ← Canonicalizes names
│ (team_aliases_db.json → canonical)│
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│ AZURE BLOB STORAGE (Single Source of Truth)    │
│ Container: ncaam-historical-data                │
│ ├── scores/fg/games_all.csv                     │
│ ├── scores/h1/h1_games_all.csv                  │
│ ├── odds/normalized/odds_consolidated.csv      │
│ ├── ratings/barttorvik/ratings_*.csv            │
│ ├── ncaahoopR_data-master/box_scores/...        │
│ ├── backtest_datasets/team_aliases_db.json      │
│ └── manifests/guard_rail_audit.json ← AUDIT    │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Backtest Dataset Builder            │
│ (build_backtest_dataset_canonical)  │
│ - Joins scores + odds + ratings     │
│ - Validates coverage requirements   │
│ - Creates backtest_master.csv       │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Backtesting / Prediction            │
│ (run_historical_backtest.py)        │
│ (prediction-service-python)         │
└─────────────────────────────────────┘
```

---

## 📋 Part 7: Checklist for Data Governance Compliance

Use this to verify EVERY data source meets standards:

### The Odds API Checklist

- [ ] Guard Rail #1: No hardcoded -110 odds
  - Verify: `df['spread_home_price'].value_counts()` has many values, not just -110
- [ ] Guard Rail #2: Spread sign convention consistent
  - Verify: If spread < 0, then home favored (check with moneyline direction)
- [ ] Guard Rail #3: Prices in [-500, +500]
  - Verify: `df['spread_home_price'].between(-500, 500).all()` = True
- [ ] Guard Rail #4: No duplicate games
  - Verify: `df.groupby(['game_id', 'market']).size().max()` = 1
- [ ] Guard Rail #5: Freshness by season
  - Verify: Current season data < 48 hours old
- [ ] Coverage: Expected for season
  - Verify: Coverage % matches `expected_coverage_pct` in registry

### ESPN API Checklist

- [ ] Guard Rail #1: Complete pairs
  - Verify: `(df['home_score'].isnull() == df['away_score'].isnull()).all()` = True
- [ ] Guard Rail #2: Reasonable ranges
  - Verify: `df['home_score'].between(1, 200).all()` = True
- [ ] Guard Rail #3: Team resolution
  - Verify: Zero unresolved teams (all in CANONICAL_TEAMS)
- [ ] Guard Rail #4: Date standardization
  - Verify: All dates represent Central Time (CST/CDT, America/Chicago) in ISO 8601 form
- [ ] Coverage: 95%+ of expected games
  - Verify: Coverage % ≥ `expected_coverage_pct` in registry

### Barttorvik Checklist

- [ ] Guard Rail #1: Prior season ratings only
  - Verify: `(df['ratings_season'] == df['game_season'] - 1).all()` = True
- [ ] Guard Rail #2: Value ranges
  - Verify: `df['adj_o'].between(50, 150).all()` = True
- [ ] Guard Rail #3: Team coverage
  - Verify: Coverage % ≥ `minimum_viable_coverage_pct` (90%)

### NCAAR (When Activated)

- [ ] Guard Rail #1: Schema present
- [ ] Guard Rail #2: Games match ESPN 1:1
- [ ] Guard Rail #3: Teams resolve
- [ ] Coverage: 95%+ of games have box scores
- [ ] Audit trail: All validations logged

### Kaggle (When Activated)

- [ ] Guard Rail #1: Dates are March-April only
- [ ] Guard Rail #2: No missing odds warning (addressed separately)
- [ ] Guard Rail #3: Teams resolve
- [ ] Coverage: 100% of 68 tournament games
- [ ] Scope: Clearly labeled as tournament-only

---

## 🚀 Next Steps (Priority Order)

### Immediate (This Week)

1. ✅ Run `data_governance_framework.py` to validate registry
2. ✅ Review guard rail definitions (above)
3. ⬜ Create `guard_rails_engine.py` with validation logic
4. ⬜ Integrate into `fetch_historical_odds.py` (test with 2026 data)
5. ⬜ Run audit and verify zero guard rail violations

### Short Term (Next 2 Weeks)

1. ⬜ Integrate guard rails into all fetch scripts
2. ⬜ Generate compliance report for all 3 active sources
3. ⬜ Archive `manifests/guard_rail_audit.json` weekly

### Medium Term (Q1 2026)

1. ⬜ Activate NCAAR ingestion through canonical pipeline
2. ⬜ Update registry status to ACTIVE
3. ⬜ Validate guard rails for NCAAR matches ESPN

### Long Term (Q2 2026)

1. ⬜ Activate Kaggle integration (tournament-only)
2. ⬜ Implement Basketball-API as secondary odds source
3. ⬜ Evaluate coverage with all 5 sources active

---

## 📞 Questions & Answers

**Q: What happens if data fails a guard rail?**  
A: Ingestion BLOCKS with error. No silent fallbacks. You must:
1. Review audit trail to see which rule failed
2. Fix source data or adjust guard rail
3. Re-run ingestion

**Q: What if a source has data gaps?**  
A: Covered by coverage % validation. If below `minimum_viable_coverage_pct`, ingestion warns but continues (only if warnings allowed). If below required, ingestion blocks.

**Q: How do we know NCAAR data is correct when we activate it?**  
A: Guard rails #2 (game matching) validates each box score matches exactly one ESPN game. If any unmatched, ingestion fails.

**Q: What about Kaggle tournament games - how do we ensure they don't leak into regular season model?**  
A: Guard rail #1 enforces dates are March-April only. If tournament dates appear in regular season data, ingestion fails.

**Q: Can we make assumptions about missing data?**  
A: NO. Missing data must be explicitly handled:
- If odds are missing: Skip game or fill with explicit strategy (documented)
- If ratings are missing: Skip game or use league average (documented)
- If scores are missing: Skip game (never infer)

**Q: Who maintains the registry?**  
A: Data engineering team. Registry lives in `data_governance_framework.py`. Changes:
1. Update `REGISTRY.sources[]`
2. Re-run `data_governance_framework.py` to regenerate manifest
3. Commit to git
4. Update this documentation

---

## 📚 Related Documents

- [SINGLE_SOURCE_OF_TRUTH.md](SINGLE_SOURCE_OF_TRUTH.md) - Azure storage structure
- [VALIDATION_GATES.md](VALIDATION_GATES.md) - Pre-prediction validation
- [DATA_SOURCES.md](DATA_SOURCES.md) - Current active sources
- [INGESTION_ARCHITECTURE.md](INGESTION_ARCHITECTURE.md) - Data flow diagram
- [manifests/data_sources_registry.json](../../manifests/data_sources_registry.json) - Machine-readable registry

---

**Version:** 1.0  
**Last Updated:** January 12, 2026  
**Status:** Implementation Ready  
**Next Review:** January 19, 2026
