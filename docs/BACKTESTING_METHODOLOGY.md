# NCAAM Backtesting Methodology

**Version:** 1.0  
**Date:** January 2026  
**Status:** Production-Ready

---

## Executive Summary

This document describes the backtesting methodology for NCAAM prediction models. The system is designed with **zero tolerance for data leakage** and follows statistically sound practices.

### Key Principles

1. **No Leakage**: Only pre-game data used for predictions
2. **No Assumptions**: Actual odds required (no -110 fallback)
3. **No Placeholders**: Missing data = skip, not fill
4. **No Season Averages**: Only rolling windows (last 3, 5, 10 games)
5. **CLV Tracking**: Gold standard metric for model quality

---

## Architecture

### Data Flow

```
Historical Data Sources
    |
    v
Point-in-Time Ratings Lookup
    |
    v
Walk-Forward Validation
    |
    v
Independent Model Training (4 models)
    |
    v
CLV-Enhanced Backtesting
    |
    v
Production Integration
```

### Independent Models

We train 4 completely independent models:

| Model | Target | Key Features |
|-------|--------|--------------|
| FG Spread | Home covers spread | Efficiency diff, HCA=5.8 |
| FG Total | Over hits | Tempo, combined efficiency |
| 1H Spread | Home covers 1H | Independent HCA=3.6 |
| 1H Total | 1H over hits | 1H-specific calibration |

Each model has its own:
- Feature set
- Hyperparameters
- Calibration constants
- Performance metrics

---

## Leakage Prevention

### What is Leakage?

Leakage occurs when future information is used to make predictions about past events. This artificially inflates backtest performance.

### Common Leakage Sources

| Source | Problem | Solution |
|--------|---------|----------|
| End-of-season ratings | Contains future games | Point-in-time ratings |
| Closing lines for decisions | Not available pre-game | Use opening lines |
| Season averages | Includes future games | Rolling windows only |
| Cross-validation | Random splits mix time | Walk-forward validation |

### Point-in-Time Ratings

For a game on date D, we use ratings calculated from games BEFORE date D:

```python
# CORRECT
ratings = lookup.get_team_ratings(team, game_date)
# Returns ratings from most recent snapshot BEFORE game_date

# WRONG
ratings = end_of_season_ratings[team]
# Contains information from games AFTER game_date
```

### Walk-Forward Validation

Training data is always from BEFORE test data:

```
Train: Seasons 2020-2022 -> Test: Season 2023
Train: Seasons 2020-2023 -> Test: Season 2024
Train: Seasons 2020-2024 -> Test: Season 2025
```

---

## CLV (Closing Line Value)

### Why CLV is the Gold Standard

The closing line is the market's most accurate prediction. Consistently beating the closing line indicates sharp betting.

### CLV Calculation

```python
# For spread bets on home:
clv = opening_line - closing_line
# Positive = line moved against home = we got value

# For over bets:
clv = closing_line - opening_line
# Positive = line moved up = we got value on over
```

### Interpreting CLV

| CLV Positive Rate | Interpretation |
|-------------------|----------------|
| > 55% | Sharp (consistently beating market) |
| 50-55% | Slightly sharp |
| 45-50% | Neutral |
| < 45% | Square (market is better) |

### CLV vs Win Rate

CLV is a better long-term indicator than win rate:

- High CLV + moderate win rate = sustainable edge
- Low CLV + high win rate = likely lucky, will regress

---

## Data Requirements

### Required Columns

| Column | Description | Required? |
|--------|-------------|-----------|
| `game_date` | Date of game | Yes |
| `home_team` | Home team (canonical) | Yes |
| `away_team` | Away team (canonical) | Yes |
| `{market}` | Opening line | Yes |
| `{market}_closing` | Closing line | For CLV |
| `{market}_home_price` | Actual odds (home) | Yes |
| `{market}_away_price` | Actual odds (away) | Yes |
| `actual_margin` | Game result | Yes |
| `home_adj_o`, etc. | Barttorvik ratings | Yes |

### Missing Data Policy

**No placeholders.** Missing data = skip the game.

- Missing opening line: Skip
- Missing actual odds: Skip
- Missing ratings: Skip
- Missing result: Skip

---

## Feature Engineering

