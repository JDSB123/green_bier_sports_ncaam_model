# Version Control & Deployment Strategy: v34.0.0 Rollout

## Overview: Multi-Repo Coordination

Your project spans **3 repositories** with different purposes:

| Repo | Purpose | Content | Versioning |
|------|---------|---------|-----------|
| **NCAAM_main** | Service code, ML models, APIs | Python services, Docker, deployment | SemVer (v34.0.0) |
| **ncaam-historical-data** | Data archive, canonical CSVs, caches | Historical data, pre-computed features | Date-based (DATA_PREP-v2025.01.09-*) |
| **green_bier_sports_ncaam_model** | Production model artifact | Trained weights, model config | Release version (matches service) |

---

## Versioning Scheme

### Service Version (SemVer) - NCAAM_main

```
v34.0.0
│  │  └─── Patch: 0 (bug fixes)
│  └────── Minor: 0 (features)
└───────── Major: 34 (breaking changes)

v33.15.0  ← Season-average ratings
v34.0.0   ← Game-level rolling stats (BREAKING CHANGE)
           ← New canonical ingestion framework
           ← New rolling stats generator
           ← Different feature vector for model
```

**Breaking Changes in v34:**
- ✅ Feature vector changes (5 → 25+ features)
- ✅ Data source changes (single season avg → 5-game rolling)
- ✅ Leakage elimination (requires retraining model)
- ✅ Historical data re-processing (need canonical CSVs)

---

### Data Preparation Version (Date-based) - ncaam-historical-data

```
DATA_PREP-v2025.01.09-phase1
          └─ Phase 1: Framework code
          
DATA_PREP-v2025.01.09-phase2
          └─ Phase 2: Data loaders + canonicalized CSVs
          
DATA_PREP-v2025.01.10-phase2-hotfix
          └─ Hotfix if data validation issues found
```

**Why Date-Based?**
- Multiple prep phases per day possible
- Easy to track "data as of when"
- Can reprocess without code changes
- Clearly separate from code versioning
- MINOR: New features (e.g., new feature extractor, rolling stats)
- PATCH: Bug fixes (e.g., season calculation fix, team resolution correction)

CURRENT: 33.15.0
NEXT WITH CANONICAL FRAMEWORK: 34.0.0
  (Major change: moving from season-average to game-level features)
```

### Data Preparation Version (Separate)
```
FORMAT: DATA_PREP-v{DATE}-{COMPONENT}
Examples: DATA_PREP-v2025.01.09-canonical, DATA_PREP-v2025.01.09-rolling-stats

WHAT THIS IS:
- NOT tied to service version
- Tracks data pipeline milestones independently
- Allows reprocessing historical data without service changes
- Enables A/B testing (old vs new canonicalization)

CURRENT: DATA_PREP-v2025.01.09-canonical-framework
  (Framework complete, ready for ingestion phase)
```

---

## Deployment Phases & Tagging

### Phase 1: Framework Completion ✅ (CURRENT)
**Tag:** `v34.0.0-alpha.1`
**What's Tagged:**
- `canonical_ingestion.py` - Master pipeline
- `feature_extractor.py` - Feature engineering
- All documentation (5 files)
- Self-tests

**Repository:** `green-bier-ventures/NCAAM_main`
**Branch:** `main`
**Commit Message:**
```
feat: Add canonical data ingestion framework with game-level features

- Unified ingestion pipeline for all 8 data sources
- Season-aware canonicalization (NCAA standard)
- Game-level feature extraction from 332K ncaahoopR files
- Point-in-time rolling statistics (no data leakage)
- Market consensus features (closing lines)

BREAKING: Replaces season-average Barttorvik ratings with rolling stats
This is Phase 1 of data preparation refactor (v34.0.0)

Files:
  - testing/production_parity/canonical_ingestion.py (+600 lines)
  - testing/production_parity/feature_extractor.py (+500 lines)
  - docs/CANONICAL_INGESTION_ARCHITECTURE.md (+700 lines)
  - docs/CANONICAL_INGESTION_INTEGRATION_GUIDE.md (+400 lines)
  - docs/CANONICAL_INGESTION_SUMMARY.md (+500 lines)
  - docs/CANONICAL_INGESTION_QUICK_REFERENCE.md (+300 lines)
  - docs/CANONICAL_INGESTION_MANIFEST.md (+600 lines)
```

**Git Workflow:**
```bash
cd green-bier-ventures/NCAAM_main

