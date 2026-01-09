# NCAAM Model Validation Report

**Date:** January 2026
**Model Version:** v33.6.5 (validated; current release is v33.11.0)
**Validation Type:** No-Leakage Rolling Window

---

## Executive Summary

This report documents a comprehensive validation of the NCAAM prediction model using **strict temporal separation** to prevent data leakage. Previous backtests may have used end-of-season ratings to predict games within the same season, inflating apparent performance.

### Key Findings

| Metric | Previous Claims | Validated Results | Notes |
|--------|-----------------|-------------------|-------|
| **Spread Direction** | 71.9% | **68.7%** | Late-season, 10+ games |
| **Spread ROI** | +18.5% | **+20-31%** | Small sample (83 bets) |
| **Total ROI** | +18.3% | **+3-6%** | Much lower than claimed |
| **Sample Size** | 3,318 games | 83-86 bets | With edge filters |

---

## Methodology

### Anti-Leakage Approach

We used **rolling point-in-time ratings** that only include data from BEFORE each game:

```
For game on Date D:
  - Use ratings calculated from games BEFORE Date D
  - Never use end-of-season ratings (contains future data)
  - This simulates real betting conditions
```

### Test Scenarios

1. **Rolling Validation**: All games where ratings exist for both teams
2. **Late Season (10+ games)**: Only teams with established records
3. **Edge Threshold Sweep**: Finding optimal betting thresholds

---

## Results

### SPREAD Performance (Late Season)

| Edge Threshold | Bets | Win Rate | Est. ROI |
|----------------|------|----------|----------|
| 1+ pts | 89 | 70.8% | +35.1% |
| 2+ pts | 83 | 68.7% | +31.1% |
| 3+ pts | 70 | 62.9% | +20.0% |
| 4+ pts | 62 | 58.1% | +10.8% |
| 5+ pts | 52 | 53.8% | +2.8% |
| 6+ pts | 48 | 52.1% | -0.6% |

**Optimal Edge:** 2-3 points (balances volume and win rate)

### TOTAL Performance (Late Season)

| Edge Threshold | Bets | Win Rate | Est. ROI |
|----------------|------|----------|----------|
| 2+ pts | 86 | 55.8% | +6.5% |
| 3+ pts | 83 | 54.2% | +3.5% |
| 4+ pts | 79 | 51.9% | -1.0% |
| 5+ pts | 75 | 52.0% | -0.8% |

**Finding:** Totals show marginal edge at low thresholds, loses value at higher edges

---

## Data Leakage Analysis

### What Caused Inflated Previous Claims?

1. **End-of-Season Ratings**: Using final Barttorvik ratings to predict all games in the same season means ratings include information from games that happened AFTER the predicted game.

2. **Example of Leakage**:
   ```
   Game: Duke vs UNC on Nov 15, 2024
   Using: Barttorvik 2024 end-of-season ratings (from April 2025)
   Problem: Those ratings include Duke's and UNC's games from Dec-April
   ```

3. **Impact**: Can inflate win rates by 5-10+ percentage points

### Proper Temporal Separation

```
CORRECT: Use Season N-1 ratings to predict Season N games
CORRECT: Use rolling ratings updated only with PAST games
WRONG:   Use Season N end-of-season ratings for Season N games
```

---

## Honest Performance Claims

Based on validated no-leakage backtests:

### Spread Betting
- **Direction Accuracy**: 65-70% (late season)
- **Realistic ROI**: +10-25% at 2-3 point edge threshold
- **Sample Required**: 50+ bets minimum for significance

### Total Betting
- **Direction Accuracy**: 53-56%
- **Realistic ROI**: +3-6% at best
- **Recommendation**: Lower confidence than spreads

### When Model Works Best
- Late season (teams have 10+ games)
- Lower edge thresholds (2-3 points)
- Spread bets over totals

### When Model Struggles
- Early season (unreliable ratings)
- High edge predictions (regression to mean)
- Total predictions (higher variance)

---

## Recommendations

### For Documentation
1. Update README and model docs with validated claims
2. Remove or qualify the "62.2% / 18.5% ROI" claims
3. Add confidence intervals and sample size context

### For Model Usage
1. Focus on late-season betting (January-March)
2. Use 2-3 point edge threshold for spreads
3. Be cautious with totals (marginal edge)
4. Track actual results vs predictions

### For Future Validation
1. Collect more historical data with real market lines
2. Track closing line value (CLV) as quality metric
3. Run out-of-sample tests each season

---

## Appendix: Backtest Scripts

| Script | Purpose |
|--------|---------|
| `testing/scripts/lite_backtest_no_leakage.py` | Cross-season validation |
| `testing/scripts/comprehensive_validation.py` | Rolling window analysis |
| `testing/scripts/backtest_fg_spread.py` | Original backtest (has leakage) |

---

## Conclusion

The NCAAM model shows **real predictive value** for spread betting, particularly in late season. However, previous ROI claims were likely inflated by data leakage from using end-of-season ratings.

**Realistic expectations:**
- 55-65% win rate (not 62%+)
- +5-20% ROI (not 18%+)
- Works best late season with established team records

The model is still valuable but claims should be updated to reflect honest, validated performance.
