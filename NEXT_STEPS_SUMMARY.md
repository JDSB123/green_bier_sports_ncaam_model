# NEXT STEPS SUMMARY

**Date**: 2026-01-16
**Current Status**: All cleanup complete, data quality verified, ready for next phase

---

## ✓ COMPLETED TODAY

1. **Data Cleanup**
   - Reduced canonical master: 109 → 99 columns
   - Removed all redundant team canonicalization columns
   - Clean schema: home_canonical/away_canonical (100% coverage)

2. **Scripts Updated**
   - Updated run_clv_backtest.py and run_historical_backtest.py
   - Removed 64+ lines of complex fallback logic
   - All scripts use canonical columns directly

3. **Deployment**
   - Deployed to Azure: canonical/canonical_training_data_master.csv
   - Git: 3 commits pushed to origin/main
   - Backtests verified working

4. **Documentation**
   - Created DATA_ACQUISITION_PLAN.md
   - Created verification scripts
   - All processes documented

---

## 🎯 WHAT'S NEXT

### Current Model Performance
Your backtests show **negative ROI**:
- FG Spread: -9.9% ROI (47.0% win rate)
- Need to improve models before going live

### Three Paths Forward

#### PATH A: Improve Models First (RECOMMENDED)
**Why**: Even with perfect data, losing models won't be profitable

**Steps**:
1. Analyze where models are losing money
   ```bash
   python testing/scripts/run_historical_backtest.py --market fg_spread --seasons 2024 2025
   python testing/scripts/run_historical_backtest.py --market fg_total --seasons 2024 2025
   python testing/scripts/run_historical_backtest.py --market h1_spread --seasons 2024 2025
   ```

2. Feature engineering
   - Add more Barttorvik stats
   - Include rest days, travel distance
   - Add situational factors (rivalry games, conference tournaments)

3. Model tuning
   - Try different algorithms (currently using LinearRegression)
   - Hyperparameter optimization
   - Ensemble methods

4. Betting strategy optimization
   - Adjust min_edge threshold
   - Selective betting (only certain matchups)
   - Kelly criterion for bet sizing

**Timeline**: 1-2 weeks
**Cost**: $0
**Risk**: Low

---

#### PATH B: Add Closing Lines (Data First)
**Why**: Get CLV metric to measure true model sharpness

**The Issue**:
- The Odds API doesn't provide historical closing lines
- Only provides current/upcoming games
- Historical closing lines require special access or data partners

**Options**:

1. **Prospective Capture** (Free)
   - Set up automated job to capture closing lines before games start
   - Start building closing line data for 2026+ season
   - Accept that 2023-2025 backtests won't have CLV
   - Timeline: 1 day to set up, ongoing capture

2. **Historical Data Purchase** ($$)
   - Contact specialized sports data vendors
   - Pinnacle, Bovada archives, or sports data partners
   - Cost: Likely $500-2000 for historical dataset
   - Timeline: 1-2 weeks procurement

3. **Skip CLV for Historical** (Free)
   - Focus on win rate and ROI for backtests
   - Add CLV tracking prospectively when live
   - Timeline: Immediate

**Recommended**: Option 1 (Prospective Capture)
**Timeline**: 1 day setup
**Cost**: Free (uses existing API key)
**Risk**: Low

---

#### PATH C: Go Live with Current Models (HIGH RISK)
**Why**: Start capturing real-world performance data

**Steps**:
1. Set up prospective closing line capture
2. Deploy models to production
3. Start with paper trading (track bets without actual money)
4. Collect real-world CLV data
5. Iterate on models based on live performance

**Timeline**: 1 week
**Cost**: $0 (paper trading)
**Risk**: HIGH if real money, LOW if paper trading

---

## 📊 CURRENT DATA QUALITY

**Good** (70%+):
- ✓ FG Spread: 77.5%
- ✓ FG Total: 77.3%
- ✓ Moneyline: 71.9%
- ✓ Ratings: 88.4%
- ✓ Actual Results: 100%

**Needs Work** (<70%):
- ❌ H1 Spread: 49.3% (2023 at 0%)
- ❌ H1 Total: 48.9% (2023 at 0%)
- ❌ Closing Lines: 0% (all seasons)

---

## 🔧 IMMEDIATE ACTIONS (Based on Path)

### If PATH A (Improve Models):
```bash
# Run comprehensive backtests
python testing/scripts/run_historical_backtest.py --market fg_spread --seasons 2023 2024 2025
python testing/scripts/run_historical_backtest.py --market fg_total --seasons 2023 2024 2025

# Analyze results
# Look for: which teams/conferences lose money, what margin ranges, home vs away

# Retrain with better features
python testing/scripts/train_independent_models.py
```

### If PATH B (Add Closing Lines):
```bash
# Create prospective closing line capture script
# (I can help build this once you confirm API access in your environment)

# Set up cron job or scheduled task to run before games
# Capture closing lines ~1 hour before commence_time

# Update canonical master schema to include closing columns
```

### If PATH C (Go Live):
```bash
# Set up production environment
# Deploy models
# Start paper trading
# Monitor performance
```

---

## 💡 MY RECOMMENDATION

**Start with PATH A + PATH B Option 1**:

1. **Week 1**: Improve models
   - Run detailed backtests
   - Analyze losing patterns
   - Engineer better features
   - Retrain models

2. **Week 2**: Set up prospective data capture
   - Build closing line capture script
   - Set up automated job
   - Verify data quality

3. **Week 3**: Validate improved models
   - Re-run backtests with better models
   - Check if ROI positive
   - Add CLV tracking prospectively

4. **Week 4**: Paper trading (if models profitable)
   - Deploy to production
   - Track real-world performance
   - Iterate based on live data

**Why This Order**:
- No point capturing closing lines if models are losing money
- Improving models is free and immediate
- Prospective capture builds dataset while you improve
- Paper trading validates before risking real money

---

## ❓ QUESTIONS FOR YOU

1. **What's your priority?**
   - A. Get models profitable first
   - B. Get perfect historical data first
   - C. Start live (paper trading) ASAP

2. **What's your risk tolerance?**
   - Conservative: Don't go live until models prove profitable historically
   - Moderate: Paper trade while improving models
   - Aggressive: Real money with current models

3. **What's your timeline?**
   - Need to be live in 1 week (PATH C)
   - Can take 1 month to perfect (PATH A + B)
   - No rush, want best system (PATH A + B + validation)

4. **API Access**:
   - Is The Odds API key available in your Azure/Docker environment?
   - Can you run the closing line capture from there?
   - Or do you need it to work locally on Windows?

---

## 📝 FILES READY

All scripts ready to run once you decide direction:
- [fetch_closing_lines_historical.py](fetch_closing_lines_historical.py) - Analyze API capabilities
- [verify_canonical_master_quality.py](verify_canonical_master_quality.py) - Data quality checks
- [testing/scripts/run_historical_backtest.py](testing/scripts/run_historical_backtest.py) - Model backtesting
- [testing/scripts/train_independent_models.py](testing/scripts/train_independent_models.py) - Model training
- [DATA_ACQUISITION_PLAN.md](DATA_ACQUISITION_PLAN.md) - Detailed data acquisition options

---

**What would you like to do next?**