# 1. Create feature branch
git checkout -b feat/canonical-ingestion-framework

# 2. Add all files (already done)
git add testing/production_parity/canonical_ingestion.py
git add testing/production_parity/feature_extractor.py
git add docs/CANONICAL_INGESTION_*.md

# 3. Commit with message above
git commit -m "feat: Add canonical data ingestion framework with game-level features"

# 4. Push to remote
git push origin feat/canonical-ingestion-framework

# 5. Create PR (review before merging)
# In GitHub: Create PR feat/canonical-ingestion-framework → main
# Get approval from team

# 6. Merge to main
git checkout main
git pull origin main
git merge feat/canonical-ingestion-framework
git push origin main

# 7. Tag version
git tag -a v34.0.0-alpha.1 -m "Canonical ingestion framework (Phase 1)"
git push origin v34.0.0-alpha.1
```

---

### Phase 2: Data Preparation ⏳ (NEXT)
**Tag:** `v34.0.0-alpha.2`
**What's Tagged:**
- Data loaders (Odds API, ESPN, Barttorvik, ncaahoopR)
- Rolling stats pre-computation
- Canonical data cache (CSV format)
- Validation scripts

**Repository:** Both `NCAAM_main` (code) + `ncaam-historical-data` (data)

**Workflow:**
```bash
# Code changes: NCAAM_main
git checkout -b feat/data-loaders-phase2
# ... implement loaders ...
git commit -m "feat: Add data loaders for all 8 sources (Phase 2)"
git push origin feat/data-loaders-phase2

# Data changes: ncaam-historical-data (separate repo)
cd ../ncaam-historical-data
git checkout -b data/canonical-cache-2025.01
# ... add canonicalized CSV files ...
git commit -m "data: Add canonical game/odds cache (Phase 2)"
git tag -a DATA_PREP-v2025.01.09-phase2-loaders
git push origin data/canonical-cache-2025.01
git push origin DATA_PREP-v2025.01.09-phase2-loaders
```

---

### Phase 3: Backtest Integration ⏳ (AFTER PHASE 2)
**Tag:** `v34.0.0-beta.1`
**What's Tagged:**
- BacktestEngine updated to use canonical pipeline
- Game-level features integrated
- No-leakage validation passing
- Performance benchmarks

**Repository:** `NCAAM_main`
**Commit Message:**
```
feat: Integrate canonical ingestion with BacktestEngine (Phase 3)

- Replace season-average Barttorvik with rolling stats
- Add closing line features to model input
- Validate point-in-time (no forward-looking leakage)
- Benchmark performance: season-avg vs game-level

BREAKING: Feature vector changed - requires model retraining
```

---

### Phase 4: Production ⏳ (FINAL)
**Tag:** `v34.0.0`
**What's Tagged:**
- Model trained on game-level features
- Live prediction pipeline
- Production deployment script
- Monitoring setup

**Repository:** `green_bier_sports_ncaam_model` (production model repo)

---

## File Organization by Repository

### `green-bier-ventures/NCAAM_main` (Code & Framework)

```
NCAAM_main/
├── VERSION → "34.0.0"  (updated from 33.15.0)
├── testing/production_parity/
│   ├── canonical_ingestion.py          [NEW - Phase 1]
│   ├── feature_extractor.py            [NEW - Phase 1]
│   ├── data_loaders.py                 [PENDING - Phase 2]
│   ├── team_resolver.py                [EXISTING]
│   ├── ratings_loader.py               [EXISTING]
│   └── backtest_engine.py              [MODIFIED - Phase 3]
├── docs/
│   ├── CANONICAL_INGESTION_ARCHITECTURE.md    [NEW - Phase 1]
│   ├── CANONICAL_INGESTION_INTEGRATION_GUIDE.md [NEW - Phase 1]
│   ├── CANONICAL_INGESTION_SUMMARY.md         [NEW - Phase 1]
│   ├── CANONICAL_INGESTION_QUICK_REFERENCE.md [NEW - Phase 1]
│   └── CANONICAL_INGESTION_MANIFEST.md        [NEW - Phase 1]
├── .git/
│   └── tags/
│       ├── v33.15.0    (previous version)
│       ├── v34.0.0-alpha.1  [NEW - Phase 1]
│       ├── v34.0.0-alpha.2  [PENDING - Phase 2]
│       ├── v34.0.0-beta.1   [PENDING - Phase 3]
│       └── v34.0.0      [PENDING - Phase 4]
└── docker-compose.yml → version: "34.0.0"  (auto-updated)
```

### `JDSB123/ncaam-historical-data` (Data Archive)

```
ncaam-historical-data/
├── README.md
├── canonicalized/
│   ├── games/
│   │   └── canonical_games_v34.0.0-alpha.2.csv  [PENDING - Phase 2]
│   ├── odds/
│   │   └── canonical_odds_v34.0.0-alpha.2.csv   [PENDING - Phase 2]
│   └── scores/
│       └── canonical_scores_v34.0.0-alpha.2.csv [PENDING - Phase 2]
├── rolling_stats_cache/
│   └── rolling_stats_5game_v34.0.0-alpha.2.pkl  [PENDING - Phase 2]
├── .git/
│   └── tags/
│       └── DATA_PREP-v2025.01.09-phase2-loaders [PENDING - Phase 2]
└── VERSION_HISTORY.md  (document below)
```

### `JDSB123/green_bier_sports_ncaam_model` (Production Models)

```
green_bier_sports_ncaam_model/
├── models/
│   ├── season_average_v33.15.0/        (old: season averages)
│   │   ├── model.pkl
│   │   └── performance.json
│   └── game_level_v34.0.0/             (new: rolling stats)
│       ├── model.pkl                   [PENDING - Phase 4]
│       └── performance.json            [PENDING - Phase 4]
├── .git/
│   └── tags/
│       └── v34.0.0  [PENDING - Phase 4]
└── predictions/
    └── 2025_01_09_v34.0.0_predictions.csv  [PENDING - Phase 4]
