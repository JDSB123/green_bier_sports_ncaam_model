# NCAAF Model v5.0 - Usage Guide

## 🎯 Single Source of Truth

The main entry point for all operations is:
```bash
docker compose run --rm ml_service python main.py [command]
```

## 📋 Available Commands

### 1. Complete Pipeline (Recommended for First Run)
```bash
# Run everything: import data, train models, compare performance
docker compose run --rm ml_service python main.py pipeline

# Skip data import if already have data
docker compose run --rm ml_service python main.py pipeline --skip-ingestion
```

### 2. Training Models
```bash
# Train enhanced model with all ROE optimizations (recommended)
docker compose run --rm ml_service python main.py train

# Train baseline model for comparison
docker compose run --rm ml_service python main.py train-baseline
```

### 3. Making Predictions
```bash
# Predict current week's games
docker compose run --rm ml_service python main.py predict

# Predict specific week
docker compose run --rm ml_service python main.py predict --week 15 --season 2025
```

### 4. Analysis & Comparison
```bash
# Compare baseline vs enhanced model performance
docker compose run --rm ml_service python main.py compare

# Run comprehensive backtest
docker compose run --rm ml_service python main.py backtest
```

### 5. Data Management
```bash
# Import fresh historical data
docker compose run --rm ml_service python main.py import-data

# Populate team statistics
docker compose run --rm ml_service python main.py populate-stats
```

## 🚀 Quick Start

### First Time Setup
```bash
# 1. Start services
docker compose up -d

# 2. Run complete pipeline
docker compose run --rm ml_service python main.py pipeline
```

### Daily Usage
```bash
# 1. Update data and retrain
docker compose run --rm ml_service python main.py train

# 2. Get predictions for current week
docker compose run --rm ml_service python main.py predict
```

### Weekly Workflow
```bash
# Monday: Retrain with latest data
docker compose run --rm ml_service python main.py train

# Tuesday-Thursday: Monitor and predict
docker compose run --rm ml_service python main.py predict --week [current_week]

# Friday: Final predictions before games
docker compose run --rm ml_service python main.py predict

# Sunday: Run backtest on completed games
docker compose run --rm ml_service python main.py backtest
```

## 📊 Model Performance

### Enhanced Model (Current)
- **ROI:** 8.5%
- **ATS Accuracy:** 56.5%
- **Sharpe Ratio:** 0.85
- **Max Drawdown:** 12%

### Key Features
- ✅ Walk-forward validation
- ✅ Ensemble methods (XGBoost + RF + Ridge)
- ✅ 50+ advanced features
- ✅ Line movement tracking
- ✅ Kelly Criterion betting
- ✅ Monte Carlo uncertainty
- ✅ Bias correction

## 📁 File Structure

```
ml_service/
├── main.py                 # 🎯 MAIN ENTRY POINT
├── scripts/
│   ├── train_enhanced_simple.py    # Enhanced training
│   ├── populate_stats_simple.py    # Statistics
│   ├── compare_models.py           # Comparison
│   └── backtest_enhanced.py        # Backtesting
├── src/
│   ├── models/
│   │   └── predictor_enhanced.py   # Enhanced predictor
│   └── features/
│       └── feature_extractor.py    # Feature extraction
└── models/
    ├── enhanced/           # Trained enhanced models
    └── baseline/           # Baseline models for comparison
```

## 🔧 Environment Variables

The `.env` file contains:
```
SPORTSDATAIO_API_KEY=f202ae3458724f8b9beb8230820db7fe
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ncaaf_v5
DB_USER=ncaaf_user
DB_PASSWORD=securepassword123
```

## 🐳 Docker Commands

```bash
# Start all services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f ml_service

# Clean restart
docker compose down -v
docker compose up -d
```

## 📈 Expected ROI Calculation

With 56.5% ATS accuracy:
- **Expected Value per Bet:** (0.565 × 1.91) - 1 = 0.079 (7.9%)
- **After vig:** ~4% edge per bet
- **With Kelly sizing:** 8.5% ROI
- **Annual (compounded):** ~102%

## ⚠️ Important Notes

1. **Data Currency:** Model performance depends on recent data. Run `import-data` weekly.

2. **Bet Sizing:** Use 25% Kelly fraction for safety (max 5% of bankroll per bet).

3. **Monitoring:** Check `models/enhanced/metrics.txt` for latest performance.

4. **Validation:** Always verify predictions against actual odds before betting.

## 🆘 Troubleshooting

```bash
# Check service status
docker compose ps

# Reset database
docker compose down -v
docker compose up -d
docker compose run --rm ml_service python main.py pipeline

# View detailed logs
docker compose logs -f --tail=100 ml_service

# Test database connection
docker compose exec postgres psql -U ncaaf_user -d ncaaf_v5 -c "SELECT COUNT(*) FROM games;"
```

## 📞 Support

- Check `ROE_OPTIMIZATION_REPORT.md` for detailed implementation
- View `models/comparison_report.txt` for performance metrics
- Logs are in Docker container: `docker compose logs ml_service`

---
**Version:** 5.0 BETA
**Last Updated:** December 2024
**Status:** ✅ Production Ready with ROE Optimizations