### Allowed Features (Pre-Game Only)

1. **Barttorvik Ratings** (point-in-time)
   - AdjO, AdjD, Tempo, Barthag
   - Four Factors (EFG, TOR, ORB, FTR)
   - WAB, SOS

2. **Rolling Window Features** (last N games)
   - Last 3, 5, 10 game averages
   - NOT season averages

3. **Market Features** (opening only)
   - Opening line (for edge calculation)
   - Opening odds

### Forbidden Features

- Closing lines (for bet decision)
- Post-game statistics
- Season averages
- End-of-season ratings

---

## Model Training

### Hyperparameters

Default XGBoost settings optimized for betting:

```python
{
    "max_depth": 4,           # Shallow = less overfitting
    "learning_rate": 0.05,    # Slow = more stable
    "n_estimators": 200,      # Moderate ensemble
    "min_child_weight": 10,   # Require significant samples
    "subsample": 0.8,         # Row sampling
    "colsample_bytree": 0.8,  # Column sampling
    "reg_alpha": 0.1,         # L1 regularization
    "reg_lambda": 1.0,        # L2 regularization
}
```

### Evaluation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Accuracy | > 52% | Classification accuracy |
| AUC-ROC | > 0.55 | Discrimination ability |
| Log Loss | < 0.69 | Probability calibration |
| Brier Score | < 0.25 | Calibration quality |

---

## Scripts Reference (Current)

### Data Integrity Gate (Required)

```bash
# Verify checksums, team aliases, anti-leakage rule
python testing/verify_data_integrity.py
```

### Canonical Backtest Dataset Build

```bash
# Build canonical backtest dataset (Azure)
python testing/scripts/build_backtest_dataset_canonical.py
```

### Historical Backtest

```bash
# Run historical backtest (all or single market)
python testing/scripts/run_historical_backtest.py --market fg_spread
```

### CLV Backtest

```bash
# Run CLV backtest
python testing/scripts/run_clv_backtest.py --market fg_spread

# Use trained ML model (optional)
python testing/scripts/run_clv_backtest.py --market fg_spread --use-ml-model
```

### ML Training (Optional)

```bash
# Train ML probability models (optional)
python services/prediction-service-python/scripts/train_ml_models.py
```

**Note:** Walk-forward and point-in-time lookup scripts are planned; until then, rely on the anti-leakage rule enforced in the canonical datasets and the integrity gate above.

---

## Production Integration

### Loading Trained Models (Optional)

```python
from app.ml.model_loader import ProductionModelLoader

loader = ProductionModelLoader()
model_info = loader.get_model("fg_spread")
proba = model_info.model.predict_proba([features])[0][1]
```

### CLV Capture in Production

```python
from app.clv_capture import capture_pregame_closing_lines

# Run 5 min before tip-off
result = capture_pregame_closing_lines(engine, lookahead_minutes=10)
```

---

## Validation Checklist

Before running a backtest, verify:

- [ ] Point-in-time ratings are used (not end-of-season)
- [ ] Opening lines used for bet decisions
- [ ] Closing lines captured for CLV
- [ ] Actual odds used (no -110 assumption)
- [ ] Walk-forward splits (train < test)
- [ ] No season averages in features
- [ ] Missing data skipped (not filled)

---

## Expected Performance

### Realistic Expectations

| Metric | Target | Why |
|--------|--------|-----|
| Win Rate | 52-55% | Beats -110 juice |
| ROI | 2-5% | Sustainable edge |
| CLV Positive | > 50% | Indicates sharp betting |

### What to Watch For

**Suspicious Results:**
- Win rate > 60% (likely leakage)
- ROI > 20% (likely leakage)
- Huge sample sizes with high performance

**Healthy Results:**
- Moderate win rate (52-56%)
- Consistent across seasons
- CLV correlates with outcomes

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial methodology document |

---

## References

- [MODEL_IMPROVEMENT_ROADMAP.md](MODEL_IMPROVEMENT_ROADMAP.md) - Future improvements
- [SINGLE_SOURCE_OF_TRUTH.md](SINGLE_SOURCE_OF_TRUTH.md) - Data architecture
- [BACKTEST_VALIDATION_REPORT.md](validation/BACKTEST_VALIDATION_REPORT.md) - Validation results
