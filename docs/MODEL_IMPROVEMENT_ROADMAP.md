# NCAAM Model Improvement Roadmap

## Current State (v33.1)

| Metric | Value | Market Benchmark |
|--------|-------|------------------|
| Spread MAE | 10.5 pts | ~7-8 pts |
| Direction Accuracy | 70% | - |
| Data Source | Public Barttorvik | Already priced in |
| Model Type | Static Formula | No learning |

**Core Problem**: We're predicting game outcomes with public data. Markets already do this better. The value isn't in predicting outcomes - it's in finding where we disagree with markets AND being right.

---

## Phase 1: Historical Betting Lines (REQUIRED)

Without historical lines, we can't measure what matters: **beating the market**.

### Data Sources

1. **The Odds API** - Historical from June 2020
   - `https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/odds`
   - Requires API key (has free tier)
   - Covers 2020-2024 seasons

2. **GitHub Repos**
   - `pmelgren/NCAAodds` - Historical NCAAB odds
   - `cresswellkg/Sports_Utilities` - Betting data utilities

3. **Action Network / Covers** - Scrape historical consensus

### Implementation

```python
# Store in PostgreSQL
CREATE TABLE historical_odds (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    home_team VARCHAR,
    away_team VARCHAR,
    -- Opening lines (for CLV calculation)
    opening_spread DECIMAL(4,1),
    opening_total DECIMAL(5,1),
    opening_spread_time TIMESTAMP,
    -- Closing lines (market consensus)
    closing_spread DECIMAL(4,1),
    closing_total DECIMAL(5,1),
    -- Sharp book reference
    pinnacle_spread DECIMAL(4,1),
    pinnacle_total DECIMAL(5,1)
);
```

### Key Metrics Enabled

- **CLV (Closing Line Value)**: Did line move toward or away from our prediction?
- **Edge Frequency**: How often do we have >2pt edge vs market?
- **Edge Accuracy**: When we have edge, how often are we right?

---

## Phase 2: Market-Relative Validation

### Current Approach (Wrong)
```
Model predicts: Duke -7.5
Actual result: Duke -12
Error: 4.5 points  <-- We measure this
```

### Correct Approach
```
Model predicts: Duke -7.5
Market line: Duke -5.5
Model says: Bet Duke (2pt edge)
Actual result: Duke -12
Outcome: WIN  <-- We measure this
```

### Implementation

```python
@dataclass
class MarketValidationResult:
    game_id: str
    model_spread: float
    market_spread: float
    edge: float  # model - market
    bet_side: str  # "HOME", "AWAY", "NO_BET"
    actual_spread: float
    outcome: str  # "WIN", "LOSS", "PUSH"
    clv: float  # closing - opening movement
```

### Success Criteria

| Metric | Target | Why |
|--------|--------|-----|
| Edge Frequency | 15-20% | Not every game has value |
| Edge Win Rate | >53% | Beats -110 juice |
| CLV Correlation | >0.3 | Our edge predicts line movement |
| ROI (flat betting) | >3% | Sustainable profit |

---

## Phase 3: Residual ML Model

The Barttorvik formula captures ~80% of predictive power. Train ML to capture the remaining 20%.

### Architecture

```
[Barttorvik Formula] --> Base Prediction
                              |
                              v
[Feature Engineering] --> Additional Features
                              |
                              v
[XGBoost/LightGBM] --> Residual Adjustment
                              |
                              v
                      Final Prediction
```

### Additional Features for Residual Model

1. **Game Context**
   - Days since last game (each team)
   - Travel distance
   - Altitude differential
   - Rivalry flag
   - Conference tournament flag
   - March Madness round

2. **Temporal**
   - Month of season (Nov ratings unreliable)
   - Days into season
   - Games played this season

3. **Matchup-Specific**
   - Style clash (tempo differential)
   - 3PT reliance mismatch
   - Recent H2H performance

4. **Market Signals**
   - Line movement direction
   - Reverse line movement flag
   - Public betting %

### Training Approach

```python
# Walk-forward validation (NO DATA LEAKAGE)
for season in [2021, 2022, 2023, 2024]:
    train_data = all_data[all_data.season < season]
    test_data = all_data[all_data.season == season]

    model.fit(train_data.X, train_data.residual)
    predictions = model.predict(test_data.X)

    # Measure on held-out season
    evaluate(predictions, test_data.actual)
```

---

## Phase 4: Walk-Forward Production Pipeline

### Daily Pipeline

```
06:00 - Fetch today's games from ESPN API
06:05 - Fetch current Barttorvik ratings
06:10 - Fetch current betting lines (The Odds API)
06:15 - Generate base predictions (formula)
06:20 - Apply residual ML adjustment
06:25 - Compare to market lines, identify edges
06:30 - Filter by confidence threshold
06:35 - Output recommendations with Kelly sizing
```

### Database Schema

```sql
-- Predictions table (immutable audit log)
CREATE TABLE predictions (
    prediction_id UUID PRIMARY KEY,
    game_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    -- Base model
    base_spread DECIMAL(4,1),
    base_total DECIMAL(5,1),
    -- ML-adjusted
    adjusted_spread DECIMAL(4,1),
    adjusted_total DECIMAL(5,1),
    -- Market comparison
    market_spread DECIMAL(4,1),
    market_total DECIMAL(5,1),
    spread_edge DECIMAL(4,2),
    total_edge DECIMAL(4,2),
    -- Recommendation
    bet_type VARCHAR,  -- 'SPREAD_HOME', 'SPREAD_AWAY', 'OVER', 'UNDER', 'NO_BET'
    confidence DECIMAL(3,2),
    kelly_fraction DECIMAL(4,3)
);

-- Results table (filled after game)
CREATE TABLE results (
    game_id VARCHAR PRIMARY KEY,
    prediction_id UUID REFERENCES predictions,
    actual_home_score INT,
    actual_away_score INT,
    closing_spread DECIMAL(4,1),
    closing_total DECIMAL(5,1),
    clv DECIMAL(4,2),
    outcome VARCHAR  -- 'WIN', 'LOSS', 'PUSH'
);
```

---

## Expected Improvement Timeline

| Phase | Effort | Impact on MAE | Impact on ROI |
|-------|--------|---------------|---------------|
| Phase 1: Lines | 1 week | None | Enables measurement |
| Phase 2: Market Val | 1 week | None | Identifies actual edge |
| Phase 3: Residual ML | 2 weeks | -1.0 pts | +2-3% |
| Phase 4: Walk-Forward | 1 week | Prevents decay | Sustainable |

**Total: 5 weeks to production-ready system**

---

## Key Insight

The goal isn't to predict games better than Vegas. It's to:

1. **Find disagreements** between our model and market
2. **Validate historically** that those disagreements are profitable
3. **Size bets** based on confidence and edge magnitude
4. **Track CLV** to confirm our edges are real (not just lucky)

A 53% win rate on -110 lines = **+2.5% ROI**
A 55% win rate = **+5% ROI**

You don't need to be way better than the market. You need to be **slightly better, consistently**.