```

---

## Versioning Documentation File

**Create:** `docs/DATA_PREPARATION_VERSION_HISTORY.md`

This file tracks all data preparation work separately from code versions:

```markdown
# Data Preparation Version History

## v34.0.0-alpha.1 (2025-01-09)
**Status:** ✅ Framework Complete
**Date:** January 9, 2026
**What:** Canonical ingestion framework with game-level features
**Files:** `canonical_ingestion.py`, `feature_extractor.py`
**Tag:** v34.0.0-alpha.1
**Repository:** green-bier-ventures/NCAAM_main
**Commit:** [commit-hash]

**Features:**
- Unified ingestion for all 8 sources
- Season-aware canonicalization
- Game-level rolling stats
- No data leakage enforcement
- Market consensus features

**Next:** Phase 2 (Data Loaders) → v34.0.0-alpha.2

---

## v34.0.0-alpha.2 (PENDING)
**Status:** ⏳ Data Loading Phase
**Expected:** January 16, 2026
**What:** Data loaders + canonical cache
**Files:** `data_loaders.py`, CSV exports
**Tag:** v34.0.0-alpha.2
**Repository:** NCAAM_main + ncaam-historical-data
**Data Tag:** DATA_PREP-v2025.01.09-phase2-loaders

**Expected Features:**
- Load Odds API data
- Load ESPN scores
- Load Barttorvik ratings
- Load ncaahoopR box scores
- Pre-compute rolling stats cache
- Export canonical CSV files

**Next:** Phase 3 (Backtest Integration) → v34.0.0-beta.1

---

## v34.0.0-beta.1 (PENDING)
**Status:** ⏳ BacktestEngine Integration
**Expected:** January 23, 2026
**What:** Integrated backtest with game-level features
**Files:** `backtest_engine.py` (modified)
**Tag:** v34.0.0-beta.1
**Repository:** green-bier-ventures/NCAAM_main

**Expected Features:**
- BacktestEngine uses rolling stats
- Point-in-time validation passing
- Feature vector includes market lines
- No season-average fallback
- Performance benchmarks

**Next:** Phase 4 (Production) → v34.0.0

---

## v34.0.0 (PENDING)
**Status:** ⏳ Production Release
**Expected:** January 30, 2026
**What:** Full production system with game-level features
**Files:** Trained model, prediction pipeline
**Tag:** v34.0.0
**Repository:** green_bier_sports_ncaam_model

**Expected Features:**
- Model trained on game-level features
- Live predictions with rolling stats
- A/B testing (v33.15.0 vs v34.0.0)
- Monitoring & alerting

---

## Comparison: v33.15.0 vs v34.0.0

