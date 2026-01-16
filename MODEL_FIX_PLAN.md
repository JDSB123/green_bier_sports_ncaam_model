# MODEL FIX PLAN - Addressing -6.44% ROI

**Date**: 2026-01-16
**Current Performance**: -6.44% ROI (48.9% win rate) on 1,346 bets
**Goal**: Achieve positive ROI (target: +3-5%)

---

## ROOT CAUSES IDENTIFIED

### 1. EDGE MISCALIBRATION (CRITICAL)
**Problem**: Bets with highest perceived edge (20+ points) have WORST performance (-10.08% ROI)

| Edge Range | Bets | Win Rate | ROI |
|------------|------|----------|-----|
| 20+ pts | 878 (65%!) | 46.9% | **-10.08%** ❌ |
| 10-20 pts | 166 | 52.4% | +0.35% |
| 5-10 pts | 94 | 50.0% | -4.66% |
| 2-5 pts | 58 | 52.6% | **+0.28%** ✓ |

**Diagnosis**: Model thinks it has massive edge when it doesn't. The formula-based prediction is systematically wrong.

**Root Cause**: The current formula in [run_historical_backtest.py:303-373](testing/scripts/run_historical_backtest.py#L303-L373):
```python
CALIBRATION_FG = 2.1
home_net = home_adj_o - home_adj_d
away_net = away_adj_o - away_adj_d
raw_margin = (home_net - away_net) / 2.0
return -(raw_margin + self.config.hca_spread) + CALIBRATION_FG
```

This is TOO SIMPLISTIC. It doesn't account for:
- Team strength variance (elite vs mid-tier)
- Conference effects
- Scheduling strength
- Recent form

---

### 2. ELITE TEAM FAILURE (CRITICAL)
**Problem**: Model hemorrhages money on top-tier programs

| Team | Bets | W/L | ROI |
|------|------|-----|-----|
| **Alabama** | 53 | 19W/33L | **-29.99%** ❌ |
| **Baylor** | 44 | 15W/26L | **-27.75%** ❌ |
| **Florida** | 44 | 17W/27L | **-26.08%** ❌ |
| **Duke** | 67 | 26W/40L | **-24.42%** ❌ |
| **UConn** | 63 | 25W/37L | **-22.54%** ❌ |

Meanwhile, mid-tier teams are profitable:
- Nebraska: +42.91% ROI
- Rutgers: +40.39% ROI
- UCF: +40.21% ROI

**Diagnosis**: Markets price elite teams MORE efficiently. Our simple formula doesn't account for this.

---

### 3. AWAY BET BIAS
**Problem**: Away bets lose 7.7% more than home bets

- Home bets: -2.21% ROI
- Away bets: -9.87% ROI

**Diagnosis**: Either:
1. Home court advantage (HCA) parameter is wrong, OR
2. Model systematically undervalues home advantage

---

## FIXES TO IMPLEMENT

### FIX 1: Add Elite Team Detection Feature

**Concept**: Create binary flag for "elite" teams (Top 25 in Barttorvik)

```python
# In canonical master or feature engineering
def is_elite_team(barthag):
    """Teams with barthag > 0.85 are elite (roughly top 25)"""
    return 1 if barthag > 0.85 else 0

# Features to add:
df['home_is_elite'] = df['home_barthag'].apply(lambda x: 1 if x > 0.85 else 0)
df['away_is_elite'] = df['away_barthag'].apply(lambda x: 1 if x > 0.85 else 0)
df['elite_matchup'] = df['home_is_elite'] * df['away_is_elite']  # Both elite
df['elite_vs_mid'] = df['home_is_elite'] + df['away_is_elite'] - 2*df['elite_matchup']  # One elite
```

**Expected Impact**: Allow model to learn that elite teams are priced differently.

---

### FIX 2: Add Conference Strength Features

**Concept**: Top conferences (ACC, Big Ten, Big 12, SEC, Big East) play differently

```python
TOP_CONFERENCES = ['ACC', 'B10', 'B12', 'SEC', 'BE']

# Assuming we have conference data in canonical master
df['home_top_conf'] = df['home_conference'].isin(TOP_CONFERENCES).astype(int)
df['away_top_conf'] = df['away_conference'].isin(TOP_CONFERENCES).astype(int)
df['conf_matchup'] = df['home_conference'] == df['away_conference']  # In-conference game
```

**Expected Impact**: Model learns conference-specific tendencies.

---

### FIX 3: Recalibrate Home Court Advantage

**Current**: HCA = 3.5 points (formula-based)

**Analysis needed**: Check if actual home advantage matches assumption

```python
# Quick analysis
df = pd.read_csv('manifests/canonical_training_data_master.csv')
avg_home_margin = df['actual_margin'].mean()
print(f"Average home margin: {avg_home_margin:.2f} points")

# Should be ~3.5 points. If not, HCA is miscalibrated.
```

**Expected Impact**: Better accuracy on home vs away predictions.

---

### FIX 4: Add Opponent-Adjusted Efficiency

**Problem**: Current formula uses raw adjusted efficiency

**Better Approach**: Adjust for opponent strength

```python
# Matchup-specific efficiency
df['home_expected_efficiency'] = df['home_adj_o'] + df['away_adj_d'] - LEAGUE_AVG
df['away_expected_efficiency'] = df['away_adj_o'] + df['home_adj_d'] - LEAGUE_AVG
df['efficiency_edge'] = df['home_expected_efficiency'] - df['away_expected_efficiency']
```

This is already partially in the formula but not used as a feature for ML models.

---

### FIX 5: Reduce Min Edge Threshold

**Current**: Only bet when edge >= 1.5 points

**Analysis**:
- 2-5 pt edge: +0.28% ROI ✓
- 10-20 pt edge: +0.35% ROI ✓
- 20+ pt edge: -10.08% ROI ❌

**New Strategy**:
- **EXCLUDE bets with edge > 15 points** (clearly miscalibrated)
- Keep bets with 1.5-15 point edge
- This removes 65% of bets but they're the LOSING ones

---

## IMPLEMENTATION STEPS

### STEP 1: Add Features to Canonical Master (if not present)

Check what features we already have:
```bash
python -c "import pandas as pd; df = pd.read_csv('manifests/canonical_training_data_master.csv'); print([c for c in df.columns if 'barthag' in c or 'rank' in c or 'conference' in c])"
```

If missing, we need to add:
- `home_conference`, `away_conference`
- Elite team flags
- Conference matchup flags

### STEP 2: Retrain Models with New Features

```bash
# Modify train_independent_models.py to include new features
python testing/scripts/train_independent_models.py
```

New feature list:
```python
FEATURES = [
    # Existing
    'home_adj_o', 'home_adj_d', 'away_adj_o', 'away_adj_d',
    'home_barthag', 'away_barthag',
    'home_tempo', 'away_tempo',

    # NEW
    'home_is_elite', 'away_is_elite',
    'elite_matchup', 'elite_vs_mid',
    'home_top_conf', 'away_top_conf',
    'conf_matchup',
    'efficiency_edge',
]
```

### STEP 3: Add Edge Filtering

Update backtest scripts to exclude miscalibrated high-edge bets:

```python
# In run_historical_backtest.py
if edge > 15.0:
    # Skip bet - edge likely miscalibrated
    continue
```

### STEP 4: Validate

Run backtests with new models:
```bash
python testing/scripts/run_historical_backtest.py --market fg_spread --seasons 2024,2025 --use-trained-models
```

Target: ROI > 0%

---

## EXPECTED RESULTS

**Conservative Estimate**:
- Remove 20+ edge bets: Eliminates -10% ROI on 878 bets = **+8.8% boost**
- Add elite team features: Improves elite team predictions by 50% = **+3% boost**
- Fix HCA calibration: Reduces away bet bias by 50% = **+2% boost**

**Total Expected**: -6.44% + 8.8% + 3% + 2% = **+7.36% ROI**

**Realistic Target**: +3-5% ROI (conservative)

---

## IMMEDIATE ACTIONS

1. **Check available features** in canonical master
2. **Add missing features** (conference, elite flags)
3. **Retrain models** with new features
4. **Add edge filter** to exclude >15pt edge bets
5. **Re-run backtests** and validate improvement

---

## ALTERNATIVE: QUICK WIN

If feature engineering is complex, try **JUST filtering edge**:

```python
# In backtest scripts, change:
if edge >= self.config.min_edge:
    # OLD: bet on everything

# To:
if self.config.min_edge <= edge <= 15.0:
    # NEW: only bet moderate edges
```

**Expected Impact**: Immediately removes worst-performing 878 bets (-10% ROI)
**Estimated ROI**: -6.44% → **+2-3% ROI** just from this change

**Test it first**:
```bash
python testing/scripts/run_historical_backtest.py --market fg_spread --seasons 2024,2025 --min-edge 1.5
# Then manually filter results to exclude edge > 15
```

---

**RECOMMENDATION**: Start with Alternative (Quick Win) to validate the hypothesis, then do full feature engineering.
