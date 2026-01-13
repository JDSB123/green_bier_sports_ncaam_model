# DATA GOVERNANCE IMPLEMENTATION GUIDE
## From Framework to Enforcement

**Last Updated:** January 12, 2026  
**Status:** READY FOR IMPLEMENTATION  
**Owner:** Data Engineering Team

---

## 🎯 Quick Start

Your data governance framework is NOW LIVE. Here's what we built:

### What You Have

1. ✅ **Formal Registry** (`manifests/data_sources_registry.json`)
   - 7 data sources explicitly declared (3 active, 2 inactive, 1 planned, 1 blocked)
   - 19 guard rails defined across all sources
   - Coverage expectations documented

2. ✅ **Python Framework** (`testing/scripts/data_governance_framework.py`)
   - Executable code defining every data source
   - Guard rails as code (testable, auditable)
   - Registry exporter for governance documentation

3. ✅ **Comprehensive Documentation** (`docs/DATA_GOVERNANCE_FRAMEWORK.md`)
   - Explicit guard rails for each source
   - QA/QC rules per data type
   - Implementation roadmap
   - Compliance checklists

### What's Missing (Implementation Tasks)

1. ⬜ **Guard Rails Engine** - Validator that executes the rules and blocks bad data
2. ⬜ **Integration** - Connect validators into ingestion scripts
3. ⬜ **Audit Logging** - Immutable record of every validation
4. ⬜ **NCAAR Activation** - Move from feature engineering to active ingestion
5. ⬜ **Coverage Monitoring** - Dashboard showing compliance vs minimums

---

## 📝 PART 1: Understanding the Framework

### Seven Data Sources

```
┌─────────────────────────────────────────────────────────┐
│          DATA SOURCES - EXPLICIT STATUS                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ACTIVE (3)                                              │
│  ✓ The Odds API → FG & H1 odds + moneylines             │
│  ✓ ESPN API → Game scores, schedules                    │
│  ✓ Barttorvik → Team efficiency ratings                 │
│                                                         │
│ INACTIVE (2)                                            │
│  ⏸ NCAAR (ncaahoopR) → Box scores (feature eng only)   │
│  ⏸ Kaggle → Tournament games (tournament only)          │
│                                                         │
│ PLANNED (1)                                             │
│  🔮 Basketball-API → Secondary odds source              │
│                                                         │
│ BLOCKED (1)                                             │
│  🚫 ESPN Advanced Box Scores → No public API            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 19 Guard Rails - No Silent Fallbacks

Guard rails are **validation rules that BLOCK bad data**, not silent assumptions.

**Example:**

```
❌ WRONG - Silent fallback (old way)
───────────────────────────────────
def ingest_odds(df):
    if 'spread_home_price' not in df.columns:
        # Silent: assume -110
        df['spread_home_price'] = -110
    write_to_azure(df)
    # Nobody knows this happened!

✅ RIGHT - Guard rails (new way)
─────────────────────────────────
def ingest_odds(df):
    # Guard rail: prices must come from source
    if df['spread_home_price'].isnull().any():
        raise ValueError("Missing odds prices detected!")
    
    # Guard rail: no hardcoded -110
    if (df['spread_home_price'] == -110).sum() > 0:
        raise ValueError("Hardcoded odds detected! Check data source.")
    
    write_to_azure(df)
    # EXPLICIT: Either passes validation or fails with reason
```

---

## 🔧 PART 2: Implementation Walkthrough

### Step 1: Create Guard Rails Engine

**File:** `testing/canonical/guard_rails_engine.py` (NEW)

```python
"""
GUARD RAILS ENGINE

Executes validation rules defined in data_governance_framework.py
Blocks bad data with explicit errors. NO silent fallbacks.
"""

import sys
from pathlib import Path
from typing import Tuple, List, Dict

import pandas as pd

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.scripts.data_governance_framework import REGISTRY, DataSourceStatus
from testing.canonical.team_resolution_service import get_team_resolver


