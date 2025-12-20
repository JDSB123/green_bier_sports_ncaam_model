# NCAAF v5.0 Backtesting System

## Overview

The NCAAF v5.0 backtesting system allows you to simulate betting strategies across historical game data to evaluate performance before risking real money. The system supports multiple bet types and game periods, providing comprehensive analytics on strategy performance.

## Supported Bet Types

### 1. Spread (Point Spread)
- Bet on whether a team will cover the point spread
- Example: Alabama -7.5 vs Georgia
- **Sides**: `home` or `away`

### 2. Moneyline
- Bet on which team will win outright
- Example: Alabama -250 vs Georgia +200
- **Sides**: `home` or `away`

### 3. Total (Over/Under)
- Bet on whether the combined score will be over or under a line
- Example: Total 52.5 points
- **Sides**: `over` or `under`

## Supported Game Periods

### 1. First Quarter (1Q)
- Bets settled based on 1st quarter results only
- Fast action, high variance
- Useful for testing early-game predictions

### 2. First Half (1H)
- Bets settled based on 1st half results
- More data than 1Q, less than full game
- Good for halftime adjustment strategies

### 3. Full Game
- Traditional full-game bets
- Settled after final score
- Most common betting period

## How It Works

### 1. Data Collection
- Historical game data with actual scores by period (1Q, 1H, Full)
- ML model predictions for each game
- Historical odds lines and prices

### 2. Bet Simulation
For each game in the backtest period:
1. **Load Prediction**: Get ML model's predicted margin, total, win probability
2. **Calculate Edge**: Compare prediction vs market odds line
3. **Determine Bet**: If edge exists and confidence > threshold, place bet
4. **Calculate Wager**: Use Kelly Criterion with constraints
5. **Determine Outcome**: Compare actual result vs odds line
6. **Calculate Profit/Loss**: Based on American odds and outcome

### 3. Performance Metrics
- **ROI (Return on Investment)**: Net profit / Total wagered
- **Win Rate**: Winning bets / Total bets
- **Sharpe Ratio**: Risk-adjusted return
- **Max Drawdown**: Largest peak-to-trough decline
- **Average Edge**: Mean edge per bet

## API Endpoints

### Create and Run Backtest

```http
POST /api/v1/backtests
Content-Type: application/json

{
  "name": "2024 Season Full Analysis",
  "description": "Test all bet types and periods for 2024 season",
  "start_date": "2024-09-01",
  "end_date": "2024-12-31",
  "bet_types": ["spread", "moneyline", "total"],
  "game_periods": ["1Q", "1H", "full"],
  "min_confidence": 0.60,
  "max_risk": 200.00,
  "unit_size": 100.00
}
```

**Response:**
```json
{
  "id": 1,
  "name": "2024 Season Full Analysis",
  "status": "completed",
  "summary": {
    "total_bets": 450,
    "total_won": 247,
    "total_lost": 195,
    "total_push": 8,
    "total_wagered": 45000.00,
    "total_returned": 49250.00,
    "net_profit": 4250.00,
    "roi": 0.0944,
    "win_rate": 0.5489
  }
}
```

### Get Backtest Summary

```http
GET /api/v1/backtests/{backtest_id}
```

Returns detailed summary with breakdowns by bet type and period.

### Get Detailed Results

```http
GET /api/v1/backtests/{backtest_id}/results?limit=100&offset=0
```

Returns individual bet results with filters.

### List All Backtests

```http
GET /api/v1/backtests?limit=50&offset=0
```

### Delete Backtest

```http
DELETE /api/v1/backtests/{backtest_id}
```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | - | Backtest name |
| `description` | string | null | Optional description |
| `start_date` | date | - | Start date (YYYY-MM-DD) |
| `end_date` | date | - | End date (YYYY-MM-DD) |
| `bet_types` | array | - | Bet types to test: `["spread", "moneyline", "total"]` |
| `game_periods` | array | - | Periods to test: `["1Q", "1H", "full"]` |
| `min_confidence` | float | 0.0 | Minimum model confidence (0-1) to place bet |
| `max_risk` | decimal | 100.00 | Maximum $ amount per bet |
| `unit_size` | decimal | 100.00 | Standard bet unit size in $ |

## Betting Strategy

### Edge Calculation

**Spread:**
```
edge = |predicted_margin - spread_line|
```

**Total:**
```
edge = |predicted_total - total_line|
```

**Moneyline:**
```
edge = predicted_win_prob - implied_probability_from_odds
```

### Wager Sizing

Uses **Fractional Kelly Criterion** (25% Kelly for safety):

```python
kelly_fraction = (edge * confidence) / (1 - confidence)
fractional_kelly = kelly_fraction * 0.25  # 25% of full Kelly
wager = unit_size * (fractional_kelly / 0.01)
wager = min(wager, unit_size, max_risk)
```

### Outcome Determination

**Spread:**
- Home bet wins if: `actual_margin > spread_line`
- Away bet wins if: `actual_margin < -spread_line`
- Push if: `actual_margin == spread_line`

**Total:**
- Over wins if: `actual_total > total_line`
- Under wins if: `actual_total < total_line`
- Push if: `actual_total == total_line`