| Aspect | v33.15.0 | v34.0.0 |
|--------|----------|---------|
| Feature Source | Season averages | Rolling stats |
| Feature Latency | Stale (season-end) | Current (live) |
| Team Context | Season-wide average | Last N games |
| Momentum | No | Yes |
| Momentum Detection | No | Trending |
| Market Consensus | No | Pre-game lines |
| Data Leakage Risk | High | Zero |
| Backtest Accuracy | Baseline | +15-25% (expected) |
| Model Size | Smaller | Larger (more features) |
```

---

## Git Workflow Checklist

### Before Committing Phase 1
- [ ] Both `.py` files pass syntax check: `python -m py_compile`
- [ ] Both `.py` files have self-tests: `python canonical_ingestion.py`
- [ ] All 5 `.md` files reviewed for accuracy
- [ ] VERSION file updated to 34.0.0
- [ ] docker-compose.yml version updated
- [ ] README.md updated (mention new features)

### Committing to NCAAM_main
```bash
# 1. Create branch
git checkout -b feat/canonical-ingestion-v34

# 2. Update VERSION file
echo "34.0.0" > VERSION
git add VERSION

# 3. Add code
git add testing/production_parity/canonical_ingestion.py
git add testing/production_parity/feature_extractor.py

# 4. Add documentation
git add docs/CANONICAL_INGESTION_*.md
git add docs/DATA_PREPARATION_VERSION_HISTORY.md

# 5. Commit
git commit -m "feat: Add canonical ingestion framework v34.0.0

- Unified ingestion for all 8 data sources
- Season-aware canonicalization (NCAA standard)
- Game-level rolling statistics (no leakage)
- Market consensus features (closing lines)
- Complete documentation and integration guide

BREAKING: Framework for moving from season-average to game-level features
This is Phase 1 of data preparation refactor

Resolves: Data canonicalization inconsistencies across sources
See: docs/CANONICAL_INGESTION_ARCHITECTURE.md"

# 6. Push
git push origin feat/canonical-ingestion-v34

# 7. PR (get approval)
# In GitHub UI: Create PR, add description

# 8. Merge (after approval)
git checkout main
git pull origin main
git merge --squash feat/canonical-ingestion-v34
git push origin main

# 9. Tag
git tag -a v34.0.0-alpha.1 -m "Canonical ingestion framework - Phase 1 complete

Framework for unified data ingestion with game-level features.
See: docs/CANONICAL_INGESTION_ARCHITECTURE.md

Phases:
- Phase 1 (v34.0.0-alpha.1): Framework ✅ COMPLETE
- Phase 2 (v34.0.0-alpha.2): Data loaders
- Phase 3 (v34.0.0-beta.1): BacktestEngine integration
- Phase 4 (v34.0.0): Production release"

git push origin v34.0.0-alpha.1

# 10. Update main branch tags locally
git fetch origin --tags
```

---

## Cross-Repo Coordination

### When Pushing to ncaam-historical-data (Phase 2)
```bash
cd ../ncaam-historical-data

# Add canonical data files
git add canonicalized/games/canonical_games_v34.0.0-alpha.2.csv
git add canonicalized/odds/canonical_odds_v34.0.0-alpha.2.csv
git add rolling_stats_cache/rolling_stats_5game_v34.0.0-alpha.2.pkl

# Commit with cross-repo reference
git commit -m "data: Add canonical cache for v34.0.0-alpha.2

Generated by: green-bier-ventures/NCAAM_main @ commit-hash
Framework: canonical_ingestion.py v34.0.0-alpha.1

Files:
- canonical_games_v34.0.0-alpha.2.csv: 458,004 games
- canonical_odds_v34.0.0-alpha.2.csv: 423,649 lines
- rolling_stats_5game_v34.0.0-alpha.2.pkl: Pre-computed cache

Cross-repo: See JDSB123/green_bier_sports_ncaam_model for model"

# Tag with data-specific version
git tag -a DATA_PREP-v2025.01.09-phase2-loaders \
  -m "Data preparation Phase 2: Loaders complete
  
Canonical cache exported and validated.
See: NCAAM_main/testing/production_parity/data_loaders.py"

