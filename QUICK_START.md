# 🚀 QUICK START - NCAAM MODEL

**Choose ONE option below:**

---

## Option A: Local Development (Windows)

```powershell
# Admin terminal
cd C:\Users\JDSB\dev\green_bier_sport_ventures\ncaam_gbsv_local\green_bier_sports_ncaam_model
.\scripts\setup-local-complete.ps1

# Verify (normal terminal)
.\scripts\verify-all.ps1

# Run
.\.venv\Scripts\Activate.ps1
cd services\prediction-service-python
python -m uvicorn app.main:app --reload --port 8000
```

**Time:** 15 minutes | **Cost:** Free | **Best for:** Full control

---

## Option B: Codespaces (Browser)

```
GitHub → Code button → Codespaces → Create codespace on main
→ Wait 2-3 min → Everything ready!
```

**Time:** 3 minutes | **Cost:** ~$0.07-0.18/hr | **Best for:** Quick collab

---

## Files You Need

✅ **SETUP.md** - Read this first (setup guide)
✅ **QUICK_START.md** - This file
✅ **scripts/setup-local-complete.ps1** - One setup script
✅ **scripts/verify-all.ps1** - Verify system
✅ **.devcontainer/devcontainer.json** - Codespaces config

❌ **DELETE** (old, no longer used):
- install-local-services.ps1
- setup-venv.ps1

---

## Architecture Overview

```
PostgreSQL (5432)
    ↓
Python ML Models (FastAPI)
    ↓
Redis Cache (6379)

Plus: Go ratings sync service

---

## Tonight workflow (live odds)

1) Set `ODDS_API_KEY` (or `THE_ODDS_API_KEY`).
2) From repo root: `python generate_tonight_picks.py --live` (2-3 hours before first tip).
3) Review outputs under `testing/results/predictions/tonight_picks_*.{csv,json}`.
4) Paper mode only; gate go-live on sustained positive ROI.
```

---

## If Stuck

1. **Read** `SETUP.md`
2. **Run** `.\scripts\verify-all.ps1`
3. **Check** error message
4. **Google** the error or check troubleshooting in SETUP.md

---

**That's it! 🎉**
