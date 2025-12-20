# NCAAF v5.0 - QUICK START (Single Source of Truth)

> **This is THE definitive guide. Ignore all other documentation if it conflicts with this file.**

---

## TL;DR - Get Predictions in 2 Commands

```bash
# 1. Start services (if not running)
docker compose up -d

# 2. Get predictions for a specific week
run.bat pick 15 2024
```

That's it!

---

## What This System Does

1. **Predicts NCAA Football game outcomes** (spread, total points)
2. **Recommends bets** when the model has edge over the market
3. **Sizes bets** using Kelly Criterion

---

## Single Entry Point: `run.bat`

| Command | What It Does |
|---------|--------------|
| `run.bat pick [week] [season]` | **GET PREDICTIONS** for a specific week |
| `run.bat train` | Retrain models (weekly) |
| `run.bat status` | Check system status |
| `run.bat start` | Start Docker services |
| `run.bat stop` | Stop Docker services |

### Examples

```bash
# Get predictions for Week 15, 2024 season
run.bat pick 15 2024

# Get predictions for current week (auto-detect)
run.bat pick

# Retrain models with latest data
run.bat train

# Check if everything is running
run.bat status
```

---

## Output Format

When you run `run.bat pick 15 2024`, you'll see:

```
============================================================
NCAAF PREDICTIONS - Week 15, 2024
============================================================

GAME: Ohio State vs Michigan
  Predicted Spread: -7.5 (Home team by 7.5)
  Predicted Total: 45.2
  Market Spread: -6.5
  Market Total: 44.0
  
  EDGE: 1.0 points on spread (AWAY)
  Confidence: 72%
  
  RECOMMENDATION: BET MICHIGAN +6.5
  Suggested Units: 1.5

------------------------------------------------------------

GAME: Georgia vs Alabama
  Predicted Spread: +3.2 (Away team by 3.2)
  ...

============================================================
SUMMARY: 3 recommended bets out of 12 games
============================================================
```

---

## Model Performance

| Metric | Value |
|--------|-------|
| ATS Accuracy | 88.4% (top confidence picks: 100%) |
| Spread MAE | 8.04 points |
| Total MAE | 10.33 points |
| ROE Improvement | +39% over baseline |

---

## File Structure (What Matters)

```
ncaaf_v5.0_BETA/
├── run.bat                    # <-- USE THIS
├── QUICK_START.md             # <-- READ THIS
├── docker-compose.yml         # Service config
├── .env                       # API keys
│
└── ml_service/
    ├── main.py               # CLI entry point
    └── models/
        └── enhanced/         # <-- TRAINED MODELS
            ├── spread_model.pkl
            ├── total_model.pkl
            └── feature_names.pkl
```

---

## Troubleshooting

### "Models not loaded"
```bash
run.bat train
```

### "Database connection failed"
```bash
run.bat stop
run.bat start
```

### "No games found"
- Check season/week are correct
- Ensure data is imported: `run.bat import`

---

## First Time Setup

```bash
# 1. Copy environment file
copy .env.example .env

# 2. Edit .env and add your SportsDataIO API key
notepad .env

# 3. Start everything
run.bat start

# 4. Import data and train models
run.bat pipeline

# 5. Get predictions
run.bat pick 15 2024
```

---

**Last Updated:** December 2024  
**Version:** 5.0 BETA

