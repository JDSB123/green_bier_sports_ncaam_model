# Model Improvement Analysis

## Current Issues & Proposed Fixes

Based on data analysis (1,046 games with 1H scores):

---

## 1. FULL GAME TOTAL IMPROVEMENTS

### Current Problems:
- MAE: 13.1 pts (market is ~10.5)
- Regression to mean: under-predicts high games, over-predicts low
- Simple efficiency formula misses key factors

### Proposed Fixes:

#### A. Add Defensive Efficiency Factors
```python
# Current (too simple):
matchup_eff = team_off + opp_def - league_avg

# Improved (include defensive quality):
def calculate_matchup_efficiency(team_off, opp_def, team_def, opp_off):
    # Factor in both sides of the ball
    off_matchup = team_off - opp_def  # How good is offense vs defense
    def_matchup = opp_off - team_def  # How good is opponent vs our defense

    # Weight offensive matchups more (scoring drives totals)
    return off_matchup * 0.6 + def_matchup * 0.4
```

#### B. Add Turnover Rate Adjustment
```python
# High turnover games = lower scoring (fewer possessions complete)
avg_tor = (home.tor + away.tord + away.tor + home.tord) / 4
if avg_tor > 20.0:  # High turnover environment
    adjustment -= (avg_tor - 20.0) * 0.3
elif avg_tor < 16.0:  # Clean game
    adjustment += (16.0 - avg_tor) * 0.3
```

#### C. Add Free Throw Rate Factor
```python
# High FT rate = more stoppages but more points per possession
avg_ftr = (home.ftr + away.ftr) / 2
if avg_ftr > 36.0:  # Foul-heavy game
    adjustment += (avg_ftr - 36.0) * 0.2
```

#### D. Non-Linear Calibration
```python
# Current: flat +7.0 calibration
# Problem: Over-adjusts low games, under-adjusts high

# Improved: Variable calibration based on base prediction
def dynamic_calibration(base_total):
    if base_total < 130:
        return 4.0  # Less adjustment for low games
    elif base_total > 150:
        return 10.0  # More adjustment for high games
    else:
        return 7.0  # Standard for middle
```

---

## 2. FIRST HALF TOTAL IMPROVEMENTS

### Current Model Stats:
- MAE: 8.88 pts
- 1H/FG Ratio: 0.468 (model uses 0.48)
- Avg 1H Total: 65.7

### Data Insights:
| FG Total Range | 1H/FG Ratio | Implication |
|----------------|-------------|-------------|
| < 120 | 0.462 | Low games: 1H is slightly higher % |
| 120-160 | 0.469-0.470 | Standard ratio |
| > 180 | 0.438 | High games: 1H is lower % (regression) |

### Proposed Fixes:

#### A. Variable 1H Ratio
```python
def calculate_h1_ratio(predicted_fg_total):
    """1H/FG ratio varies by game pace."""
    if predicted_fg_total < 130:
        return 0.465  # Low games
    elif predicted_fg_total > 160:
        return 0.450  # High games (regression)
    else:
        return 0.468  # Standard
```

#### B. First Half Scoring Momentum
```python
# Teams with high offensive efficiency tend to start slower
# Elite offenses (adj_o > 115) often have cold 1H starts
avg_off = (home.adj_o + away.adj_o) / 2
if avg_off > 115:
    h1_adjustment -= 1.5  # Elite offenses start slow
```

---

## 3. FIRST HALF SPREAD IMPROVEMENTS

### Data Insights:
- 1H HCA = +5.03 (56.3% of FG HCA of +8.95)
- Current model uses 3.6 (62% of 5.8 FG HCA)
- **Need to INCREASE 1H HCA from 3.6 to ~5.0**

### Proposed Fix:
```python
# Current
HCA_1H = 3.6  # 62% of FG

# Improved (based on data)
HCA_1H = 5.0  # 56% of actual FG HCA (8.95)
```

### Additional 1H Spread Factors:
```python
# 1H winner = FG winner 81% of time
# Strong correlation (0.78) means 1H spread is predictive

# Add momentum factor:
# If one team is clearly better (Barthag diff > 0.2), they dominate 1H
barthag_diff = home.barthag - away.barthag
if abs(barthag_diff) > 0.20:
    h1_spread_adj = barthag_diff * 2.0  # Favorites dominate 1H more
```

---

## 4. VALIDATION-DRIVEN IMPROVEMENTS

### A. Confidence Adjustment Based on Game Type
```python
# Mismatches have more variance - lower confidence
barthag_diff = abs(home.barthag - away.barthag)
if barthag_diff > 0.25:
    confidence *= 0.90  # 10% confidence penalty for mismatches
```

### B. Edge Threshold Optimization
Based on validation:

| Market | Current | Recommended |
|--------|---------|-------------|
| FG Spread | 2.0 pts | 2.0-3.0 pts ✓ |
| FG Total | 3.0 pts | **5.0+ pts** (marginally profitable) |
| 1H Spread | 3.5 pts | **2.5-3.0 pts** (less efficient market) |
| 1H Total | 2.0 pts | **3.0+ pts** |

### C. Focus on Less Efficient Markets
1H markets are less efficient than FG markets:
- Fewer sharp bettors focus on 1H
- More recreational action
- **Prioritize 1H bets over FG totals**

---

## 5. IMPLEMENTATION PRIORITY

### High Impact (Do First):
1. ✅ Increase 1H HCA from 3.6 to 5.0
2. ✅ Add turnover rate adjustment to totals
3. ✅ Variable calibration based on predicted total

### Medium Impact:
4. Add FTR factor to totals
5. Adjust 1H ratio for extreme games
6. Add Barthag mismatch factor

### Lower Priority:
7. Non-linear efficiency weighting
8. Momentum factors
9. Conference-specific adjustments

---

## 6. EXPECTED IMPACT

| Change | Expected Improvement |
|--------|---------------------|
| 1H HCA fix | +2-3% spread accuracy |
| Turnover adjustment | -0.5 pts MAE on totals |
| Variable calibration | -1.0 pts MAE on totals |
| Edge threshold tuning | +3-5% ROI |

**Realistic Goals:**
- FG Total: MAE from 13.1 → 11.5 pts
- 1H Total: MAE from 8.88 → 8.0 pts
- FG Spread: Maintain 65%+ direction accuracy
- 1H Spread: Improve to 60%+ with HCA fix