**Moneyline:**
- Home bet wins if: `home_score > away_score`
- Away bet wins if: `away_score > home_score`
- No pushes on moneyline

### Payout Calculation

**American Odds:**

Positive odds (underdog):
```
payout = wager + (wager * odds / 100)
profit = wager * odds / 100
```

Negative odds (favorite):
```
payout = wager + (wager / (|odds| / 100))
profit = wager / (|odds| / 100)
```

**Example:**
- Bet $100 on -110 odds:
  - If win: Payout = $190.91, Profit = $90.91
  - If loss: Payout = $0, Profit = -$100
  - If push: Payout = $100, Profit = $0

## Example Usage

### Scenario 1: Conservative Spread Strategy

Test only high-confidence spread bets:

```json
{
  "name": "Conservative Spread Only",
  "start_date": "2024-09-01",
  "end_date": "2024-12-31",
  "bet_types": ["spread"],
  "game_periods": ["full"],
  "min_confidence": 0.75,
  "max_risk": 100.00,
  "unit_size": 100.00
}
```

### Scenario 2: 1st Quarter Total Betting

Test 1Q totals only:

```json
{
  "name": "1Q Total Betting",
  "start_date": "2024-09-01",
  "end_date": "2024-12-31",
  "bet_types": ["total"],
  "game_periods": ["1Q"],
  "min_confidence": 0.60,
  "max_risk": 50.00,
  "unit_size": 50.00
}
```

### Scenario 3: Multi-Period Comparison

Compare same bet type across all periods:

```json
{
  "name": "Spread Across All Periods",
  "start_date": "2024-09-01",
  "end_date": "2024-12-31",
  "bet_types": ["spread"],
  "game_periods": ["1Q", "1H", "full"],
  "min_confidence": 0.65,
  "max_risk": 100.00,
  "unit_size": 100.00
}
```

## Analyzing Results

### Summary Metrics

Check overall performance:
- **ROI > 0.05** (5%+) is profitable
- **Win Rate > 0.53** needed to profit at -110 odds
- **Sharpe Ratio > 1.0** indicates good risk-adjusted returns

### Breakdown Analysis

Review period breakdown:
- Which game period performs best?
- 1Q often has higher variance
- Full game usually has more data reliability

Review bet type breakdown:
- Which bet type has best ROI?
- Where is the model's edge strongest?
- Average edge per bet type

### Individual Results

Filter detailed results:
```http
GET /api/v1/backtests/{id}/results?bet_type=spread&outcome=win&limit=50
```

Export to CSV for analysis:
```http
GET /api/v1/backtests/{id}/export
```

## Best Practices

### 1. Start Small
- Test with small date ranges first
- Verify data quality before large backtests
- Use `min_confidence` to filter bets

### 2. Compare Periods
- Run same strategy across 1Q, 1H, full game
- Identify which periods model performs best
- Consider variance vs sample size tradeoffs

### 3. Validate Edge
- Ensure `avg_edge` is meaningful (>1 point for spreads/totals)
- Higher edge doesn't always mean higher profit
- Balance edge size with frequency

### 4. Check for Overfitting
- Test on different time periods
- Verify consistency across seasons
- Use walk-forward analysis

### 5. Risk Management
- Set appropriate `max_risk`
- Don't bet more than bankroll can handle
- Consider max drawdown in sizing

## Limitations

### Current Limitations

1. **Historical Data Required**
   - Needs complete game data with period scores
   - ML predictions must exist for games
   - Odds data must be available

2. **Simplified Market Assumptions**
   - Uses consensus odds (may not reflect actual available lines)
   - Assumes all bets can be placed at listed odds
   - No line shopping simulation

3. **No Juice Optimization**
   - Standard -110 assumed for most bets
   - Actual juice may vary by book
   - No reduced juice scenarios

4. **Static Bankroll**
   - Doesn't simulate bankroll growth
   - Kelly sizing based on fixed unit
   - No compounding effects

### Future Enhancements

- [ ] Live odds integration
- [ ] Multiple sportsbook comparison
- [ ] Dynamic bankroll management
- [ ] Correlation between bets
- [ ] Parlay simulation
- [ ] Steam move detection
- [ ] CLV (Closing Line Value) analysis

## Troubleshooting

### Empty Results

**Issue**: Backtest returns 0 bets

**Solutions**:
- Lower `min_confidence` threshold
- Check date range has games
- Verify predictions exist for period
- Ensure odds data is available

### Low Win Rate

**Issue**: Win rate < 50%

**Solutions**:
- Increase `min_confidence` to filter weak predictions
- Check if model is calibrated correctly
- Review edge calculation logic
- Analyze breakdown by bet type/period

### Excessive Losses

**Issue**: Large negative ROI

**Solutions**:
- Review individual losing bets
- Check for systematic biases
- Verify outcome calculation logic
- Consider if market is efficient in this segment

## Support

For issues or questions about backtesting:
1. Check this documentation
2. Review API documentation at `/docs`
3. Examine individual bet results for patterns
4. Contact development team

## Database Schema

The backtesting system uses two main tables:

### `backtests`
Stores backtest metadata and summary metrics

### `backtest_results`
Stores individual bet results with full details

See migration file: `migrations/000006_create_backtest_tables.up.sql`
