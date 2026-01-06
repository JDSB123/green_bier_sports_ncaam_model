# Backtest Tracking Document
## NCAAM Model - Testing Log

This document tracks all backtest runs, results, and decisions.
Production code is NOT modified until backtests validate changes.

---

## Current Production State

| Attribute | Value |
|-----------|-------|
| Version | 33.12.0 |
| FG Total Calibration | -9.5 |
| H1 Total Calibration | -11.8 |
| FG Spread Calibration | +0.3 |
| H1 Spread Calibration | +0.3 |
| Last Deployed | 2026-01-05 |

---

## Backtest Run Log

### Run #1 - Initial Calibration Validation (2026-01-05)
**Purpose:** Establish bias corrections for production model

| Model | Games | MAE | Bias Before | Calibration Applied | Bias After |
|-------|-------|-----|-------------|---------------------|------------|
| FG Spread | 3,222 | 10.16 | -0.3 | +0.3 | 0.0 |
| FG Total | 3,222 | 14.64 | +7.0 | -9.5 | -2.5* |
| H1 Spread | 3,222 | 7.85 | -0.3 | +0.3 | 0.0 |
| H1 Total | 3,222 | 8.52 | +11.8 | -11.8 | 0.0 |

*FG Total overcorrected slightly - may need adjustment

---

## Pending Tests

### Test A: ROI Simulation with Historical Odds
- **Status:** NOT STARTED
- **Data Available:** 2020-2021 season odds
- **Purpose:** Determine if model edge translates to profit
- **Thresholds to Test:** 1.0, 1.5, 2.0, 2.5, 3.0+

### Test B: Calibration Validation with New Values
- **Status:** NOT STARTED  
- **Purpose:** Verify -9.5/-11.8 calibrations produce ~0 bias
- **Seasons:** 2021-2025 (using prior season ratings)

### Test C: Edge Threshold Optimization
- **Status:** NOT STARTED
- **Purpose:** Find optimal minimum edge for each model
- **Current Thresholds:** 2.0 across all models (need validation)

---

## Decision Log

| Date | Decision | Rationale | Version Change |
|------|----------|-----------|----------------|
| 2026-01-05 | Applied -9.5/-11.8 calibrations | Historical backtest showed persistent bias | 33.11.0 → 33.12.0 |
| | | | |

---

## Version Bump Criteria

Only bump version and deploy when:
1. ✅ Backtest validates change across 3+ seasons
2. ✅ No data leakage in methodology
3. ✅ Change documented in this file
4. ✅ Results reviewed before commit