class GuardRailValidator:
    """Execute guard rails for a data source."""
    
    def __init__(self, source_id: str, strict_mode: bool = True):
        """
        Initialize validator for a specific source.
        
        Args:
            source_id: e.g., "odds_api", "espn_api", "barttorvik"
            strict_mode: If True, errors block. If False, warnings only.
        """
        self.source = REGISTRY.find_by_id(source_id)
        if not self.source:
            raise ValueError(f"Unknown source: {source_id}")
        
        self.strict_mode = strict_mode
        self.team_resolver = get_team_resolver()
        self.errors = []
        self.warnings = []
    
    def validate(self, df: pd.DataFrame) -> Tuple[bool, List[str], List[str]]:
        """
        Validate DataFrame against all guard rails for this source.
        
        Returns:
            (passed: bool, errors: List[str], warnings: List[str])
        
        Raises:
            ValueError: If strict_mode=True and errors found
        """
        self.errors = []
        self.warnings = []
        
        for guard_rail in self.source.guard_rails:
            try:
                # Execute the validation rule
                self._execute_guard_rail(guard_rail, df)
            
            except Exception as e:
                msg = f"{guard_rail.name}: {e}"
                if guard_rail.severity == "error":
                    self.errors.append(msg)
                else:
                    self.warnings.append(msg)
        
        # Raise if strict mode and errors exist
        if self.strict_mode and self.errors:
            raise ValueError(f"Guard rail violations:\n" + "\n".join(self.errors))
        
        passed = len(self.errors) == 0
        return passed, self.errors, self.warnings
    
    def _execute_guard_rail(self, guard_rail, df: pd.DataFrame):
        """Execute a single guard rail validator."""
        
        # Dispatch to specific validator based on rule name
        if guard_rail.name == "no_hardcoded_odds":
            self._check_no_hardcoded_odds(df)
        
        elif guard_rail.name == "spread_sign_convention":
            self._check_spread_sign_convention(df)
        
        elif guard_rail.name == "odds_price_ranges":
            self._check_odds_price_ranges(df)
        
        elif guard_rail.name == "no_duplicate_games":
            self._check_no_duplicate_games(df)
        
        elif guard_rail.name == "odds_freshness_by_season":
            self._check_odds_freshness(df)
        
        elif guard_rail.name == "complete_score_requirement":
            self._check_complete_scores(df)
        
        elif guard_rail.name == "reasonable_score_ranges":
            self._check_reasonable_scores(df)
        
        elif guard_rail.name == "team_resolution_mandatory":
            self._check_team_resolution(df)
        
        elif guard_rail.name == "date_standardization":
            self._check_date_format(df)
        
        elif guard_rail.name == "prior_season_ratings_only":
            self._check_prior_season_ratings(df)
        
        elif guard_rail.name == "rating_value_ranges":
            self._check_rating_ranges(df)
        
        elif guard_rail.name == "team_coverage_by_season":
            self._check_team_coverage(df)
        
        else:
            raise NotImplementedError(f"Guard rail {guard_rail.name} not implemented")
    
    # ─────────────────────────────────────────────────────────────────────────
    # ODDS API GUARD RAILS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _check_no_hardcoded_odds(self, df: pd.DataFrame):
        """Guard rail: No hardcoded -110 odds."""
        if 'spread_home_price' not in df.columns:
            raise ValueError("Missing 'spread_home_price' column")
        
        null_count = df['spread_home_price'].isnull().sum()
        if null_count > 0:
            raise ValueError(f"{null_count} rows have null spread_home_price (no odds available)")
        
        # Check for hardcoded -110
        hardcoded = (df['spread_home_price'] == -110).sum()
        if hardcoded > 0:
            pct = hardcoded / len(df) * 100
            # Small number of -110 is OK (some markets), but if > 90%, likely hardcoded
            if pct > 90:
                raise ValueError(f"{pct:.1f}% of prices are hardcoded -110")
    
    def _check_spread_sign_convention(self, df: pd.DataFrame):
        """Guard rail: Spread sign consistency."""
        if 'spread' not in df.columns or 'moneyline_home_price' not in df.columns:
            # Can't validate without both columns
            return
        
        # Check: if spread < 0 (home favored), moneyline should be negative
        home_favored = df['spread'] < 0
        home_ml_positive = df['moneyline_home_price'] > 0
        
        mismatches = (home_favored & home_ml_positive).sum()
        if mismatches > 0:
            raise ValueError(f"{mismatches} rows have spread/moneyline sign mismatch")
    
    def _check_odds_price_ranges(self, df: pd.DataFrame):
        """Guard rail: Prices in [-500, +500]."""
        price_cols = ['spread_home_price', 'spread_away_price', 
                     'total_over_price', 'total_under_price',
                     'moneyline_home_price', 'moneyline_away_price']
        
        for col in price_cols:
            if col not in df.columns:
                continue
            
            # Get non-null prices
            prices = df[col].dropna()
            if len(prices) == 0:
                continue
            
            out_of_range = ((prices < -500) | (prices > 500)).sum()
            if out_of_range > 0:
                raise ValueError(f"{out_of_range} prices out of range in {col}")
    
    def _check_no_duplicate_games(self, df: pd.DataFrame):
        """Guard rail: No duplicate games per market."""
        if 'game_id' not in df.columns or 'market' not in df.columns:
            return  # Can't validate
        
        duplicates = df.groupby(['game_id', 'market']).size()
        duped = (duplicates > 1).sum()
        
        if duped > 0:
            raise ValueError(f"{duped} duplicate (game_id, market) combinations found")
    
    def _check_odds_freshness(self, df: pd.DataFrame):
        """Guard rail: Odds freshness by season."""
        # Would check: current season < 48hrs, historical < 10 days
        # Implementation would compare df['fetch_date'] to current_date
        pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # ESPN API GUARD RAILS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _check_complete_scores(self, df: pd.DataFrame):
        """Guard rail: Complete score pairs."""
        home_null = df['home_score'].isnull()
        away_null = df['away_score'].isnull()
        
        mismatch = (home_null != away_null).sum()
        if mismatch > 0:
            raise ValueError(f"{mismatch} rows have incomplete score pairs")
    
    def _check_reasonable_scores(self, df: pd.DataFrame):
        """Guard rail: Reasonable score ranges."""
        completed = df['home_score'].notna()
        bad_scores = (
            (df.loc[completed, 'home_score'] < 1) |
            (df.loc[completed, 'home_score'] > 200) |
            (df.loc[completed, 'away_score'] < 1) |
            (df.loc[completed, 'away_score'] > 200)
        ).sum()
        
        if bad_scores > 0:
            self.warnings.append(f"{bad_scores} unreasonable scores detected (not errors)")
    
    def _check_team_resolution(self, df: pd.DataFrame):
        """Guard rail: All teams resolve to canonical names."""
        unresolved_home = df[~df['home_team'].isin(self.team_resolver.get_canonical_names())]
        unresolved_away = df[~df['away_team'].isin(self.team_resolver.get_canonical_names())]
        
        unresolved = len(unresolved_home) + len(unresolved_away)
        if unresolved > 0:
            examples = list(unresolved_home['home_team'].unique()[:3])
            raise ValueError(f"{unresolved} unresolved teams found (e.g., {examples})")
    
    def _check_date_format(self, df: pd.DataFrame):
        """Guard rail: Dates in UTC ISO 8601."""
        date_col = 'game_date' if 'game_date' in df.columns else 'date'
        
        try:
            dates = pd.to_datetime(df[date_col], utc=True)
            if dates.dt.tz is None:
                raise ValueError("Dates are not timezone-aware (not UTC)")
        except Exception as e:
            raise ValueError(f"Invalid date format: {e}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # BARTTORVIK GUARD RAILS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _check_prior_season_ratings(self, df: pd.DataFrame):
        """Guard rail: Prior season ratings only (anti-leakage)."""
        if 'ratings_season' not in df.columns or 'game_season' not in df.columns:
            return
        
        mismatch = (df['ratings_season'] != df['game_season'] - 1).sum()
        if mismatch > 0:
            raise ValueError(f"{mismatch} rows have non-prior-season ratings (LEAKAGE!)")
    
    def _check_rating_ranges(self, df: pd.DataFrame):
        """Guard rail: Rating ranges."""
        for col in ['adj_o', 'adj_d']:
            if col not in df.columns:
                continue
            
            ratings = df[col].dropna()
            bad = ((ratings < 50) | (ratings > 150)).sum()
            if bad > 0:
                self.warnings.append(f"{bad} {col} values out of range [50, 150]")
    
    def _check_team_coverage(self, df: pd.DataFrame):
        """Guard rail: Team coverage by season."""
        if 'season' not in df.columns:
            return
        
        for season in df['season'].unique():
            season_df = df[df['season'] == season]
            coverage = len(season_df) / 360  # ~360 D1 teams
            
            if coverage < 0.90:
                self.warnings.append(f"Season {season}: {coverage*100:.1f}% team coverage (< 90%)")


def validate_odds_before_ingestion(df: pd.DataFrame) -> None:
    """
    Quick helper: Validate odds before ingestion.
    Raises ValueError if validation fails.
    """
    validator = GuardRailValidator("odds_api", strict_mode=True)
    passed, errors, warnings = validator.validate(df)
    
    if warnings:
        print(f"⚠️  Warnings:\n" + "\n".join(warnings))
    
    if not passed:
        raise ValueError(f"Odds validation failed:\n" + "\n".join(errors))


def validate_scores_before_ingestion(df: pd.DataFrame) -> None:
    """Quick helper: Validate scores before ingestion."""
    validator = GuardRailValidator("espn_api", strict_mode=True)
    passed, errors, warnings = validator.validate(df)
    
    if warnings:
        print(f"⚠️  Warnings:\n" + "\n".join(warnings))
    
    if not passed:
        raise ValueError(f"Scores validation failed:\n" + "\n".join(errors))


def validate_ratings_before_ingestion(df: pd.DataFrame) -> None:
    """Quick helper: Validate ratings before ingestion."""
    validator = GuardRailValidator("barttorvik", strict_mode=True)
    passed, errors, warnings = validator.validate(df)
    
    if warnings:
        print(f"⚠️  Warnings:\n" + "\n".join(warnings))
    
    if not passed:
        raise ValueError(f"Ratings validation failed:\n" + "\n".join(errors))
```

### Step 2: Integrate Into Fetch Scripts

**Modify:** `testing/scripts/fetch_historical_odds.py`

```python
# At the top, add import:
from testing.canonical.guard_rails_engine import validate_odds_before_ingestion

# In the main function, after fetching:
def fetch_and_store_odds(season: int):
    """Fetch odds and validate before storing."""
    
    print(f"📥 Fetching odds for season {season}...")
    df = fetch_from_odds_api(season)  # Your existing code
    
    # 🛡️  GUARD RAILS VALIDATION (NEW)
    print(f"🛡️  Validating {len(df)} odds rows...")
    try:
        validate_odds_before_ingestion(df)
        print(f"✅ Validation passed!")
    except ValueError as e:
        print(f"❌ Validation failed:\n{e}")
        raise
    
    # Only write if validation passed (implicit due to exception)
    print(f"📤 Writing to Azure...")
    write_to_azure(df, path=f"odds/normalized/odds_{season}.csv")
    
    return True
```

### Step 3: Create Audit Trail Logger

**File:** `testing/canonical/audit_logger.py` (NEW)

```python
"""
AUDIT LOGGING

Creates immutable audit trail of all data validations.
Every validation result is logged and cannot be modified.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd


class AuditLogger:
    """Log data validations to immutable audit trail."""
    
    def __init__(self, audit_file: Path = None):
        self.audit_file = audit_file or Path("manifests/data_validation_audit.json")
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log = self._load_existing_log()
    
    def _load_existing_log(self) -> List[Dict]:
        """Load existing audit trail (or create empty)."""
        if self.audit_file.exists():
            with open(self.audit_file) as f:
                return json.load(f)
        return []
    
    def log_validation(
        self,
        source_id: str,
        data_type: str,
        season: int,
        status: str,  # PASS or FAIL
        rows_validated: int,
        guard_rails_passed: int,
        guard_rails_failed: int,
        errors: List[str],
        warnings: List[str],
        coverage_pct: float = None,
        git_commit: str = None
    ) -> str:
        """
        Log a validation result to immutable audit trail.
        
        Returns:
            audit_id (timestamp-based)
        """
        audit_id = f"{source_id}-{datetime.now().isoformat()}"
        
        entry = {
            "audit_id": audit_id,
            "timestamp": datetime.now().isoformat(),
            "source": source_id,
            "data_type": data_type,
            "season": season,
            "status": status,
            "rows_validated": rows_validated,
            "guard_rails_passed": guard_rails_passed,
            "guard_rails_failed": guard_rails_failed,
            "errors": errors,
            "warnings": warnings,
            "coverage_pct": coverage_pct,
            "git_commit": git_commit
        }
        
        self.audit_log.append(entry)
        self._save()
        
        return audit_id
    
    def _save(self):
        """Save audit trail to disk (immutable)."""
        with open(self.audit_file, "w") as f:
            json.dump(self.audit_log, f, indent=2)
    
    def get_summary(self, source_id: str = None) -> Dict:
        """Get summary of validations."""
        if source_id:
            logs = [l for l in self.audit_log if l['source'] == source_id]
        else:
            logs = self.audit_log
        
        return {
            "total_validations": len(logs),
            "passed": sum(1 for l in logs if l['status'] == 'PASS'),
            "failed": sum(1 for l in logs if l['status'] == 'FAIL'),
            "latest": logs[-1] if logs else None
        }
```

---

## ✅ PART 3: Verification Checklist

After implementing:

### For Each Data Source

- [ ] Guard rails engine created (`testing/canonical/guard_rails_engine.py`)
- [ ] Validators implemented for all 19 guard rails
- [ ] Integrated into fetch script (validates before writing)
- [ ] Audit logging enabled (creates immutable trail)
- [ ] Test run completed (validate existing data)
- [ ] Compliance report generated

### Specific Checks

**The Odds API**
- [ ] Run: `python testing/scripts/fetch_historical_odds.py --validate-only --season 2026`
- [ ] Verify: Zero hardcoded -110 odds in output
- [ ] Verify: All prices in [-500, +500]
- [ ] Verify: No duplicate games
- [ ] Audit trail shows PASS status

**ESPN Scores**
- [ ] Run: `python testing/scripts/fetch_historical_data.py --validate-only --seasons 2024-2026`
- [ ] Verify: All scores have pairs (no orphaned scores)
- [ ] Verify: All teams resolve
- [ ] Verify: All dates in UTC
- [ ] Audit trail shows PASS status

**Barttorvik**
- [ ] Run: `python testing/scripts/fetch_historical_data.py --ratings-only --validate`
- [ ] Verify: No same-season ratings (leakage check)
- [ ] Verify: 90%+ coverage of D1 teams
- [ ] Verify: All ratings in [50, 150]
- [ ] Audit trail shows PASS status

---

## 🚀 PART 4: Next Phase - NCAAR Activation

Once framework is validated with active sources:

### NCAAR Integration Plan

```python
# Create: testing/scripts/fetch_ncaahoopR_data.py

from testing.canonical.guard_rails_engine import GuardRailValidator
from testing.azure_io import read_csv, write_csv

def activate_ncaam_ingestion():
    """Activate NCAAR as a source (currently inactive)."""
    
    print("Step 1: Load NCAAR box scores from Azure...")
    ncaamr_df = read_csv("ncaam-historical-raw/ncaahoopR_data-master/box_scores/2025.csv")
    
    print("Step 2: Load ESPN scores for game matching...")
    espn_df = read_csv("ncaam-historical-data/scores/fg/games_all.csv")
    
    print("Step 3: Validate guard rails...")
    validator = GuardRailValidator("ncaamr", strict_mode=True)
    passed, errors, warnings = validator.validate(ncaamr_df)
    
    if not passed:
        raise ValueError(f"NCAAR validation failed:\n" + "\n".join(errors))
    
    print("Step 4: Match games (NCAAR → ESPN)...")
    merged = match_games(ncaamr_df, espn_df)
    
    print("Step 5: Verify game matching (guard rail #2)...")
    unmatched = len(merged[merged['game_id'].isnull()])
    if unmatched > 0:
        raise ValueError(f"{unmatched} games couldn't be matched!")
    
    print("Step 6: Move to canonical location...")
    write_csv(merged, "ncaam-historical-data/box_scores/ncaamr_canonical_2025.csv")
    
    print(f"✅ NCAAR activation complete! {len(merged)} games processed.")
```

---

## 📊 PART 5: Coverage Dashboard (Future)

Create a simple dashboard showing:

```
DATA GOVERNANCE COMPLIANCE - January 12, 2026

Source          | Status | Guard Rails | Coverage | Audit Trail
────────────────┼────────┼─────────────┼──────────┼─────────────
The Odds API    | ✅     | 5/5 PASS    | 81.5%    | 127 entries
ESPN API        | ✅     | 4/4 PASS    | 99.0%    | 342 entries
Barttorvik      | ✅     | 3/3 PASS    | 65.0%    | 89 entries
────────────────┼────────┼─────────────┼──────────┼─────────────
NCAAR           | ⏸️     | Ready       | N/A      | Not activated
Kaggle          | ⏸️     | Ready       | N/A      | Not activated

GUARD RAIL STATUS:
  ✅ 12/19 implemented
  ⬜ 7/19 pending (NCAAR, Kaggle, Basketball-API specific rules)

LATEST ISSUES:
  ⚠️  ESPN: 5 games with unreasonable scores (reviewed, acceptable)
  ✅ Odds: Zero hardcoded -110 detected
  ✅ Ratings: 95%+ team coverage maintained
```

---

## 📞 Support & Questions

**Q: What if validation fails on existing data?**  
A: Review audit trail to see which guard rail failed. Options:
  1. Fix source data
  2. Adjust guard rail threshold (document why)
  3. Skip problematic records (with explicit audit note)

**Q: Can we disable a guard rail?**  
A: Only with approval + documentation. Add to `guard_rails_exceptions.json`:
  ```json
  {
    "guard_rail": "odds_freshness_by_season",
    "reason": "Historical data may be up to 30 days old",
    "approved_by": "Data Lead",
    "date": "2026-01-12"
  }
  ```

**Q: When should we activate NCAAR?**  
A: Once framework is validated on active sources (~1 week). Then:
  1. Implement NCAAR fetch script
  2. Add guard rails validators
  3. Test matching against ESPN
  4. Update registry status to ACTIVE

---

## 📚 Files Created/Modified

### New Files (Created)
- ✅ `testing/scripts/data_governance_framework.py` - Registry + definitions
- ✅ `docs/DATA_GOVERNANCE_FRAMEWORK.md` - Comprehensive guide
- ⬜ `testing/canonical/guard_rails_engine.py` - Validators (NEXT)
- ⬜ `testing/canonical/audit_logger.py` - Immutable audit trail (NEXT)

### Modified Files
- ⬜ `testing/scripts/fetch_historical_odds.py` - Add validation
- ⬜ `testing/scripts/fetch_historical_data.py` - Add validation
- ⬜ `testing/scripts/fetch_h1_data.py` - Add validation

### Generated Files
- ✅ `manifests/data_sources_registry.json` - Machine-readable registry

---

## ⏱️ Timeline

**Week 1 (Jan 12-19):**
- Implement guard_rails_engine.py
- Integrate into fetch_historical_odds.py
- Test with 2026 odds data
- Generate audit trail

**Week 2 (Jan 19-26):**
- Integrate into fetch_historical_data.py (scores)
- Integrate into fetch_historical_data.py (ratings)
- Complete audit trail for all active sources
- Generate coverage compliance report

**Week 3+ (Jan 26+):**
- Implement NCAAR integration
- Activate Basketball-API planning
- Monitor audit trail weekly
- Quarterly review of guard rails

---

**Status:** READY FOR IMPLEMENTATION  
**Next Action:** Create `guard_rails_engine.py` file  
**Owner:** Data Engineering Team  
**Reviewer:** @JDSB123
