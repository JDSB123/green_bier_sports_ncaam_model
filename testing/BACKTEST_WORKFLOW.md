# Backtest Workflow Guide
## Non-Disruptive Testing for NCAAM Model

This document explains how to run backtests without disrupting production.

---

## Golden Rule

> **Never modify production code until backtests validate changes**

```
testing/              ← Work here for backtests
├── production_parity/
│   ├── backtest_engine.py    # Core backtest framework
│   ├── roi_simulator.py      # ROI/betting simulation
│   └── audit_logs/           # All results saved here
├── BACKTEST_TRACKING.md      # Decision log
└── run_backtest_suite.py     # CLI entry point

services/             ← Only modify after validation
└── prediction-service-python/
    └── app/predictors/       # Production models
```

---

## Quick Start

### 1. Run Calibration Validation

Tests if current calibrations produce ~0 bias:

```powershell
cd c:\Users\JB\green-bier-ventures\NCAAM_main

# Test across multiple seasons
python testing/run_backtest_suite.py calibration --seasons 2022 2023 2024 2025
```

**What you want to see:**
- Bias close to 0.0 for each model
- Consistent MAE across seasons

### 2. Run ROI Simulation

Tests if model edge translates to profit:

```powershell
# Test with historical odds (2020-2021 season available)
python testing/run_backtest_suite.py roi --seasons 2021
```

**What you want to see:**
- Positive ROI at higher edge thresholds
- Win rate > 52.4% (breakeven at -110)

### 3. Run Full Validation

Complete suite before any deployment:

```powershell
python testing/run_backtest_suite.py full
```

---

## Anti-Leakage Rules

The backtest system enforces strict anti-leakage:

| Game Date | Game Season | Ratings Used |
|-----------|-------------|--------------|
| 2024-01-15 | 2024 | 2023 FINAL |
| 2023-11-20 | 2024 | 2023 FINAL |
| 2023-03-18 | 2023 | 2022 FINAL |

This prevents artificially inflated results.

---

## When to Bump Version

✅ **DO bump version when:**
- Backtest validates change across 3+ seasons
- Bias is corrected (target: ±0.5)
- ROI improves or stays neutral
- Results documented in BACKTEST_TRACKING.md

❌ **DON'T bump version when:**
- Testing single season only
- Results are inconclusive
- No documentation
- Rushed or untested changes

---

## Version Bump Checklist

Before bumping from vX.Y.Z to vX.Y.(Z+1):

1. [ ] Run `python testing/run_backtest_suite.py full`
2. [ ] Review results in `testing/production_parity/audit_logs/`
3. [ ] Update `testing/BACKTEST_TRACKING.md` with results
4. [ ] Verify all model biases < ±1.0
5. [ ] Commit backtest results to git
6. [ ] THEN update `VERSION` file and push

---

## Data Requirements

### Historical Ratings
Located in: `ncaam_historical_data_local/ratings/raw/barttorvik/barttorvik_YYYY.json`

Required seasons: 2019-2025 (for testing 2020-2026)

### Historical Games
Located in: `ncaam_historical_data_local/canonicalized/scores/fg/games_all_canonical.csv`

Columns needed:
- `date`, `home_team`, `away_team`
- `home_score`, `away_score`
- Optional: `h1_home`, `h1_away` (for H1 models)

### Historical Odds
Located in: `ncaam_historical_data_local/odds/normalized/odds_consolidated_canonical.csv`

Columns needed:
- `commence_time`, `home_team`, `away_team`
- `spread`, `total`
- Optional: `h1_spread`, `h1_total`

---

## Output Files

All outputs go to `testing/production_parity/audit_logs/`:

```
audit_logs/
├── backtest_audit_YYYYMMDD_HHMMSS.csv    # Per-game predictions
├── backtest_audit_YYYYMMDD_HHMMSS.json   # Summary stats
└── full_validation_YYYYMMDD_HHMMSS.json  # Full suite results
```

---

## Troubleshooting

### "No historical odds found"
→ Ensure canonical odds exist under `ncaam_historical_data_local/odds/normalized/`

### "Games file not found"
→ Check `ncaam_historical_data_local/canonicalized/scores/fg/games_all_canonical.csv` exists

### High bias after calibration
→ Calibration may need adjustment, iterate in backtest

### Import errors
→ Run from NCAAM_main root: `cd c:\Users\JB\green-bier-ventures\NCAAM_main`
