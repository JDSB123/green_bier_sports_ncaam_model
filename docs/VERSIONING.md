# NCAAM Prediction Model - Versioning Strategy

## Overview

This document outlines the versioning strategy for the NCAAM prediction model system.
All components follow semantic versioning (SemVer) with model-specific extensions.

## Version Format

```
v{MAJOR}.{MINOR}.{PATCH}[-{MODEL_TAG}]
```

## Single Source of Truth

- The repository root contains a `VERSION` file with the current semantic version (e.g., `33.6.2`).
- Python modules (`app/__init__.py`, predictors, config) read directly from this file at runtime.
- Tooling that needs the container tag should prefix the raw value with `v` (handled automatically in the GitHub Actions workflow and `azure/deploy.ps1`).
- When bumping the model, update `VERSION` first, then rerun the workflow so images, documentation, and runtime metadata stay aligned.

### Components

| Component | Description |
|-----------|-------------|
| MAJOR | Breaking API changes, major model architecture changes |
| MINOR | New features, model calibration updates, backtesting improvements |
| PATCH | Bug fixes, documentation, minor tweaks |
| MODEL_TAG | Optional tag for model-specific versions (e.g., `spread`, `total`) |

## Current Version

**v33.6.2** - Rest-day compatibility and Azure image alignment

## Version History

### v33.6.2 (2025-12-28)
- Added backward-compatible rest-day accessors (supports `days_rest` and legacy `days_since_game`).
- Updated Azure defaults and docs to deploy image tag v33.6.2 (prevents rollback to v33.6.1).

### v33.6.1 (2025-12-27)
- Fixed 1H Total confidence (0.52 → 0.68) - was below 0.65 threshold
- Fixed MIN_EDGE alignment across all models:
  - FG Spread: 7.0 → 2.0 (was too conservative)
  - FG Total: 2.0 → 3.0 (aligned with backtest)
  - H1 Total: 1.5 → 2.0 (aligned with backtest)
- Added extreme total handling thresholds
- Added CLV (Closing Line Value) tracking infrastructure
- Added comprehensive unit tests for all predictors

### v33.6.0 (2024-12-24)
- All 4 models independently backtested with real ESPN data
- FG Spread: HCA=5.8 (from 3,318-game backtest)
- FG Total: Calibration=+7.0
- H1 Spread: HCA=3.6 (from 904-game backtest)
- H1 Total: Calibration=+2.7 (from 562-game backtest)

### v33.5.0 (2024-12-24)
- Cleanup: Removed 7 stale/duplicate predictor files
- Canonical models established: fg_total.py, fg_spread.py, h1_total.py, h1_spread.py

### v33.4.0 (2024-12-24)
- ROOT CAUSE FIX: Removed incorrect total_calibration_adjustment (-4.6)
- Fixed league_avg_tempo: 68.5 -> 67.6
- Fixed league_avg_efficiency: 106.0 -> 105.5

### v33.3.0 (2024-12-24)
- Real odds backtest: 313 games with DraftKings/FanDuel lines
- Updated min_spread_edge: 7.0 -> 3.0
- Updated min_total_edge: 999 -> 11.0 (now profitable)

### v33.1.0 (2024-12-23)
- CALIBRATED: HCA increased from 3.2 to 4.7 (4,194-game backtest)
- CALIBRATED: Total adjustment -4.6 to fix over-prediction bias

### v33.0.0 (2024-12-22)
- Consolidated Docker architecture
- Single entry point (predict.bat)
- Explicit HCA values (what you see is what gets applied)

## Model Update Process

### 1. Backtest Phase
- Run backtests on historical data (minimum 500 games)
- Document MAE, direction accuracy, ROI metrics
- Compare against previous model version

### 2. Calibration Phase
- Update HCA or calibration values if needed
- Run validation tests (`pytest tests/`)
- Update config.py with new values

### 3. Version Bump
- Update version in `config.py`: `service_version`
- Update version in `predictors/*.py`: `MODEL_VERSION`
- Add entry to this document

### 4. Deployment
- Build new Docker image
- Push to Azure Container Registry
- Update Container Apps

## File Locations

| File | Version Field |
|------|---------------|
| `app/config.py` | `service_version` (Settings class) |
| `app/predictors/fg_spread.py` | `MODEL_VERSION` |
| `app/predictors/fg_total.py` | `MODEL_VERSION` |
| `app/predictors/h1_spread.py` | `MODEL_VERSION` |
| `app/predictors/h1_total.py` | `MODEL_VERSION` |

## Git Tags

Each release should be tagged:
```bash
git tag -a v33.6.0 -m "All 4 models independently backtested"
git push origin v33.6.0
```

## Container Image Tags

Docker images use the format:
```
ncaamstablegbsvacr.azurecr.io/ncaam-prediction:v{VERSION}
ncaamstablegbsvacr.azurecr.io/ncaam-prediction:latest
```

## API Version Header

The `/health` endpoint returns the current version:
```json
{
  "service": "prediction-service",
  "version": "33.6.1",
  "status": "ok"
}
```

## Model Independence

Each prediction model is versioned independently:

| Model | Version | HCA/Calibration | Backtest Games |
|-------|---------|-----------------|----------------|
| FG Spread | 33.6.1 | HCA=5.8, MIN_EDGE=2.0 | 3,318 |
| FG Total | 33.6.1 | Cal=+7.0, MIN_EDGE=3.0 | 3,318 |
| H1 Spread | 33.6.1 | HCA=3.6, MIN_EDGE=3.5 | 904 |
| H1 Total | 33.6.1 | Cal=+2.7, MIN_EDGE=2.0 | 562 |

## Breaking Changes Policy

**MAJOR version bumps** are required for:
- API endpoint changes (removed/renamed)
- Request/response schema changes
- Prediction formula changes that affect output format
- Database schema migrations that aren't backwards-compatible

**MINOR version bumps** are appropriate for:
- New endpoints
- Model recalibration
- New features (opt-in)
- Performance improvements

**PATCH version bumps** are for:
- Bug fixes
- Documentation updates
- Dependency updates (non-breaking)
