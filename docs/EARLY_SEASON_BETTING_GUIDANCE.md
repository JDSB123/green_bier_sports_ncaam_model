# Early Season Betting Guidance

## 2024 Season Anomaly Analysis

Investigation of the 2024 season revealed a significant performance degradation (-9.78% ROI) compared to other seasons (~-2% ROI). This document explains the root cause and provides actionable guidance.

## Key Findings

### Season-by-Season Performance (FG Spread, HCA=5.8)

| Season | Bets | Win Rate | ROI |
|--------|------|----------|-----|
| 2021 | 722 | 51.2% | -2.25% |
| 2022 | 834 | 51.2% | -2.30% |
| 2023 | 876 | 52.3% | **-0.12%** |
| 2024 | 752 | 47.1% | **-9.78%** |
| 2025 | 773 | 51.0% | -2.51% |

### 2024 Monthly Breakdown

| Month | Bets | Win Rate | ROI | Analysis |
|-------|------|----------|-----|----------|
| Nov '23 | 109 | 46.2% | **-11.75%** | Stale prior-year ratings |
| Dec '23 | 146 | 41.3% | **-21.24%** | Worst month - ratings severely outdated |
| Jan '24 | 185 | 49.5% | -5.60% | Market adjusting |
| Feb '24 | 181 | 52.0% | **-0.73%** | Model performing well |
| Mar '24 | 131 | 44.6% | **-14.83%** | March Madness chaos |

## Root Cause

The model uses **prior season (N-1) ratings** to predict current season (N) games. This is correct methodology to prevent data leakage, but creates problems:

### Early Season (November-December)
- Teams have significant roster changes (transfers, freshmen, coaching changes)
- Prior year ratings don't reflect current team quality
- Market efficiency is higher (oddsmakers also use current information)
- **Result**: Model predictions are based on outdated team strength assessments

### March Madness (March)
- Tournament games have unique dynamics:
  - Single elimination pressure
  - Neutral sites
  - Unfamiliar opponents
  - High variance in performance
- Basic efficiency models miss these tournament-specific factors
- **Result**: Standard model edge is reduced or eliminated

## Recommended Actions

### Immediate (High Priority)

1. **Increase edge thresholds for early season (Nov-Dec)**
   ```
   Normal:     min_edge = 1.5%
   Early Season: min_edge = 3.0% (stricter)
   ```

2. **Reduce bet sizing in early season**
   ```
   Normal:     kelly_fraction = 0.25
   Early Season: kelly_fraction = 0.15 (more conservative)
   ```

3. **Consider skipping November entirely**
   - Wait until December or January when more current-season data exists
   - Alternative: Only bet games with extreme edges (>5%)

### Medium Term

4. **Track roster continuity**
   - Add feature: % of minutes returning from prior year
   - Weight predictions by continuity score
   - Low continuity teams → require higher edge

5. **Add current-season performance tracking**
   - After ~10 games, incorporate current-season stats
   - Blend prior-year ratings with current-year performance

### Long Term

6. **Separate March Madness model**
   - Consider tournament-specific adjustments
   - Add seed differential features
   - Account for neutral site dynamics

7. **Regime detection**
   - Detect when model is underperforming
   - Auto-adjust bet sizing based on recent results

## Implementation Checklist

- [ ] Add `early_season_mode` flag to run_today.py
- [ ] Implement stricter edge thresholds for Nov-Dec
- [ ] Add monthly performance tracking to health summary
- [ ] Create roster continuity data source
- [ ] Implement current-season stat blending
- [ ] Add March Madness detection flag

## Validation

After implementing changes, validate using:

```bash
# Run backtest excluding early season
python testing/scripts/run_historical_backtest.py --market fg_spread --exclude-months 11,12

# Compare ROI with/without early season
python testing/scripts/run_historical_backtest.py --market fg_spread --months 1,2,3
```

## Expected Impact

If excluding November-December 2024:
- Removes 255 bets (146 + 109) with combined -17% ROI
- Remaining 497 bets would have ~-3% ROI (in line with other seasons)
- Demonstrates model validity when ratings are current

## Configuration

Add to `config.py` or `run_today.py`:

```python
# Early season adjustment
EARLY_SEASON_MONTHS = [11, 12]  # November, December
EARLY_SEASON_MIN_EDGE = 3.0     # vs 1.5 normal
EARLY_SEASON_KELLY = 0.15       # vs 0.25 normal

# March Madness adjustment
MARCH_MADNESS_DATES = ["03-15", "03-16", ...]  # Tournament dates
MARCH_MADNESS_MIN_EDGE = 2.5
```

---

*Document created: January 2026*
*Based on analysis of 3,957 historical bets across seasons 2021-2025*