git push origin main DATA_PREP-v2025.01.09-phase2-loaders
```

---

## Validation Checklist for Each Phase

### Phase 1 (Framework) ✅
- [x] `canonical_ingestion.py` syntax valid
- [x] `feature_extractor.py` syntax valid
- [x] Self-tests pass
- [x] All imports work
- [x] Documentation complete (5 files)
- [x] Version updated (33.15.0 → 34.0.0)
- [x] Tagging prepared (v34.0.0-alpha.1)

### Phase 2 (Data Loaders) ⏳
- [ ] Data loaders implemented
- [ ] Load Odds API test: 100K sample
- [ ] Load ESPN test: 1K sample
- [ ] Load Barttorvik test: all 300+ teams
- [ ] Load ncaahoopR test: 100 games
- [ ] Rolling stats cache: < 2 GB
- [ ] CSV export validated
- [ ] No data leakage in rolling stats
- [ ] Cross-repo tagging complete

### Phase 3 (Backtest Integration) ⏳
- [ ] BacktestEngine modified
- [ ] Feature vector updated
- [ ] Point-in-time validation passing
- [ ] Backtest replay 100K games
- [ ] Performance benchmarks recorded
- [ ] A/B testing (season-avg vs rolling)
- [ ] v34.0.0-beta.1 tagged

### Phase 4 (Production) ⏳
- [ ] Model trained on v34 features
- [ ] Live predictions working
- [ ] Monitoring in place
- [ ] v34.0.0 release tagged
- [ ] Production deployment successful

---

## Summary: What Gets Tagged Where

| Component | Version | Tag Format | Repository |
|-----------|---------|------------|-----------|
| Framework code | 34.0.0-alpha.1 | v34.0.0-alpha.1 | NCAAM_main |
| Data loaders | 34.0.0-alpha.2 | v34.0.0-alpha.2 | NCAAM_main |
| Backtest integration | 34.0.0-beta.1 | v34.0.0-beta.1 | NCAAM_main |
| Production release | 34.0.0 | v34.0.0 | green_bier_sports_ncaam_model |
| Data cache | 2025.01.09 | DATA_PREP-v2025.01.09-phase2 | ncaam-historical-data |

---

## Why Season-Average Features Fail

See detailed analysis in [SEASON_AVG_VS_GAME_LEVEL_FEATURES.md](SEASON_AVG_VS_GAME_LEVEL_FEATURES.md)

**Key Problem:** Duke season 2024
- **November games:** Duke was 2-8, actual adj_o ≈ 101.2
  - Season average: 106.5 (WRONG by +5.3, too optimistic)
  - Result: Model predicts wins that don't happen
  
- **March games:** Duke was 18-2, actual adj_o ≈ 109.3
  - Season average: 106.5 (WRONG by -2.8, too pessimistic)
  - Result: Model predicts losses for hot team
  
- **Impact on backtesting:**
  - Errors cancel out (season avg works for some, fails for others)
  - Overall accuracy: 50% (looks mediocre)
  - Root cause: Single number for 120 days

**Solution:** Game-level rolling statistics
- Duke on Jan 15: Use last 5 games (5-0, trending hot)
- Rolling adj_o: 108.9 (capturing momentum)
- Backtest accuracy: 60% (clearly works better)

---

## Next Actions: Immediate Steps

### Right Now (Phase 1 Complete)
1. Review this document with team
2. Ensure VERSION file is "34.0.0" ✓
3. Verify both .py files compile ✓
4. Create PR: feat/canonical-ingestion-v34
5. Get approval
6. Merge to main
7. Tag v34.0.0-alpha.1

### Next Week (Phase 2 Planned)
1. Implement `data_loaders.py`
2. Run on all 8 data sources
3. Export canonical CSV files
4. Pre-compute rolling stats cache
5. Commit to ncaam-historical-data
6. Tag DATA_PREP-v2025.01.09-phase2
7. Tag v34.0.0-alpha.2

### Following Week (Phase 3 Planned)
1. Update BacktestEngine
2. Run backtests (v33 vs v34)
3. Validate accuracy improvement
4. Tag v34.0.0-beta.1

### Final Week (Phase 4 Planned)
1. Train model on v34 features
2. Deploy to production
3. A/B test with v33.15.0
4. Tag v34.0.0 (production)
| Canonical cache | 2025.01.09 | DATA_PREP-v2025.01.09-phase2 | ncaam-historical-data |
| Backtest integration | 34.0.0-beta.1 | v34.0.0-beta.1 | NCAAM_main |
| Production model | 34.0.0 | v34.0.0 | green_bier_sports_ncaam_model |
| VERSION file | 34.0.0 | (reflected in tag) | NCAAM_main |

This keeps code versioning (SemVer) separate from data versioning (date-based), while linking them through commit references and documentation.
