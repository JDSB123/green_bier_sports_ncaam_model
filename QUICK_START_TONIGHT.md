# 🚀 TONIGHT'S QUICK START GUIDE

## Status: ✅ READY TO GO

All 6 prediction markets backtested. **FG Spread + H1 Spread are PROFITABLE.**

---

## ⚡ DO THIS NOW

### 1. Set Odds API Key (one-time)
```powershell
# In PowerShell:
$env:ODDS_API_KEY = "your_odds_api_key_here"

# Or permanently add to System Environment Variables
```

Get key: https://theoddsapi.com (free account = 500 requests/month)

### 2. Generate Tonight's Picks (2-3 hours before first tip)
```bash
cd c:\Users\JDSB\dev\green_bier_sport_ventures\ncaam_gbsv_local\green_bier_sports_ncaam_model
python generate_tonight_picks.py --live
```

Output: `testing/results/predictions/tonight_picks_*.csv` and `.json`

### 3. Review Picks
- Check predictions vs market lines
- Verify edge % > 1.5%
- See confidence scores (HIGH/MEDIUM/LOW)
- **DO NOT STAKE REAL MONEY YET** (paper mode only)

### 4. Track Results
- Manually record outcomes after each game
- Expected win rate: 54%+ for FG spread, 54%+ for H1 spread
- Expected ROI: +3.8% to +1.5%

---

## 📊 WHAT TO EXPECT

### FG Spread Predictions
- 54.4% historical win rate
- +3.82% ROI (2024-2025 backtest)
- ~150-200 bets over full season

Example pick format:
```
Away Team @ Home Team
Predicted: -2.5 (home favored by 2.5)
Market Line: -1.0 (home favored by 1.0)
Edge: 1.5 pts (1.36% edge)
Bet: HOME SPREAD (cover -2.5)
Confidence: MEDIUM
```

### H1 Spread Predictions
- 54.2% historical win rate
- +1.54% ROI (2024-2025 backtest)
- ~100-150 bets over full season

Same format as FG but for first half.

---

## 🚨 IMPORTANT WARNINGS

### Paper Mode Only ⚠️
- No real money tonight
- Predictions are for validation only
- Go live next week only if:
  - Paper picks hit 54%+ win rate for 7 days
  - Actual odds match expected coverage
  - Team reviews picks before staking

### Data Gaps to Know
- ❌ Closing lines not captured yet (setup tomorrow)
- ❌ H1 2023 data missing (only affects historical context)
- ✅ FG/H1 2024-2025 strong coverage (75%+)

### Skip These Markets Tonight
- ❌ FG Total (-4.90% ROI; needs work)
- ❌ H1 Total (-5.68% ROI; needs work)
- ❌ FG Moneyline (-3.27% ROI; odds calibration off)
- ❌ H1 Moneyline (no data)

**Stick to FG Spread + H1 Spread only.**

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `generate_tonight_picks.py` | Generate predictions for tonight |
| `capture_closing_lines.py` | Capture lines 60-90 min pre-tip (setup tomorrow) |
| `testing/models/fg_spread.json` | FG Spread prediction model |
| `testing/models/h1_spread.json` | H1 Spread prediction model |
| `manifests/canonical_training_data_master.csv` | All historical data (3,339 games) |
| `PRODUCTION_READY_STATUS.md` | Full technical documentation |

---

## 🎯 Success Metrics (Tonight)

✅ Predictions generated without errors
✅ 5-15 picks output (per slate)
✅ All picks have edge > 1.5%
✅ Confidence scores reasonable
✅ Pick volume similar to historical (150-200 FG spread + 100-150 H1 spread per night expected)

---

## 🔧 Troubleshooting

### "KeyError: 'ODDS_API_KEY'"
```
→ Set ODDS_API_KEY in PowerShell: 
  $env:ODDS_API_KEY = "your_key"
```

### "No picks generated (all edges below 1.5%)"
```
→ Script working correctly; just no high-edge opportunities
→ Try: python generate_tonight_picks.py --market fg_spread
```

### "Can't find canonical_training_data_master.csv"
```
→ Verify file exists: 
  ls manifests/canonical_training_data_master.csv
→ If not, run: python deploy_to_azure.py
```

### Odds API rate limited
```
→ Free tier = 500 requests/month
→ Upgrade at theoddsapi.com
→ Or skip --live; use local canonical master instead
```

---

## 📞 Next Steps (After Tonight)

- **Tomorrow Morning**: Review paper picks vs actual outcomes
- **Tomorrow (Setup)**: Set up closing line capture with `python capture_closing_lines.py --daemon`
- **Next 7 Days**: Run paper picks nightly; track ROI
- **Next Week**: If paper ROI positive, deploy with real money ($50-100/night)

---

## ✨ TL;DR

```bash
# Set API key
$env:ODDS_API_KEY = "your_key"

# Generate picks (2-3 hours before tip-off)
python generate_tonight_picks.py --live

# Review output
cat testing/results/predictions/tonight_picks_*.csv

# Track results manually
# (Expected: 54% win rate, +1.5-6.2% ROI)

# Tomorrow: Set up closing line capture
python capture_closing_lines.py --run-once
```

---

**Status**: 🟢 Ready for paper trading tonight  
**Confidence**: High (backtested +3.82% ROI)  
**Risk**: Low (paper mode; no real money)  
**Expected Result**: 50-100 predictions tonight  

**GO LIVE DECISION**: End of week if paper ROI validates backtest.

---

Questions? See [PRODUCTION_READY_STATUS.md](PRODUCTION_READY_STATUS.md) for full details.
